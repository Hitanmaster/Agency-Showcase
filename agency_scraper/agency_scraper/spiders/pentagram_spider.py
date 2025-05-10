import time
import scrapy
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

class PentagramSpider(scrapy.Spider):
    name = "pentagram_projects"
    allowed_domains = ["pentagram.com"]
    start_urls = ["https://www.pentagram.com/arts-culture"]

    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        self.driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=chrome_options
        )

    def parse(self, response):
        self.driver.get(response.url)
        time.sleep(3)

        prev_height = 0
        while True:
            try:
                load_more_btn = self.driver.find_element(By.CLASS_NAME, "load-more-button")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", load_more_btn)
                self.driver.execute_script("arguments[0].click();", load_more_btn)
                time.sleep(2)

                new_height = len(self.driver.page_source)
                if new_height == prev_height:
                    break  # No new content loaded
                prev_height = new_height

            except Exception as e:
                self.logger.info(f"No more 'Load More' button or error: {str(e)}")
                break

        # All content loaded. Now parse the cards.
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        cards = soup.find_all("div", class_="project-card")

        for card in cards:
            title_tag = card.find("h2")
            link_tag = card.find("a", href=True)
            desc_tag = card.find("p")

            image_tag = card.find("img")
            video_tag = card.find("video")

            yield {
                "title": title_tag.text.strip() if title_tag else None,
                "url": response.urljoin(link_tag["href"]) if link_tag else None,
                "description": desc_tag.text.strip() if desc_tag else None,
                "image": response.urljoin(image_tag["src"]) if image_tag else None,
                "video": response.urljoin(video_tag["src"]) if video_tag else None,
            }

    def closed(self, reason):
        self.driver.quit()
