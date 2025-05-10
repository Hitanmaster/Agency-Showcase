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

def scrape_pentagram_page(target_url, max_load_more_clicks=50, headless=True):
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

        print("Clicking 'Load More' button until it disappears...")
        clicks = 0
        while True:
            try:
                load_more_buttons = driver.find_elements(By.CSS_SELECTOR, load_more_button_selector)
                if not load_more_buttons:
                    print("No more 'Load More' button. Done loading.")
                    break

                for load_more_button in load_more_buttons:
                    if load_more_button.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", load_more_button)
                        print(f"Clicked 'Load More' ({clicks + 1}). Waiting...")
                        time.sleep(wait_time_after_click)
                        clicks += 1
                        break  # After first visible button click, re-loop to re-evaluate
                else:
                    print("Load More button not visible or clickable. Stopping.")
                    break
            except Exception as e:
                print(f"Error during 'Load More' clicking: {e}")
                break

        print("Parsing project cards...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        project_cards = soup.select(project_card_selector)
        print(f"Found {len(project_cards)} project cards in total.")

        # ... (media extraction and card parsing remains unchanged)

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
        "https://www.pentagram.com/arts-culture"
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

