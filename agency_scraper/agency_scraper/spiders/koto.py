import scrapy


class KotoSpider(scrapy.Spider):
    name = "koto"
    allowed_domains = ["koto.studio"]
    start_urls = ["https://koto.studio/work"]

    def parse(self, response):
        projects = response.css('a.work-row-thumb.tile')  # Target each project card

        for project in projects:
            title = project.css('h2::text').get(default='Untitled').strip()
            href = project.css('::attr(href)').get()
            video = project.css('::attr(data-work-page-thumbnail-video)').get()

            yield {
                'title': title,
                'url': response.urljoin(href),
                'video': video,
                'image': None,  # Optional: if you want to scrape thumbnails too
                'source': 'koto.studio'
            }
