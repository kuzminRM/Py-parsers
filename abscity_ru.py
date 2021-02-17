import requests
import json
import urllib3
import re
import time

from bs4 import BeautifulSoup
from urllib.parse import urljoin
from decimal import Decimal


class EstateObject():

    possible_types = ['flat', 'apartment', 'parking', 'commercial',
                      'storeroom', 'townhouse', 'cottage']

    def __init__(self):
        self.complex = None
        self.type = None
        self.phase = None
        self.building = None
        self.section = None
        self.price = None
        self.price_base = None
        self.price_sale = None
        self.price_finished = None
        self.price_finished_sale = None
        self.area = None
        self.living_area = None
        self.number = None
        self.number_on_site = None
        self.rooms = None
        self.floor = None
        self.in_sale = 1
        self.sale_status = None
        self.finished = 0
        self.currency = None
        self.ceil = None
        self.article = None
        self.finishing_name = None
        self.furniture = 0
        self.furniture_price = None
        self.plan = None
        self.feature = None
        self.view = None
        self.euro_planning = 0
        self.sale = None
        self.discount_percent = None
        self.discount = None

    @staticmethod
    def remove_restricted(value, restricted):
        if isinstance(value, str):
            value = value.lower().strip()
            for part in restricted:
                if part in value:
                    value = value.replace(part, '').strip()
        return value

    @staticmethod
    def correct_decimal_delimeter(value):
        if isinstance(value, str):
            return value.replace(',', '.')
        return value

    def set_complex(self, value, city):
        if 'апартамент' in value:
            self.type = 'apartment'

        name = re.search('«[\d,\D]*»', value)
        if name:
            self.complex = name.group(0) + " (" + city + ")"
        else:
            restricted_parts = ['\t', '\n', 'жк', "«", "»", 'апартаменты']
            value = self.remove_restricted(value, restricted_parts)
            self.complex = value + " (" + city + ")"

    def set_obj_type(self, value):
        self.type = value

    def set_phase(self, value):
        restricted_parts = ['очередь']
        value = self.remove_restricted(value, restricted_parts)
        self.phase = value

    def set_building(self, value):
        restricted_parts = ['корпус', 'корп.', 'корп', '№', 'дом', ':',
                            '\t', '\n', 'квартал']
        value = self.remove_restricted(value, restricted_parts)
        self.building = value

    def set_section(self, value):
        restricted_parts = ['секция', '№', ':', '\t', 'подъезд']
        value = self.remove_restricted(value, restricted_parts)
        self.section = value

    def _decode_price(self, value, multi=1):
        if isinstance(value, str) and 'запрос' in value:
            return
        restricted_parts = ['руб.', 'руб', ' ', 'цена:', 'млн.', 'млн',
                            '₽', 'р.', 'р', ' ']
        value = self.correct_decimal_delimeter(value)
        value = self.remove_restricted(value, restricted_parts)
        if value:
            return round(Decimal(value) * multi, 0)

    def _check_price_value(self, price):
        if price:
            if (price > 0 and price < 10000) or \
                    price > 1000000 * 100000:
                raise Exception('Wrong price value')

    def set_price_base(self, value, sale=None, multi=1):
        self.price_base = self._decode_price(value, multi)
        if sale:
            price_sale = self._decode_price(sale, multi)
            if price_sale:
                if price_sale < self.price_base:
                    self.price_sale = price_sale
                elif price_sale > self.price_base:
                    raise Exception('wrong price order')
        self._check_price_value(self.price_base)

    def _area_cleaner(self, value) -> Decimal:
        # restricted_parts = ['общая', 'площадь', 'м²', 'м2', 'кв.м.', 'кв.м',
        #                     'м', 'жилая', '\t', '\n', ' ']
        value = self.correct_decimal_delimeter(value)
        if isinstance(value, str):
            value = re.findall(r'[+-]?[0-9]*[.]?[0-9]+', value)[0]
        # value = self.remove_restricted(value, restricted_parts)
        return Decimal(value)

    def set_area(self, value):
        self.area = self._area_cleaner(value)

    def set_number(self, value):
        restricted_parts = ['офис', 'квартира', '№', 'машиноместо', 'кладовая',
                            'нежилое помещение']
        value = self.remove_restricted(value, restricted_parts)
        self.number = value

    def set_number_on_site(self, value):
        restricted_parts = ['офис', 'квартира', '№', 'машиноместо', 'кладовая',
                            'нежилое помещение']
        value = self.remove_restricted(value, restricted_parts)
        self.number_on_site = value

    def set_rooms(self, value):
        if isinstance(value, str):
            value = value.lower().strip()
            if 'одно' in value or '1' in value:
                self.rooms = 1
            elif 'двух' in value or '2' in value:
                self.rooms = 2
            elif 'трех' in value or 'трёх' in value or '3' in value:
                self.rooms = 3
            elif 'четырех' in value or '4' in value:
                self.rooms = 4
            elif 'пяти' in value or '5' in value:
                self.rooms = 5
            elif 'шести' in value or '6' in value:
                self.rooms = 6
            elif 'семи' in value or '7' in value:
                self.rooms = 7
            else:
                if 'студия' in value or 'студ' in value or\
                        'studio' in value or value == 'с'\
                        or value == 'c':
                    self.rooms = 'studio'
                elif "таун" in value:
                    self.type = 'townhouse'
                elif "коттедж" in value:
                    self.type = 'cottage'
                else:
                    value = re.findall(r'\d+', value)[0]
                    self.rooms = int(value)
        else:
            self.rooms = int(value)
        if self.rooms == 0:
            self.rooms = 'studio'
        if "евро" in value:
            self.set_euro_planning(1)

    def set_floor(self, value):
        if isinstance(value, str):
            if 'из' in value:
                value = value.split('из')[0]
            if '/' in value:
                value = value.split('/')[0]
            value = re.findall(r'-?\d+', value)[0]
        self.floor = int(value)

    def set_in_sale(self, value=1):
        if value not in [0, 1, None]:
            raise Exception('Wrong object in_sale attribute', value)
        self.in_sale = value

    def set_finished(self, value=0):
        if value not in [0, 1, None, 'optional']:
            raise Exception('Wrong object finished attribute', value)
        self.finished = value

    def set_currency(self, value):
        self.currency = value

    # Next go v_2.2 part

    def set_sale_status(self, value):
        restricted_parts = ['статус', ':']
        value = self.remove_restricted(value, restricted_parts)
        self.sale_status = value

    def set_living_area(self, value):
        if value:
            self.living_area = self._area_cleaner(value)

    def set_ceil(self, value):
        restricted_parts = ['высота потолка:', 'потолки', 'потолок',
                            ':', 'м.', 'м']
        value = self.correct_decimal_delimeter(value)
        value = self.remove_restricted(value, restricted_parts)
        self.ceil = Decimal(value)

    def set_article(self, value):
        restricted_parts = ['№', 'артикул:', 'тип планировки']
        value = self.remove_restricted(value, restricted_parts)
        self.article = value

    def set_finishing_name(self, value):
        restricted_parts = []
        value = self.remove_restricted(value, restricted_parts)
        self.finishing_name = value.lower()
        if "без" in self.finishing_name:
            self.set_finished(0)
            self.finishing_name = None
        else:
            self.set_finished(1)
            if "мебел" in self.finishing_name:
                self.set_furniture(1)

    def set_price_sale(self, value, multi=1):
        self.price_sale = self._decode_price(value, multi)
        self._check_price_value(self.price_sale)

    def set_price_finished(self, value, sale=None, multi=1):
        self.price_finished = self._decode_price(value, multi)
        self._check_price_value(self.price_finished)

    def set_price_finished_sale(self, value, sale=None, multi=1):
        self.price_finished_sale = self._decode_price(value, multi)
        self._check_price_value(self.price_finished_sale)

    def set_furniture_price(self, value, sale=None, multi=1):
        self.furniture_price = self._decode_price(value, multi)
        self._check_price_value(self.furniture_price)

    def set_furniture(self, value=0):
        if value not in [0, 1, 'optional', None]:
            raise Exception('Wrong object furniture attribute', value)
        self.furniture = value

    def set_plan(self, url, base_url=None):
        if url:
            if base_url:
                url = urljoin(base_url, url)
            self.plan = url

    def set_feature(self, value):
        if self.feature:
            if isinstance(self.feature, str):
                self.feature = [self.feature]
            self.feature.append(value)
        else:
            self.feature = value

    def set_view(self, value):
        if self.view:
            self.view.append(value)
        else:
            self.view = [value]

    def set_euro_planning(self, value):
        value = int(value)
        if value not in [0, 1, None]:
            raise Exception('Wrong object euro_planning attribute', value)
        self.euro_planning = value

    def set_sale(self, value):
        self.sale = value

    def set_discount_percent(self, value):
        restricted_parts = ['скидка', '%', '-']
        value = self.correct_decimal_delimeter(value)
        value = self.remove_restricted(value, restricted_parts)
        self.discount_percent = Decimal(value)

    def set_discount(self, value):
        self.discount = self._decode_price(value)

    def final_check(self):
        self._set_not_in_sale_if_no_price()
        self._swap_base_price_and_finish_price()
        self._validate_prices()
        if self.type not in EstateObject.possible_types:
            raise Exception('Wrong object type', self.type)

    def _set_not_in_sale_if_no_price(self):
        if not (self.price_base or self.price_sale or self.price_finished
                or self.price_finished_sale):
            self.set_in_sale(0)

    def _swap_base_price_and_finish_price(self):
        if self.finished and self.price_base and not self.price_finished:
            self.price_finished = self.price_base
            self.price_base = None

        if self.finished and self.price_sale and not self.price_finished_sale:
            self.price_finished_sale = self.price_sale
            self.price_sale = None

    def _validate_prices(self):
        if self.price_base and self.price_sale:
            if self.price_base < self.price_sale:
                raise Exception('Wrond sale price', self.price_base,
                                self.price_sale)

        if self.price_finished and self.price_finished_sale:
            if self.price_finished < self.price_finished_sale:
                raise Exception('Wrond price_finished_sale price',
                                self.price_finished,
                                self.price_finished_sale)

        if self.discount_percent and self.discount_percent > 30:
            raise Exception('Too big discount rate', self.discount_percent)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __hash__(self):
        return hash(tuple(sorted(self.__dict__.items())))

    def __repr__(self):
        return str(self.__dict__)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)


# ________ utils ________________
urllib3.disable_warnings()
loaded_objects = []
session = requests.Session()

URL_BASE = 'https://abscity.ru/novostroiki-spb/page-'


class EstateInstance(EstateObject):

    def __init__(self):
        super().__init__()
        self.type = 'flat'


def load_data():
    # ищем номер последней сраницы
    with session.get(URL_BASE + str(1), verify=False) as req:
        soup = BeautifulSoup(req.text, features='html5lib')
        max_page = int(re.search('\d{1,3}', soup.find("a", class_='pagination__item _last')['href']).group(0))

    for page in range(1, max_page+1):
        time.sleep(0.5)
        with session.get(URL_BASE+str(page), verify=False) as req:
            soup = BeautifulSoup(req.text, features='html5lib')
            links = list(map(lambda tag: tag.div.a['href'],
                             soup.find_all('div', class_='catalog-list__item catalog-card')))
            # есть два типа ссылок, например: https://abscity.ru/novostroiki-spb/zhk-126/ и https://kleny.abscity.ru/
            for link in links:
                if "abscity.ru/novostroiki-spb" in link:
                    with session.get(link, verify=False) as req:
                        soup = BeautifulSoup(req.text, features='html5lib')

                        complex = soup.find("div", class_='about-block__title')
                        # не всегда название в одном и том же месте
                        if complex:
                            complex = complex.h1.text
                        else:
                            complex = soup.find('h1', class_='hero__title')
                            if complex:
                                complex = complex.text
                            else:
                                continue

                        flats = soup.find_all("tr", class_='prices-plans-table__tr')
                        for flat in flats:
                            save_JS_obj(extract_data_1(complex, flat))
                else:
                    with session.get(link, verify=False) as req:
                        soup = BeautifulSoup(req.text, features='html5lib')

                        complex = soup.find("div", class_='about-block__title')
                        # не всегда название в одном и том же месте
                        if complex:
                            complex = complex.h1.text
                        else:
                            complex = soup.find('h1', class_='hero__title')
                            if complex:
                                complex = complex.text
                            else:
                                continue

                        flats = soup.find_all("div", class_='rooms-item')
                        for flat in flats:
                            save_JS_obj(extract_data_2(complex, flat, link))


def extract_data_1(complex, data):
    obj = EstateInstance()

    obj.set_complex(complex, 'Санкт-Петербург')
    obj.set_phase(data['data-queue'])
    obj.set_building(data['data-block'])
    obj.set_finishing_name(data['data-otdelka'])
    if obj.finished == 1:
        obj.set_price_finished(data['data-price'])
    else:
        obj.set_price_base(data['data-price'])
    obj.set_area(data['data-pl'])
    obj.set_rooms(data['data-kv'])
    obj.set_floor(data['data-floor'])
    obj.set_plan('https://abscity.ru/'+data.td.img['src'])
    return obj


def extract_data_2(complex, data, link):
    if 'rooms-item_button' in data['class']:
        return None
    if not data['data-price'] or int(data['data-price']) < 1_000_000:
        return None

    obj = EstateInstance()

    obj.set_complex(complex, 'Ленинградская область')
    obj.set_phase(data['data-queue'])
    obj.set_building(data['data-block'])
    obj.set_finishing_name(data['data-otdelka'])
    if obj.finished == 1:
        obj.set_price_finished(data['data-price'])
    else:
        obj.set_price_base(data['data-price'])
    obj.set_area(data['data-pl'])
    obj.set_rooms(data.find('div', class_='rooms-item__title').text)
    obj.set_floor(data['data-floor'])
    obj.set_plan(link+data.find("div", class_='rooms-item__img').img['src'])
    return obj


def save_JS_obj(obj):
    if obj:
        obj.final_check()
        loaded_objects.append(obj.__dict__)


def price():
    load_data()
    print(json.dumps(loaded_objects, cls=DecimalEncoder, indent=1,
                     sort_keys=False, ensure_ascii=False))


if __name__ == "__main__":
    price()
