import time
import json
import re
import os
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, OperationFailure
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    print("pymongo library not found. MongoDB upload will be disabled. To enable, run: pip install pymongo")

def upload_to_mongodb(data_list, mongo_uri, db_name, collection_name):
    if not PYMONGO_AVAILABLE:
        print("MongoDB upload skipped: pymongo library is not available.")
        return
    if not data_list:
        print("No data to upload to MongoDB.")
        return
    if not mongo_uri or mongo_uri == "YOUR_MONGODB_ATLAS_CONNECTION_STRING":
        print("MongoDB URI not configured. Skipping MongoDB upload.")
        return
    try:
        print(f"Attempting to connect to MongoDB: {mongo_uri.split('@')[-1] if '@' in mongo_uri else mongo_uri} ...")
        client = MongoClient(mongo_uri)
        client.admin.command('ismaster')
        print("Successfully connected to MongoDB.")
        db = client[db_name]
        collection = db[collection_name]
        print(f"Inserting {len(data_list)} documents into {db_name}.{collection_name}...")
        result = collection.insert_many(data_list)
        print(f"Successfully inserted {len(result.inserted_ids)} documents.")
    except ConnectionFailure:
        print("MongoDB connection failed. Please check your URI, IP whitelisting, and network settings.")
    except OperationFailure as e:
        print(f"MongoDB operation failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during MongoDB upload: {e}")
    finally:
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()
            print("MongoDB connection closed.")

def scrape_pentagram_page(target_url, max_load_more_clicks=20, headless=True):
    load_more_button_selector = "a[data-behavior='homeLoadMore']"
    project_card_selector = "div[data-behavior='projectCard']"
    wait_time_after_click = 4
    page_load_timeout = 45

    print(f"Setting up Chrome WebDriver (Headless: {headless})...")
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")

    driver = None
    try:
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
        driver.set_page_load_timeout(page_load_timeout)
    except Exception as e:
        print(f"Error setting up WebDriver: {e}")
        return []

    all_projects_data = []
    base_url = "https://www.pentagram.com"

    try:
        print(f"Navigating to {target_url}...")
        driver.get(target_url)
        WebDriverWait(driver, page_load_timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, project_card_selector)))
        print("Page loaded successfully.")

        clicks = 0
        while clicks < max_load_more_clicks:
            initial_card_count = len(driver.find_elements(By.CSS_SELECTOR, project_card_selector))
            try:
                load_more_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, load_more_button_selector)))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                time.sleep(0.8)
                driver.execute_script("arguments[0].click();", load_more_button)
                print(f"Clicked 'Load More' button ({clicks + 1}). Waiting for content...")
                time.sleep(wait_time_after_click)
                current_card_count = len(driver.find_elements(By.CSS_SELECTOR, project_card_selector))
                if current_card_count == initial_card_count:
                    print("Card count did not increase after click. Assuming all content is loaded.")
                    break
                clicks += 1
            except (TimeoutException, ElementClickInterceptedException, NoSuchElementException):
                print("No more 'Load More' button. Assuming all content is loaded.")
                break

        print("Parsing project cards...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        project_cards = soup.select(project_card_selector)
        print(f"Found {len(project_cards)} project cards in total.")

        for card_soup in project_cards:
            project_data = {
                "title": None,
                "project_page_url": None,
                "description": None,
                "media_url": None,
                "media_type": None,
                "categories": []
            }

            media_link_tag = card_soup.find('a', attrs={"aria-label": "view work"})
            if media_link_tag:
                href = media_link_tag.get("href")
                if href:
                    project_data["project_page_url"] = href if href.startswith("http") else f"{base_url}{href}"

                media_found = False
                video_tag = media_link_tag.find("video")
                if video_tag:
                    source_tag = video_tag.find("source")
                    if source_tag and source_tag.get("src"):
                        media_src = source_tag.get("src")
                        project_data["media_url"] = media_src if media_src.startswith("http") else f"{base_url}{media_src}"
                        project_data["media_type"] = "video"
                        media_found = True

                if not media_found:
                    picture_tag = media_link_tag.find("picture")
                    if picture_tag:
                        style_attr = picture_tag.get("style")
                        if style_attr:
                            match = re.search(r"background-image:\s*url\(['\"]?(.*?)['\"]?\)", style_attr)
                            if match:
                                img_url = match.group(1)
                                project_data["media_url"] = img_url
                                project_data["media_type"] = "image_from_picture_style"
                                media_found = True

                if not media_found and picture_tag:
                    source_tag = picture_tag.find("source")
                    if source_tag:
                        srcset = source_tag.get("srcset")
                        if srcset:
                            img_url = srcset.split(",")[0].split(" ")[0].strip()
                            project_data["media_url"] = img_url
                            project_data["media_type"] = "image_from_srcset"
                            media_found = True

                if not media_found:
                    img_tag = media_link_tag.find("img")
                    if img_tag:
                        img_src = img_tag.get("src") or img_tag.get("data-src")
                        if img_src and not img_src.startswith("data:image"):
                            project_data["media_url"] = img_src if img_src.startswith("http") else f"{base_url}{img_src}"
                            project_data["media_type"] = "image"
                            media_found = True

                if not project_data["media_url"]:
                    print(f"\u26a0\ufe0f  Media not found for card titled: {project_data.get('title') or '[No Title]'}")

            text_container = card_soup.select_one('a.block.pt-8.bg-primary, div.pt-8.bg-primary')
            if not text_container and media_link_tag:
                parent = media_link_tag.parent
                for tag in parent.find_all(['a', 'div'], recursive=False):
                    if tag != media_link_tag and tag.find('h3'):
                        text_container = tag
                        break
            if text_container:
                title_tag = text_container.find("h3")
                if title_tag:
                    project_data["title"] = title_tag.get_text(strip=True)
                desc_tag = text_container.find("p")
                if desc_tag:
                    project_data["description"] = desc_tag.get_text(strip=True)

            tags_container = card_soup.find("div", attrs={"data-projectcard-tags": ""})
            if tags_container:
                for cat_link in tags_container.find_all("a"):
                    span_tag = cat_link.find("span")
                    if span_tag:
                        category_name = span_tag.get_text(strip=True)
                        if category_name:
                            project_data["categories"].append(category_name)

            if project_data["title"] or project_data["project_page_url"]:
                all_projects_data.append(project_data)

    except TimeoutException:
        print(f"Page ({target_url}) did not load within timeout.")
    except Exception as e:
        print(f"Unexpected error during scraping: {e}")
    finally:
        if driver:
            driver.quit()
            print("WebDriver closed.")

    return all_projects_data

if __name__ == "__main__":
    urls_to_scrape = [
        "https://www.pentagram.com/arts-culture",
        "https://www.pentagram.com/technology",
    ]

    MONGO_URI = "YOUR_MONGODB_ATLAS_CONNECTION_STRING"
    MONGO_DB_NAME = "pentagram_projects_db"

    output_directory = "scraped_pentagram_data"
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for url in urls_to_scrape:
        print(f"\n--- Scraping URL: {url} ---")
        path_segment = urlparse(url).path.strip('/').split('/')[-1] or "homepage"
        file_name_base = re.sub(r'[^a-zA-Z0-9_-]', '_', path_segment)
        json_file_path = os.path.join(output_directory, f"{file_name_base}.json")
        mongo_collection_name = file_name_base

        scraped_data = scrape_pentagram_page(url, headless=True)

        if scraped_data:
            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(scraped_data, f, indent=4, ensure_ascii=False)
            print(f"Saved data to {json_file_path}")

            if PYMONGO_AVAILABLE and MONGO_URI != "YOUR_MONGODB_ATLAS_CONNECTION_STRING":
                upload_to_mongodb(scraped_data, MONGO_URI, MONGO_DB_NAME, mongo_collection_name)
            else:
                print("MongoDB upload skipped.")
        else:
            print(f"No data scraped from {url}")

    print("\n--- All scraping tasks completed. ---")
