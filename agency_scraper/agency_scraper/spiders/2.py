import time
import json
import datetime # Added for scraping date
import os      # Added to check if DB file exists
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- Configuration for simulated DB ---
DB_FILE = "pentagram_projects_db.json"

def load_existing_data(db_file_path):
    """Loads existing project data from the JSON DB file."""
    if not os.path.exists(db_file_path):
        print(f"Database file '{db_file_path}' not found. Starting fresh.")
        return []
    try:
        with open(db_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                print(f"Successfully loaded {len(data)} existing projects from '{db_file_path}'.")
                return data
            else:
                print(f"Data in '{db_file_path}' is not a list. Starting fresh.")
                return []
    except json.JSONDecodeError:
        print(f"Error decoding JSON from '{db_file_path}'. File might be corrupted or empty. Starting fresh.")
        return []
    except Exception as e:
        print(f"An error occurred while loading data from '{db_file_path}': {e}. Starting fresh.")
        return []

def save_data_to_db(db_file_path, data_to_save):
    """Saves the provided data to the JSON DB file."""
    try:
        with open(db_file_path, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved {len(data_to_save)} projects to '{db_file_path}'.")
    except Exception as e:
        print(f"An error occurred while saving data to '{db_file_path}': {e}")

def scrape_pentagram_arts_culture():
    """
    Scrapes project data from Pentagram's Arts & Culture page.
    Handles "Load More" button clicks and extracts details from each project card.
    Adds a scraped_date to each project.
    """
    # --- Configuration ---
    target_url = "https://www.pentagram.com/arts-culture"
    load_more_button_selector = "a[data-behavior='homeLoadMore']"
    project_card_selector = "div[data-behavior='projectCard']"
    max_load_more_clicks = 20 
    wait_time_after_click = 3  
    page_load_timeout = 30 

    # --- Setup Selenium WebDriver ---
    print("Setting up Chrome WebDriver...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    try:
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
        driver.set_page_load_timeout(page_load_timeout)
    except Exception as e:
        print(f"Error setting up WebDriver: {e}")
        print("Please ensure you have Google Chrome installed and an internet connection.")
        print("If issues persist, try running `pip install --upgrade webdriver-manager`.")
        return []

    current_scraped_projects = []

    try:
        # --- Navigate to the URL ---
        print(f"Navigating to {target_url}...")
        driver.get(target_url)
        WebDriverWait(driver, page_load_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, project_card_selector)) 
        )
        print("Page loaded successfully.")

        # --- Handle "Load More" Button ---
        print("Attempting to click 'Load More' button to load all projects...")
        prev_page_source_len = 0
        clicks = 0
        while clicks < max_load_more_clicks:
            current_page_source_len = len(driver.page_source)
            if clicks > 0 and current_page_source_len == prev_page_source_len:
                print("Page source length did not change. Assuming no new content loaded.")
                break
            prev_page_source_len = current_page_source_len

            try:
                load_more_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, load_more_button_selector))
                )
                driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                time.sleep(0.5) 
                driver.execute_script("arguments[0].click();", load_more_button)
                print(f"Clicked 'Load More' button ({clicks + 1}). Waiting for content...")
                time.sleep(wait_time_after_click) 
                clicks += 1
            except TimeoutException:
                print("No 'Load More' button found or it's no longer clickable. Assuming all content is loaded.")
                break
            except ElementClickInterceptedException:
                print("ElementClickInterceptedException. An overlay might be present or button not fully interactable.")
                time.sleep(1) 
                break
            except NoSuchElementException:
                print("NoSuchElementException for 'Load More' button. Assuming all content is loaded.")
                break
            except Exception as e:
                print(f"An error occurred while trying to click 'Load More': {e}")
                break
        
        if clicks == max_load_more_clicks:
            print(f"Reached maximum 'Load More' clicks ({max_load_more_clicks}). Proceeding with parsing.")

        # --- Parse Project Cards ---
        print("All content loaded (or 'Load More' process completed). Parsing project cards...")
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        
        project_cards = soup.select(project_card_selector)
        print(f"Found {len(project_cards)} project cards on the page.")
        
        today_date_iso = datetime.date.today().isoformat() # Get current date once

        for card_soup in project_cards:
            project_data = {
                "title": None,
                "url": None,
                "description": None,
                "media_url": None,
                "media_type": None, # 'image' or 'video'
                "scraped_date": today_date_iso # Add scraping date
            }
            
            text_container_link = card_soup.select_one("a.block.pt-8.bg-primary") 
            if not text_container_link:
                 all_direct_a_tags = card_soup.find_all('a', recursive=False)
                 if len(all_direct_a_tags) > 1:
                     text_container_link = all_direct_a_tags[1]

            if text_container_link:
                title_tag = text_container_link.find("h3", class_="f-body-1 text-primary")
                if title_tag:
                    project_data["title"] = title_tag.get_text(strip=True)

                project_url_path = text_container_link.get("href")
                if project_url_path:
                    if not project_url_path.startswith("http"):
                        project_data["url"] = f"https://www.pentagram.com{project_url_path}"
                    else:
                        project_data["url"] = project_url_path

                desc_tag = text_container_link.find("p", class_="f-body-1 text-secondary")
                if desc_tag:
                    project_data["description"] = desc_tag.get_text(strip=True)
            else: 
                title_tag_fallback = card_soup.find("h3")
                if title_tag_fallback:
                     project_data["title"] = title_tag_fallback.get_text(strip=True)
                first_a_tag = card_soup.find('a', recursive=False)
                if first_a_tag:
                    project_url_path = first_a_tag.get("href")
                    if project_url_path:
                        if not project_url_path.startswith("http"):
                            project_data["url"] = f"https://www.pentagram.com{project_url_path}"
                        else:
                            project_data["url"] = project_url_path
            
            media_container_link = card_soup.find('a', {"aria-label": "view work"})
            if not media_container_link:
                all_direct_a_tags = card_soup.find_all('a', recursive=False)
                if len(all_direct_a_tags) > 0:
                    media_container_link = all_direct_a_tags[0]

            if media_container_link:
                video_tag = media_container_link.find("video")
                if video_tag:
                    source_tag = video_tag.find("source")
                    if source_tag and source_tag.get("src"):
                        media_src = source_tag.get("src")
                        project_data["media_url"] = media_src if media_src.startswith("http") else f"https://www.pentagram.com{media_src}"
                        project_data["media_type"] = "video"

                if not project_data["media_url"]: 
                    picture_tag = media_container_link.find("picture")
                    img_tag = None
                    if picture_tag:
                        img_tag = picture_tag.find("img")
                    if not img_tag: 
                        img_tag = media_container_link.find("img")
                    
                    if img_tag:
                        media_src = img_tag.get("src")
                        if media_src:
                            project_data["media_type"] = "image"
                            if media_src.startswith("data:image"): # Handle lazy-loaded base64
                                srcset = img_tag.get('srcset')
                                if srcset:
                                    # Get the last URL from srcset (often highest resolution)
                                    # Format: "url1 w1, url2 w2, ..." or just "url1, url2"
                                    parts = srcset.split(',')
                                    last_part = parts[-1].strip()
                                    media_src = last_part.split(' ')[0] # Get URL part
                                else: # Fallback if srcset is not helpful, use style's background-image if present
                                    style_attr = picture_tag.get('style') if picture_tag else None
                                    if style_attr and 'background-image:url(' in style_attr:
                                        try:
                                            media_src = style_attr.split("background-image:url('")[1].split("');")[0]
                                        except IndexError:
                                            media_src = img_tag.get("src") # Original placeholder
                            
                            project_data["media_url"] = media_src if media_src.startswith("http") else f"https://www.pentagram.com{media_src}"


            if project_data.get("url"): # Use URL as a key indicator of a valid project
                current_scraped_projects.append(project_data)
            else:
                print(f"Skipping a card, could not extract URL. Title (if any): {project_data.get('title')}")

    except TimeoutException:
        print(f"Page ({target_url}) or a crucial element did not load within the timeout period.")
    except Exception as e:
        print(f"An unexpected error occurred during scraping: {e}")
    finally:
        if 'driver' in locals() and driver:
            print("Closing WebDriver...")
            driver.quit()
    
    return current_scraped_projects

if __name__ == "__main__":
    print(f"--- Starting Pentagram Scraper ---")
    # 1. Load existing data from DB
    existing_projects = load_existing_data(DB_FILE)
    existing_project_urls = {project.get("url") for project in existing_projects if project.get("url")}
    print(f"Found {len(existing_project_urls)} unique project URLs in the database.")

    # 2. Scrape current data from the website
    print("\n--- Scraping Live Data ---")
    currently_scraped_projects = scrape_pentagram_arts_culture()
    print(f"Scraped {len(currently_scraped_projects)} projects from the website in this run.")

    # 3. Identify new projects and prepare data for saving
    newly_added_to_db_count = 0
    all_projects_for_db = list(existing_projects) # Start with a copy of existing projects

    # Create a dictionary of existing projects by URL for easy update if needed (though here we just add new)
    # For this version, we are only adding new ones, not updating existing ones.
    
    for scraped_project in currently_scraped_projects:
        if scraped_project.get("url") and scraped_project.get("url") not in existing_project_urls:
            all_projects_for_db.append(scraped_project) # Add the new project
            existing_project_urls.add(scraped_project.get("url")) # Add to set to avoid duplicates in this run
            newly_added_to_db_count += 1
            print(f"  New project identified: {scraped_project.get('title')} ({scraped_project.get('url')})")

    # 4. Save updated data to DB if there were new additions or if DB was initially empty
    if newly_added_to_db_count > 0 or (not existing_projects and currently_scraped_projects):
        print(f"\n--- Updating Database ---")
        print(f"Adding {newly_added_to_db_count} new project(s) to the database.")
        save_data_to_db(DB_FILE, all_projects_for_db)
    else:
        print("\n--- Database Update ---")
        print("No new projects found to add to the database.")

    print(f"\n--- Scraping Complete ---")
    print(f"Total projects now in '{DB_FILE}': {len(all_projects_for_db)}")
    
    if newly_added_to_db_count > 0:
        print("\n--- Newly Added Projects This Run (JSON Preview) ---")
        newly_added_preview = [p for p in all_projects_for_db if p not in existing_projects][:5] # Preview first 5
        print(json.dumps(newly_added_preview, indent=4))


