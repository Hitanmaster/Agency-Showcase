import time
import json
import re # Added for regex
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def scrape_pentagram_arts_culture():
    """
    Scrapes project data from Pentagram's Arts & Culture page.
    Handles "Load More" button clicks and extracts details from each project card
    according to specified targeting rules.
    """
    # --- Configuration ---
    target_url = "https://www.pentagram.com/arts-culture"
    load_more_button_selector = "a[data-behavior='homeLoadMore']"
    project_card_selector = "div[data-behavior='projectCard']" # As per user request
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
        return []

    all_projects_data = []
    base_url = "https://www.pentagram.com"

    try:
        print(f"Navigating to {target_url}...")
        driver.get(target_url)
        WebDriverWait(driver, page_load_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, project_card_selector))
        )
        print("Page loaded successfully.")

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
                print("No 'Load More' button found or it's no longer clickable.")
                break
            except ElementClickInterceptedException:
                print("ElementClickInterceptedException for 'Load More'.")
                break
            except NoSuchElementException:
                print("NoSuchElementException for 'Load More' button.")
                break
            except Exception as e:
                print(f"An error occurred while trying to click 'Load More': {e}")
                break
        
        if clicks == max_load_more_clicks:
            print(f"Reached maximum 'Load More' clicks ({max_load_more_clicks}).")

        print("Parsing project cards...")
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        
        project_cards = soup.select(project_card_selector)
        print(f"Found {len(project_cards)} project cards.")

        for card_soup in project_cards:
            project_data = {
                "title": None,
                "project_page_url": None,
                "description": None,
                "media_url": None,
                "media_type": None, 
                "categories": []
            }

            # 1. Project URL (from <a aria-label="view work">)
            media_link_tag = card_soup.find('a', attrs={"aria-label": "view work"})
            if media_link_tag:
                href = media_link_tag.get("href")
                if href:
                    project_data["project_page_url"] = href if href.startswith("http") else f"{base_url}{href}"

                # 2. Media URL (Video or Image from picture style)
                video_tag = media_link_tag.find("video")
                if video_tag:
                    source_tag = video_tag.find("source")
                    if source_tag and source_tag.get("src"):
                        media_src = source_tag.get("src")
                        project_data["media_url"] = media_src if media_src.startswith("http") else f"{base_url}{media_src}"
                        project_data["media_type"] = "video"
                else:
                    picture_tag = media_link_tag.find("picture")
                    if picture_tag:
                        style_attr = picture_tag.get("style")
                        if style_attr:
                            # Regex to extract URL from background-image:url('...')
                            # Handles optional quotes around URL
                            match = re.search(r"background-image:\s*url\(['\"]?(.*?)['\"]?\)", style_attr)
                            if match:
                                img_url_from_style = match.group(1)
                                project_data["media_url"] = img_url_from_style # Already absolute from Pentagram's CDN
                                project_data["media_type"] = "image_from_picture_style"
                                # Note: This URL from picture style is often a low-res placeholder.
                                # For higher-res, one would typically parse <source srcset> or <img src> inside <picture>.
                    
                    # Fallback if specific image from picture style not found, try generic img src (as in previous version)
                    if not project_data["media_url"]:
                        img_tag_fallback = media_link_tag.find("img")
                        if img_tag_fallback and img_tag_fallback.get("src"):
                            img_src = img_tag_fallback.get("src")
                            if not img_src.startswith("data:image"): # Avoid base64 placeholders
                                project_data["media_url"] = img_src if img_src.startswith("http") else f"{base_url}{img_src}"
                                project_data["media_type"] = "image"


            # 3. Title and Description (from the sibling <a> tag)
            #    This is often the second direct 'a' child of the project card, or one with specific classes.
            text_content_elements = card_soup.select('a.block.pt-8.bg-primary, div.pt-8.bg-primary') # Handles if it's a div sometimes
            
            text_container = None
            if text_content_elements:
                text_container = text_content_elements[0] # Take the first match

            if not text_container: # Broader fallback if specific classes not found
                # Try to find a container that is not the media_link_tag and contains h3
                potential_text_containers = card_soup.find_all(['a','div'], recursive=False)
                for ptc in potential_text_containers:
                    if ptc != media_link_tag and ptc.find('h3'):
                        text_container = ptc
                        break
            
            if text_container:
                title_tag = text_container.find("h3") # As per user: target h3
                if title_tag:
                    project_data["title"] = title_tag.get_text(strip=True)

                desc_tag = text_container.find("p") # As per user: target p
                if desc_tag:
                    project_data["description"] = desc_tag.get_text(strip=True)
            
            # 4. Categories
            tags_container = card_soup.find("div", attrs={"data-projectcard-tags": ""})
            if tags_container:
                category_links = tags_container.find_all("a")
                for cat_link in category_links:
                    span_tag = cat_link.find("span")
                    if span_tag:
                        category_name = span_tag.get_text(strip=True)
                        if category_name:
                            project_data["categories"].append(category_name)
            
            if project_data["title"] or project_data["project_page_url"]: # Add if we have some key info
                all_projects_data.append(project_data)
            else:
                print(f"Skipping a card, could not extract minimal data. Card HTML snippet: {str(card_soup)[:200]}...")

    except TimeoutException:
        print(f"Page ({target_url}) or a crucial element did not load within the timeout period.")
    except Exception as e:
        print(f"An unexpected error occurred during scraping: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging
    finally:
        if 'driver' in locals() and driver:
            print("Closing WebDriver...")
            driver.quit()
    
    return all_projects_data

if __name__ == "__main__":
    scraped_data = scrape_pentagram_arts_culture()
    if scraped_data:
        print("\n--- Scraped Data (JSON) ---")
        print(json.dumps(scraped_data, indent=4))
        print(f"\nSuccessfully scraped {len(scraped_data)} projects.")
        
        # To save to a file:
        # file_path = "pentagram_projects_updated.json"
        # with open(file_path, "w", encoding="utf-8") as f:
        #     json.dump(scraped_data, f, indent=4, ensure_ascii=False)
        # print(f"\nData also saved to {file_path}")
    else:
        print("No data was scraped or an error occurred.")

