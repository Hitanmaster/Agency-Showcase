import scrapy
import datetime
from urllib.parse import urlparse
from pymongo import MongoClient

class PentagramSpider(scrapy.Spider):
    name = "pentagram"
    allowed_domains = ["pentagram.com"]

    category_urls = {
        "Arts & Culture": "https://www.pentagram.com/work/sector/arts-culture",
        "Banking & Finance": "https://www.pentagram.com/work/sector/banking-finance",
        "Civic & Public": "https://www.pentagram.com/work/sector/civic-public",
        "Design & Architecture": "https://www.pentagram.com/work/sector/design-architecture",
        "Education": "https://www.pentagram.com/work/sector/education",
        "Entertainment": "https://www.pentagram.com/work/sector/entertainment",
        "Fashion & Beauty": "https://www.pentagram.com/work/sector/fashion-beauty",
        "Food & Drink": "https://www.pentagram.com/work/sector/food-drink",
        "Healthcare": "https://www.pentagram.com/work/sector/healthcare",
        "Hospitality & Leisure": "https://www.pentagram.com/work/sector/hospitality-leisure",
        "Manufacturing & Industrials": "https://www.pentagram.com/work/sector/manufacturing-industrials",
        "Not for Profit": "https://www.pentagram.com/work/sector/not-for-profit",
        "Professional Services": "https://www.pentagram.com/work/sector/professional-services",
        "Publishing": "https://www.pentagram.com/work/sector/publishing",
        "Real Estate": "https://www.pentagram.com/work/sector/real-estate",
        "Retail": "https://www.pentagram.com/work/sector/retail",
        "Technology": "https://www.pentagram.com/work/sector/technology",
        "Transport": "https://www.pentagram.com/work/sector/transport",
    }

    def __init__(self):
        # Setup MongoDB connection (replace with your connection string)
        mongo_uri = "mongodb+srv://Himanshu:Himanshu#0987@cluster0.mbirvgi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
        self.client = MongoClient(mongo_uri)
        self.db = self.client["agency_data"]
        self.collection = self.db["projects"]

    def start_requests(self):
        for category, url in self.category_urls.items():
            yield scrapy.Request(url=url, callback=self.parse_category, meta={"category": category})

    def parse_category(self, response):
        category = response.meta["category"]
        projects = response.css("article.workItem")

        for project in projects:
            try:
                title = project.css(".workItem__title span::text").get(default="Untitled").strip()
                href = project.css("a.workItem__link::attr(href)").get()
                url = response.urljoin(href) if href else None

                video_tag = project.css("video source[type='video/mp4']::attr(src)").get()
                img_tag = project.css("img.workItem__img::attr(src)").get()

                if not url:
                    self.logger.warning(f"Missing URL for project in category: {category}")
                    continue

                document = {
                    "title": title or "Untitled",
                    "url": url,
                    "video": video_tag,
                    "image": img_tag,
                    "source": "pentagram.com",
                    "category": category,
                    "timestamp": datetime.datetime.utcnow()
                }

                if not self.collection.find_one({"url": url}):
                    self.collection.insert_one(document)
                    yield document
            except Exception as e:
                self.logger.error(f"Error parsing project in category '{category}': {e}")
