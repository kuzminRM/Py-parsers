import scrapy


class AuthorSpider(scrapy.Spider):
    name = 'dromRU'

    def gen(url):
        # 0 - 2 999 999
        for cost in range(0, 60):
            for dist in range(0, 100):
                yield url+'?minprice=%d&maxprice=%d&minprobeg=%d&maxprobeg=%d' % (
                    cost * 50_000, (cost + 1) * 50_000 - 1, dist * 10_000, (dist + 1) * 10_000 - 1)
        # 3 000 000 - 5 999 999
        for cost in range(0, 30):
            yield url+'?minprice=%d&maxprice=%d' % (3_000_000 + cost * 100_000, 3_000_000 + (cost + 1) * 100_000 - 1)
        # over 6 000 000
        yield url+'?minprice=%d' % (6_000_000)

    start_urls = (link for link in gen("https://auto.drom.ru/bez-probega/all/"))

    def parse(self, response):
        for car in response.xpath('.//a[@data-ftid="bulls-list_bull"]'):
            header = car.xpath(".//span[@data-ftid='bull_title']/text()").get(default=None)  # - заголовки
            price = car.xpath(".//span[@data-ftid='bull_price']/text()").re(r'\d+\s\d+\s*\d*')[0]  # - цены
            city = car.xpath(".//span[@data-ftid='bull_location']/text()").get(default=None)  # - город
            docs = bool(car.xpath(".//div[@data-ftid='bull_label_nodocs']/img/@title").get(
                default=None))  # - проблемы с документами
            broken = bool(
                car.xpath(".//div[@data-ftid='bull_label_broken']/img/@title").get(default=None))  # - битая/не на ходу
            estimation = car.xpath("./div[3]/div[1]/div[2]/div/text()").get()

            car_page_link = car.xpath('@href').get()  # - ссылка на машину

            yield scrapy.Request(car_page_link,
                                 callback=self.parse_car,
                                 cb_kwargs=dict(header=header, price=price, city=city, docs=docs, broken=broken, estimation=estimation))

        pagination_links = response.xpath('.//a[@data-ftid="component_pagination-item-next"]')
        yield from response.follow_all(pagination_links, self.parse)

    def parse_car(self, response, header, price, city, docs, broken, estimation):
        key = ['Заголовок', 'Цена', 'Город', 'docs', 'broken', 'Оценка']
        key += response.xpath(".//th/text()").getall()  # - ключи для словаря

        arg = [header, price, city, docs, broken, estimation]
        arg += response.xpath(
            ".//td/text()[1]|.//td/span/text()[1]|.//td/span/a/text()[1]|.//td/a/text()[1]").getall()  # - значения словаря

        yield dict(zip(key, arg))
