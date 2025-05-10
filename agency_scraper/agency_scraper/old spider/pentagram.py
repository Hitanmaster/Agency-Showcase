import scrapy
import json
import datetime
from pymongo import MongoClient
from pathlib import Path

class PentagramSpider(scrapy.Spider):
    name = "pentagram"
    allowed_domains = ["pentagram.com"]

    category_urls = {
        "Arts & Culture": "https://www.pentagram.com/arts-culture",
        "Banking & Finance": "https://www.pentagram.com/banking-finance",
        "Civic & Public": "https://www.pentagram.com/civic-public",
        "Design & Architecture": "https://www.pentagram.com/design-architecture",
        "Education": "https://www.pentagram.com/education",
        "Entertainment": "https://www.pentagram.com/entertainment",
        "Fashion & Beauty": "https://www.pentagram.com/fashion-beauty",
        "Food & Drink": "https://www.pentagram.com/food-drink",
        "Healthcare": "https://www.pentagram.com/healthcare",
        "Hospitality & Leisure": "https://www.pentagram.com/hospitality-leisure",
        "Manufacturing & Industrials": "https://www.pentagram.com/manufacturing-industrials",
        "Not for Profit": "https://www.pentagram.com/not-for-profit",
        "Professional Services": "https://www.pentagram.com/professional-services",
        "Publishing": "https://www.pentagram.com/publishing",
        "Real Estate": "https://www.pentagram.com/real-estate",
        "Retail": "https://www.pentagram.com/retail",
        "Technology": "https://www.pentagram.com/technology",
        "Transport": "https://www.pentagram.com/transport",
    }

    def __init__(self):
        self.output_file = Path("pentagram_data.json")
        self.results = []
        self.client = MongoClient("mongodb+srv://Himanshu:Himanshu#0987@cluster0.mbirvgi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        self.db = self.client["agency_data"]
        self.collection = self.db["projects"]

    def start_requests(self):
        for category, url in self.category_urls.items():
            yield scrapy.Request(url=url, callback=self.parse_category)

    def parse_category(self, response):
        projects = response.css("li[data-behavior='projectCard']")

        for proj in projects:
            try:
                title = proj.css("h3::text").get(default="Untitled").strip()
                url = proj.css("a::attr(href)").get()
                full_url = response.urljoin(url)

                video_tag = proj.css("video source[type='video/mp4']::attr(src)").get()
                img_tag = proj.css("picture img::attr(src)").get()

                document = {
                    "title": title,
                    "url": full_url,
                    "video": video_tag,
                    "image": img_tag,
                    "source": "pentagram.com"
                }

                self.results.append(document)

            except Exception as e:
                self.logger.error(f"Error parsing project: {e}")

    def closed(self, reason):
        # Save JSON in requested format
        with self.output_file.open("w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        self.logger.info(f"Saved {len(self.results)} items to {self.output_file}")

        # Insert to MongoDB if not already present
        try:
            for doc in self.results:
                if not self.collection.find_one({"url": doc["url"]}):
                    # Add timestamp for DB only
                    doc_with_time = doc.copy()
                    doc_with_time["timestamp"] = datetime.datetime.utcnow()
                    self.collection.insert_one(doc_with_time)
            self.logger.info("Inserted new documents to MongoDB")
        except Exception as e:
            self.logger.error(f"MongoDB insertion failed: {e}")
