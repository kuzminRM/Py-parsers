import json
import urllib3
import requests
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple
from time import sleep

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def init_realty_object(complex_name: str, region: str, realty_type: str) -> dict:
    return {
        'complex': f'{complex_name} ({region})',
        'type': realty_type,
        'phase': None,
        'building': None,
        'section': None,
        'price_base': None,
        'price_finished': None,
        'price_sale': None,
        'price_finished_sale': None,
        'area': None,
        'living_area': None,
        'number': None,
        'number_on_site': None,
        'rooms': None,
        'floor': None,
        'in_sale': None,
        'sale_status': None,
        'finished': None,
        'currency': None,
        'ceil': None,
        'article': None,
        'finishing_name': None,
        'furniture': None,
        'furniture_price': None,
        'plan': None,
        'feature': None,
        'view': None,
        'euro_planning': None,
        'sale': None,
        'discount_percent': None,
        'discount': None,
        'comment': None,
    }


class PikParser:
    def __init__(self):
        self.thread_pool = ThreadPoolExecutor(max_workers=20)
        self.realty_types_map = {
            '1': 'flat',
            '2': 'apartment',
            '4': 'commercial',
            '5': 'parking',
            '6': 'storeroom',
        }
        self.realty_objects = []
        self.errors = []

    @staticmethod
    def request(url: str, max_attempts: int = 3) -> Dict:
        '''
        Умеет повторить HTTP запрос через 5, 10 и 15 секунд.
        После трех неудачных попыток, бросит исключение.
        Кол-во попыток задается параметром.
        '''
        errors = []
        timeout_between_requests = 5
        for t in range(max_attempts):
            try:
                with requests.get(url, verify=False, timeout=90) as response:
                    return response.json()
            except Exception as e:
                errors.append(e)
            sleep(timeout_between_requests * len(errors))
        message = f'HTTP request failed: max retries exceeded with url {url}'
        raise Exception(message) from errors.pop()

    def fetch_complexes(self) -> List[Tuple]:
        complexes = []
        url = 'https://api.pik.ru/v2/filter?filter=1'
        data = self.request(url)
        for complex_data in data['block']:
            name = complex_data['name']
            name = name and name.strip()
            if not name:
                continue
            name = name[:name.index('(') - 1:] if '(' in name else name
            region = complex_data['locations']['parent']['name']
            region = region.strip().capitalize()
            if not region:
                continue
            complexes.append((complex_data['id'], name, region, complex_data['counts']))
        return complexes

    def load_realty_objects(self, complex_data: tuple, realty_type_id: str):
        complex_id, complex_name, region = complex_data
        try:
            bulks = self.fetch_bulks(complex_id, realty_type_id)
            realty_type_name = self.realty_types_map[realty_type_id]
            for bulk in bulks:
                raw_objects = self.fetch_realty_objects(realty_type_name, bulk)
                self.create_realty_objects(complex_data, raw_objects)
        except Exception as e:
            self.errors.append(e)

    def fetch_bulks(self, complex_id: int, realty_type_id: str):
        base_url = 'https://api.pik.ru/v1/bulk/chessplan?new=1&block_id={complex_id}&types={realty_type}'
        # TODO: надо перейти на v2 API, там есть знание про аукцион
        # base_url = 'https://api.pik.ru/v2/filter?type={realty_type}&block={complex_id}'
        url = base_url.format(complex_id=complex_id, realty_type=realty_type_id)
        response = self.request(url)
        sleep(1.5)
        return response['bulks'] or []

    def fetch_realty_objects(self, realty_type_name: str, bulk: Dict) -> List[Tuple]:
        sections = bulk.get('sections')
        if not sections:
            return
        if bulk['name']:
            stop_list = ['дом', 'корпус', 'блок', 'строение', 'владение',
                         'вл', 'башня', 'д', 'вавилова', 'подземный', 'паркинг']
            name = bulk['name'].lower().replace('д.', '').replace('корп.', '')
            name = name.split()
            format_name = []
            for n in name:
                if n.lower() not in stop_list:
                    format_name.append(n.replace(',', ''))
            building_id = '.'.join(format_name)
            if 'корп' in building_id:
                building_id = building_id.replace('корпус.', '').replace('.', '', 1)
        else:
            building_id = None
        raw_objects = []
        section_regex = re.compile(r'(секция|подъезд)\s*:?\s*(\d+).*', re.UNICODE | re.IGNORECASE)
        for section in sections:
            floors = section.get('floors')
            if not floors:
                continue
            if isinstance(floors, list):
                floors = {1: floors[0]}
            section_name = section.get('name')
            if section_name:
                matched = section_regex.search(section_name)
                section_id = matched and matched[2]
            else:
                section_id = None
            for floor_number, floor_data in floors.items():
                objects = floor_data.get('flats')
                if not objects:
                    continue
                raw_objects.append(
                    (realty_type_name, building_id, section_id, floor_number, objects)
                )
        return raw_objects

    def create_realty_objects(self, complex_data: Tuple, raw_objects: List[Tuple]):
        complex_id, complex_name, region = complex_data
        for realty_type_name, building_id, section_id, floor, objects in raw_objects:
            for raw_data in objects:
                realty_object = init_realty_object(complex_name, region, realty_type_name)
                realty_object['building'] = building_id
                realty_object['floor'] = int(floor)
                realty_object['section'] = section_id
                self.fill_realty_object(raw_data, realty_object, realty_type_name)
                if self.validate_realty_object(realty_object):
                    if realty_object['in_sale']:
                        self.realty_objects.append(realty_object)

    def fill_realty_object(self, raw_data: dict, realty_object: dict, realty_type: str):
        # Общая часть
        furniture = raw_data.get('furniture') or raw_data.get('kitchenFurniture')
        realty_object['furniture'] = furniture and 1 or 0
        realty_object['euro_planning'] = 0  # TODO: сохраняем поведение старого парсера. Спорный момент
        sale_status = raw_data['status'].strip().lower()
        realty_object['in_sale'] = (sale_status in {'free', 'reserve'}) and 1 or 0
        realty_object['sale_status'] = (sale_status == 'reserve') and 'Зарезервирована' or None
        realty_object['area'] = round(float(raw_data['area']), 2) or None
        realty_object['number'] = raw_data['number']
        if raw_data.get('finish'):
            realty_object['price_finished'] = raw_data['price']
            realty_object['finished'] = 1
        else:
            realty_object['price_base'] = raw_data['price']
            realty_object['finished'] = 0
        layout = raw_data.get('layout')
        if layout:
            plan = layout.get('plan') or layout.get('preview')
            plan_url = plan and plan.strip()
            if plan_url:
                realty_object['plan'] = f'http:{plan_url}'
            article = layout.get('name')
            realty_object['article'] = article.strip() if article else None
        # Специфичные части
        if realty_type in {'flat', 'apartment'}:
            if realty_type == 'apartment' and realty_object['in_sale']:
                res = self.request('https://api.pik.ru/v1/flat?id={}&similar=1'.format(raw_data['id']))
                if res and res.get('layout'):
                    realty_object['article'] = res['layout']['name']
                    realty_object['plan'] = res.get('layout').get('flat_plan_svg') or \
                                            res.get('layout').get('flat_plan_png')
            self.fill_flat_data(raw_data, realty_object)
        elif realty_type == 'parking':
            pass
        elif realty_type == 'commercial':
            pass
        elif realty_type == 'storeroom':
            pass
        return realty_object

    def fill_flat_data(self, raw_data: dict, realty_object: dict):
        realty_object['number'] = raw_data['apartment_number']
        rooms = raw_data['rooms']
        realty_object['rooms'] = int(rooms) if rooms.isnumeric() else rooms
        realty_object['number_on_site'] = raw_data['stage_number']

    def validate_realty_object(self, realty_object: dict):
        """
        Всякие проверки полученных данных.
        """
        rooms = realty_object['rooms'] or 0
        area = realty_object['area'] or 0
        if isinstance(rooms, int) and rooms > 10 and area < 100:
            raise Exception(f'Маленькая площадь ({area}) при большом кол-ве комнат ({rooms})')
        if isinstance(rooms, int) and rooms > 30:
            raise Exception(f'Слишком большое кол-во комнат ({rooms})')
        floor = realty_object['floor'] or 0
        if floor > 100:
            raise Exception(f'Слишком большое кол-во этажей ({floor})')
        realty_type = realty_object['type']
        if realty_type in {'flat', 'apartment', 'parking'} and area < 10:
            return False
        if realty_type == 'parking' and area > 50:
            return False
        prices = (
            realty_object['price_base'],
            realty_object['price_finished'],
            realty_object['price_sale'],
            realty_object['price_finished_sale']
        )
        if not any(prices):
            realty_object['in_sale'] = 0
        if realty_type == 'parking' or realty_type == 'storeroom':
            realty_object['rooms'] = None
        price = realty_object['price_base'] or realty_object['price_finished'] or 0
        if price and price / area < 20000:
            return False
        return True

    def run(self):
        complexes = self.fetch_complexes()
        for complex_data in complexes:
            for type_id, type_name in self.realty_types_map.items():
                if complex_data[3][type_id] != 0:
                    self.load_realty_objects(complex_data[0:3], type_id)

        print(json.dumps(self.realty_objects, sort_keys=False, ensure_ascii=False))


if __name__ == '__main__':
    PikParser().run()
