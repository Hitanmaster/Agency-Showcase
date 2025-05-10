import scrapy
import json
import datetime
from pymongo import MongoClient

class PentagramSpider(scrapy.Spider):
    name = "pentagram_updated"
    allowed_domains = ["pentagram.com"]
    start_urls = ["https://www.pentagram.com/work"]

    def __init__(self):
        # Setup MongoDB connection (replace with your actual MongoDB URI)
        mongo_uri = "YOUR_MONGODB_URI"
        self.client = MongoClient(mongo_uri)
        self.db = self.client["agency_data"]
        self.collection = self.db["projects"]

    def parse(self, response):
        # Extract all initial project cards
        yield from self.extract_projects(response)

        # Extract "load more" button endpoint if it exists
        next_url = response.css("button[data-endpoint]").attrib.get("data-endpoint")
        if next_url:
            yield response.follow(next_url, callback=self.load_more)

    def load_more(self, response):
        # Called when new projects are loaded via "Load More"
        yield from self.extract_projects(response)

        # Repeat if more load-more buttons appear
        next_url = response.css("button[data-endpoint]").attrib.get("data-endpoint")
        if next_url:
            yield response.follow(next_url, callback=self.load_more)

    def extract_projects(self, response):
        projects = response.css("li[data-behavior='projectCard']")

        for proj in projects:
            try:
                title = proj.css("h3::text").get(default="Untitled").strip()
                url = proj.css("a::attr(href)").get()
                full_url = response.urljoin(url)

                description = proj.css("p::text").get(default="").strip()
                image_url = proj.css("picture img::attr(src)").get()

                document = {
                    "title": title,
                    "url": full_url,
                    "description": description,
                    "image": image_url,
                    "source": "pentagram.com",
                    "timestamp": datetime.datetime.utcnow()
                }

                if not self.collection.find_one({"url": full_url}):
                    self.collection.insert_one(document)
                    yield document
            except Exception as e:
                self.logger.error(f"Error parsing project: {e}")
