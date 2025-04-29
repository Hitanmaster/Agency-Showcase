import scrapy
from datetime import datetime


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
                "agency_name": "Koto Studio",
                "project_title": title,
                "project_description": "",  # Optional: we don't have it here yet
                "project_url": response.urljoin(href),
                "project_images": [video] if video else [],
                "tags": [],  # Empty for now, you can add manually later if needed
                "scraped_date": datetime.utcnow().isoformat(),
                "last_updated": datetime.utcnow().isoformat()
            }
