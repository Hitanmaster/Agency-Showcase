import time
import json
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
    Handles "Load More" button clicks and extracts details from each project card.
    """
    # --- Configuration ---
    target_url = "https://www.pentagram.com/arts-culture"
    load_more_button_selector = "a[data-behavior='homeLoadMore']"
    project_card_selector = "div[data-behavior='projectCard']"
    max_load_more_clicks = 20 # Safety break for the load more loop
    wait_time_after_click = 3  # Seconds to wait after clicking "Load More"
    page_load_timeout = 30 # Seconds to wait for initial page load

    # --- Setup Selenium WebDriver ---
    print("Setting up Chrome WebDriver...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode (no browser window)
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

    all_projects_data = []

    try:
        # --- Navigate to the URL ---
        print(f"Navigating to {target_url}...")
        driver.get(target_url)
        WebDriverWait(driver, page_load_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, project_card_selector)) # Wait for initial cards
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
                # Wait for the button to be potentially available and clickable
                load_more_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, load_more_button_selector))
                )
                
                # Scroll to the button and click using JavaScript for robustness
                driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                time.sleep(0.5) # Brief pause after scroll
                driver.execute_script("arguments[0].click();", load_more_button)
                
                print(f"Clicked 'Load More' button ({clicks + 1}). Waiting for content...")
                time.sleep(wait_time_after_click) # Wait for content to load
                clicks += 1
            except TimeoutException:
                print("No 'Load More' button found or it's no longer clickable. Assuming all content is loaded.")
                break
            except ElementClickInterceptedException:
                print("ElementClickInterceptedException. Trying to scroll and click again or an overlay might be present.")
                # Potentially add logic here to handle overlays if they are common
                time.sleep(1) # Wait a bit before retrying or breaking
                # For simplicity, we break here, but more sophisticated handling could be added
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
        print(f"Found {len(project_cards)} project cards.")

        for card_soup in project_cards:
            project_data = {
                "title": None,
                "url": None,
                "description": None,
                "media_url": None,
                "media_type": None # 'image' or 'video'
            }

            # The card structure usually has two main 'a' tags:
            # 1. Wraps the media (image/video)
            # 2. Wraps the text content (title, description)
            
            # Find the 'a' tag that contains the title and description
            # This is typically the second 'a' tag or one with specific classes like 'block pt-8 bg-primary'
            text_container_link = card_soup.select_one("a.block.pt-8.bg-primary") # More specific selector
            if not text_container_link: # Fallback to second 'a' if specific class not found
                 all_direct_a_tags = card_soup.find_all('a', recursive=False)
                 if len(all_direct_a_tags) > 1:
                     text_container_link = all_direct_a_tags[1]


            if text_container_link:
                title_tag = text_container_link.find("h3", class_="f-body-1 text-primary")
                if title_tag:
                    project_data["title"] = title_tag.get_text(strip=True)

                project_data["url"] = text_container_link.get("href")
                if project_data["url"] and not project_data["url"].startswith("http"):
                    project_data["url"] = f"https://www.pentagram.com{project_data['url']}"


                desc_tag = text_container_link.find("p", class_="f-body-1 text-secondary")
                if desc_tag:
                    project_data["description"] = desc_tag.get_text(strip=True)
            else: # Fallback if the text container link is not found as expected
                title_tag_fallback = card_soup.find("h3")
                if title_tag_fallback:
                     project_data["title"] = title_tag_fallback.get_text(strip=True)
                # Attempt to get URL from the first link if text_container_link failed
                first_a_tag = card_soup.find('a', recursive=False)
                if first_a_tag:
                    project_data["url"] = first_a_tag.get("href")
                    if project_data["url"] and not project_data["url"].startswith("http"):
                         project_data["url"] = f"https://www.pentagram.com{project_data['url']}"


            # Find the media URL (image or video)
            # This is usually in the first 'a' tag within the card
            media_container_link = card_soup.find('a', {"aria-label": "view work"}) # More specific selector
            if not media_container_link:
                all_direct_a_tags = card_soup.find_all('a', recursive=False)
                if len(all_direct_a_tags) > 0:
                    media_container_link = all_direct_a_tags[0]

            if media_container_link:
                video_tag = media_container_link.find("video")
                if video_tag:
                    source_tag = video_tag.find("source")
                    if source_tag and source_tag.get("src"):
                        project_data["media_url"] = source_tag.get("src")
                        project_data["media_type"] = "video"
                        if project_data["media_url"] and not project_data["media_url"].startswith("http"):
                             project_data["media_url"] = f"https://www.pentagram.com{project_data['media_url']}"


                if not project_data["media_url"]: # If no video, look for an image
                    # Look for img tag directly within picture, or just an img tag
                    picture_tag = media_container_link.find("picture")
                    img_tag = None
                    if picture_tag:
                        img_tag = picture_tag.find("img")
                    if not img_tag: # Fallback if img is not inside picture or picture not found
                        img_tag = media_container_link.find("img")
                    
                    if img_tag and img_tag.get("src"):
                        project_data["media_url"] = img_tag.get("src")
                        project_data["media_type"] = "image"
                        # Check if src is a placeholder (e.g., base64 for lazy loading)
                        if project_data["media_url"].startswith("data:image"):
                            # Try to get from srcset or other attributes if main src is placeholder
                            # This part can be complex due to various lazy loading techniques
                            # For now, we'll take the src, but acknowledge it might be a placeholder
                            srcset = img_tag.get('srcset')
                            if srcset:
                                # Simplistic way to get a URL from srcset (often the last one is highest res)
                                project_data["media_url"] = srcset.split(',')[-1].strip().split(' ')[0]
                        
                        if project_data["media_url"] and not project_data["media_url"].startswith("http"):
                             project_data["media_url"] = f"https://www.pentagram.com{project_data['media_url']}"


            if project_data["title"]: # Only add if we found a title (basic check for valid card)
                all_projects_data.append(project_data)
            else:
                print(f"Skipping a card, could not extract minimal data (e.g., title). Card HTML: {card_soup.prettify()[:200]}...")


    except TimeoutException:
        print(f"Page ({target_url}) or a crucial element did not load within the timeout period.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        # --- Cleanup ---
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
        
        # Example: Save to a JSON file
        # with open("pentagram_projects.json", "w", encoding="utf-8") as f:
        #     json.dump(scraped_data, f, indent=4, ensure_ascii=False)
        # print("\nData also saved to pentagram_projects.json")
    else:
        print("No data was scraped.")