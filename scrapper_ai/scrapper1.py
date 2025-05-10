# scrape_dynamic_cloudshell_filtered.py

import os
import json
import time
import requests # Keep requests for potential fallback or other uses
from dotenv import load_dotenv
import google.generativeai as genai
from urllib.parse import urlparse
from bs4 import BeautifulSoup # Useful for potential pre/post-processing

# --- Selenium Imports ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions # Import Options

# --- Configuration ---
# Load environment variables from a .env file
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY") # Reads GEMINI_API_KEY from .env file

# !!! IMPORTANT: Replace this with the actual target URL !!!
TARGET_URL = "https://www.pentagram.com/arts-culture" # <--- PASTE TARGET URL HERE

# --- Validate Configuration ---
if not API_KEY:
    # Instructions if API key is missing
    print("Error: Gemini API Key not found.")
    print("Please create a file named '.env' in the same directory as this script")
    print("and add the following line to it, replacing YOUR_API_KEY_HERE:")
    print("GEMINI_API_KEY=YOUR_API_KEY_HERE")
    exit() # Exit if no API key is found

if not TARGET_URL or TARGET_URL == "https://website-with-load-more.com/work":
     print("Warning: TARGET_URL is set to the example URL.")
     print("Please update the TARGET_URL variable in the script with the actual website you want to scrape.")
     # Consider exiting if the URL isn't set: exit()

# --- Gemini Configuration ---
try:
    genai.configure(api_key=API_KEY)

    generation_config = {
      "temperature": 0.2, # Lower temperature for more deterministic JSON
      "top_p": 1,
      "top_k": 1,
      "max_output_tokens": 8192, # Adjust based on model and expected output size
      "response_mime_type": "application/json", # Request JSON output directly
    }

    safety_settings = [
      {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
      {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
      {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
      {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]

    # Initialize the Gemini Model
    model = genai.GenerativeModel(model_name="gemini-1.5-flash", # Or gemini-1.5-pro, etc.
                                  generation_config=generation_config,
                                  safety_settings=safety_settings)
    print("Gemini model initialized successfully.")

except Exception as e:
    print(f"Error initializing Gemini model: {e}")
    model = None # Ensure model variable exists even on failure

# --- Helper Functions ---

def get_domain(url):
    """Extracts the domain name (e.g., pentagram.com) from a URL."""
    try:
        parsed_uri = urlparse(url)
        # Handle cases like 'www.example.com' and 'example.com'
        domain = parsed_uri.netloc.replace('www.', '')
        return domain
    except Exception as e:
        print(f"Error parsing domain from URL '{url}': {e}")
        return None

# --- Updated Prompt Function ---
def construct_gemini_prompt_for_cards(filtered_html_content, source_domain):
    """
    Creates the prompt for the Gemini API, specifically mentioning that the
    HTML contains pre-filtered project card elements.

    Args:
        filtered_html_content (str): The concatenated HTML of project card elements.
        source_domain (str): The domain name of the source website.

    Returns:
        str: The formatted prompt string.
    """
    # Truncate if still too long (less likely with filtered content, but good practice)
    max_html_length = 150000 # Keep a generous limit
    if len(filtered_html_content) > max_html_length:
        print(f"Warning: Filtered HTML content was long ({len(filtered_html_content)} chars). Truncated to {max_html_length} characters.")
        filtered_html_content = filtered_html_content[:max_html_length] + "\n... [HTML truncated]"

    # The core instructions for Gemini, adapted for filtered input
    instructions = f"""
You are an expert website scraper specializing in creative agency portfolio websites.
The HTML content provided below consists *only* of the relevant project card elements extracted from the page. Your task is to meticulously extract project details from **each** of these card elements.

**Source Domain:** {source_domain}

**Instructions:**
1.  Carefully analyze the following HTML content, which contains individual project card snippets.
2.  For **each distinct project card snippet** provided, extract the following information:
    * `title`: The main title or name of the project found within the card. Be precise.
    * `url`: The **full, absolute URL** linking directly to the project's detail page or case study, found within the card. If the link in the HTML is relative (e.g., '/work/project-x'), you MUST prepend it with 'https://{source_domain}' to make it absolute. If no specific project URL is found within the card, omit this field.
    * `image`: The **full, absolute URL** of a relevant thumbnail, preview image, or video poster image associated with the project, found within the card. Resolve relative image URLs using 'https://{source_domain}'. If no image is clearly associated within the card, omit this field.
    * `source`: The source domain, which is always '{source_domain}'. Include this field for every project.
    * `category`: If available, extract the category, discipline, or service type associated with the project (e.g., Branding, Web Design, Architecture) found within or near the card's text. If no category is clearly present for a specific project card, omit this field for that project.
3.  Format the entire output strictly as a single JSON array `[...]`. Each element in the array should be a JSON object `{...}` representing one project extracted from one card.
4.  **Crucially:** Ensure all extracted URLs (`url`, `image`) are absolute (start with 'http://' or 'https://').
5.  **Output Requirements:** Your response MUST contain ONLY the JSON array. Do not include any introductory text, explanations, apologies, or markdown formatting like ```json before or after the array. Just the raw `[` character to the final `]` character. Omit fields if their value is null, empty, or not found (except for the mandatory `source` field).

**Example JSON Object Structure within the Array:**
{{
  "title": "Example Project Title",
  "url": "https://{source_domain}/path/to/project",
  "image": "https://{source_domain}/images/preview.jpg",
  "source": "{source_domain}",
  "category": "Example Category"
}}

**Filtered HTML Content (Project Cards) to Analyze:**
```html
{filtered_html_content}
```

**Required Output Format:** A raw JSON array `[...]` containing the extracted project objects.
"""
    return instructions


# --- Updated Scraping Function ---
def scrape_with_load_more(url, max_clicks=10, wait_time=5):
    """
    Uses Selenium to handle 'Load More' (using data-behavior), extracts
    project card HTML (using data-behavior), and sends filtered HTML to Gemini.

    Args:
        url (str): The URL of the page to scrape.
        max_clicks (int): Maximum number of times to click 'Load More'.
        wait_time (int): Seconds to wait after each click for content to load.

    Returns:
        list or dict: A list of dictionaries containing scraped project data,
                      or a dictionary with an 'error' key on failure.
                      Returns None if the Gemini model isn't initialized.
    """
    if not model:
         print("Error: Gemini model is not initialized. Cannot proceed.")
         return None

    source_domain = get_domain(url)
    if not source_domain:
        print(f"Error: Could not parse domain from URL: {url}")
        return {"error": f"Could not parse domain from URL: {url}"}

    print(f"Attempting to scrape: {url}")
    print(f"Source Domain: {source_domain}")
    print(f"Max 'Load More' clicks: {max_clicks}, Wait time per click: {wait_time}s")

    driver = None
    filtered_html_content = "" # Initialize string to hold filtered HTML

    try:
        # --- Selenium Setup (same as before) ---
        print("Setting up Selenium options for headless Chrome...")
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36')

        print("Initializing Headless Chrome Driver...")
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as driver_init_err:
             print(f"Initial driver setup failed: {driver_init_err}")
             print("Attempting with explicit service path /usr/local/bin/chromedriver...")
             try:
                 service = ChromeService(executable_path='/usr/local/bin/chromedriver')
                 driver = webdriver.Chrome(service=service, options=options)
             except Exception as service_err:
                  print(f"Driver setup with explicit path also failed: {service_err}")
                  return {"error": "Failed to initialize Selenium WebDriver."}
        print("WebDriver initialized successfully.")

        # --- Navigation ---
        print(f"Navigating to {url}...")
        driver.get(url)
        print("Navigation complete. Waiting briefly...")
        time.sleep(3)

        # --- Handle "Load More" using specific data-behavior ---
        print("Starting 'Load More' button click loop using data-behavior='homeLoadMore'...")
        clicks = 0
        while clicks < max_clicks:
            try:
                # --- Use specific selector for the load more button ---
                # Adjust tag name ('button', 'a', 'div', etc.) if needed
                load_more_selector = (By.XPATH, "//*[@data-behavior='homeLoadMore']")
                # ---

                # Wait for the button to be present and clickable
                load_more_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(load_more_selector)
                )

                print(f"Found 'Load More' button (data-behavior='homeLoadMore', Attempt {clicks + 1}/{max_clicks}). Clicking...")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                time.sleep(0.5)

                # Click the button (try standard click first)
                try:
                    load_more_button.click()
                except ElementClickInterceptedException:
                    print("   Standard click intercepted. Trying JavaScript click...")
                    driver.execute_script("arguments[0].click();", load_more_button)

                clicks += 1
                print(f"   Clicked {clicks} times. Waiting {wait_time}s for new content...")
                time.sleep(wait_time) # Wait for new content to load

            except TimeoutException:
                print("No more 'Load More' buttons found or button timed out (likely all content loaded).")
                break
            except NoSuchElementException:
                 print("No element found with data-behavior='homeLoadMore'. Stopping.")
                 break
            except StaleElementReferenceException:
                 print("   Load more button became stale. Re-finding and retrying click...")
                 time.sleep(1) # Brief pause before retry
                 # No increment on clicks here, just retry finding/clicking
                 continue
            except Exception as e:
                print(f"An unexpected error occurred during clicking: {e}")
                break

        print(f"Finished 'Load More' loop. Total clicks performed: {clicks}.")

        # --- Extract Filtered HTML based on project card data-behavior ---
        print("Extracting HTML for elements with data-behavior='projectCard'...")
        try:
            # --- Use specific selector for project cards ---
            # Adjust tag name ('div', 'article', 'li', etc.) if needed
            project_card_selector = (By.XPATH, "//*[@data-behavior='projectCard']")
            # ---
            project_card_elements = driver.find_elements(*project_card_selector) # Use * to unpack tuple

            if not project_card_elements:
                print("Warning: No elements found with data-behavior='projectCard'.")
                # Attempt to get full page source as fallback? Or return error?
                # For now, proceed with empty filtered HTML, Gemini might handle it gracefully or fail.
                # Alternatively, could grab body HTML: driver.find_element(By.TAG_NAME, 'body').get_attribute('outerHTML')
                final_page_source = driver.page_source # Get full source as fallback
                print("Falling back to sending full page source as no project cards were identified.")
                # We need to call the original prompt function if using full source
                prompt = construct_gemini_prompt(final_page_source, source_domain) # Fallback prompt

            else:
                print(f"Found {len(project_card_elements)} elements with data-behavior='projectCard'. Extracting outerHTML...")
                html_parts = []
                for element in project_card_elements:
                    try:
                        # Get the HTML content of each project card element
                        html_parts.append(element.get_attribute('outerHTML'))
                    except StaleElementReferenceException:
                        print("   Warning: A projectCard element became stale during extraction. Skipping it.")
                        continue # Skip this stale element

                filtered_html_content = "\n".join(html_parts) # Join the HTML snippets
                print(f"Extracted filtered HTML content (length: {len(filtered_html_content)} characters).")
                 # *** Use the specific prompt function for filtered HTML ***
                prompt = construct_gemini_prompt_for_cards(filtered_html_content, source_domain)


        except Exception as extract_err:
            print(f"Error extracting project card HTML: {extract_err}")
            return {"error": f"Failed to extract project card HTML: {extract_err}"}

    except Exception as selenium_err:
        print(f"An error occurred during Selenium automation: {selenium_err}")
        return {"error": f"Selenium automation failed: {selenium_err}"}
    finally:
        if driver:
            print("Closing Selenium WebDriver...")
            driver.quit()
            print("WebDriver closed.")

    # --- Call Gemini ---
    # Check if we have a prompt (either from filtered HTML or fallback) and the model
    if 'prompt' in locals() and prompt and model:
        print("Constructing/Sending prompt to Gemini API...")
        try:
            print("Sending request to Gemini API... (This may take a moment)")
            start_gemini_time = time.time()
            gemini_response = model.generate_content(prompt) # Send the constructed prompt
            end_gemini_time = time.time()
            print(f"Gemini API response received in {end_gemini_time - start_gemini_time:.2f} seconds.")

            raw_json_text = gemini_response.text
            cleaned_json_text = raw_json_text.strip()
            if cleaned_json_text.startswith("```json"):
                 cleaned_json_text = cleaned_json_text[7:]
            if cleaned_json_text.endswith("```"):
                 cleaned_json_text = cleaned_json_text[:-3]
            cleaned_json_text = cleaned_json_text.strip()

            print("Parsing JSON response from Gemini...")
            scraped_data = json.loads(cleaned_json_text)

            if not isinstance(scraped_data, list):
                print("Warning: Gemini response was valid JSON but not the expected array format.")
                return {"error": "Gemini did not return the expected JSON array format.", "response": scraped_data}

            print(f"Successfully parsed JSON. Found {len(scraped_data)} potential projects.")
            return scraped_data

        except json.JSONDecodeError as json_err:
            print(f"Error decoding JSON from Gemini response: {json_err}")
            print("--- Gemini Raw Response (first 1000 chars) ---")
            print(raw_json_text[:1000] + ("..." if len(raw_json_text) > 1000 else ""))
            print("--- End Gemini Raw Response ---")
            return {"error": "Failed to parse JSON response from AI.", "raw_response_preview": raw_json_text[:1000]}
        except Exception as e:
            print(f"Error calling Gemini API or processing its response: {e}")
            try:
                error_details = getattr(gemini_response, 'prompt_feedback', None)
                if error_details:
                     print(f"Gemini Prompt Feedback: {error_details}")
                     return {"error": f"Gemini API error: {e}", "feedback": str(error_details)}
            except Exception:
                 pass
            return {"error": f"An error occurred communicating with the AI: {e}"}
    elif not model:
         return {"error": "Gemini model was not initialized."}
    else:
         # This case means we failed to get HTML or construct a prompt
         return {"error": "Failed to get HTML content or construct prompt before calling Gemini."}


# --- Main Execution Block ---
if __name__ == "__main__":
    print("Script starting...")
    if not TARGET_URL or not TARGET_URL.startswith(('http://', 'https://')):
        print(f"Error: Invalid TARGET_URL configured: {TARGET_URL}")
    elif not model:
         print("Cannot run scraping because the Gemini model failed to initialize.")
    else:
        start_time = time.time()
        result = scrape_with_load_more(TARGET_URL, max_clicks=15, wait_time=5) # Increased max_clicks slightly
        end_time = time.time()

        print("\n--- Scraping Result ---")
        output_filename = "scraped_projects.json" # Define output filename

        if result is None:
             print("Scraping function did not run due to initialization errors.")
        elif isinstance(result, dict) and 'error' in result:
             print("Scraping failed:")
             print(json.dumps(result, indent=2))
             # Optionally write error to file
             # with open(output_filename, 'w') as f:
             #     json.dump(result, f, indent=2)
             # print(f"Error details saved to {output_filename}")
        elif isinstance(result, list):
             print(f"Successfully scraped {len(result)} projects.")
             # Save the successful result to a JSON file
             try:
                 with open(output_filename, 'w', encoding='utf-8') as f:
                     json.dump(result, f, indent=2, ensure_ascii=False)
                 print(f"Scraped data successfully saved to '{output_filename}'")
             except Exception as write_err:
                 print(f"Error writing results to JSON file: {write_err}")
                 print("Printing results to console instead:")
                 print(json.dumps(result, indent=2)) # Print to console as fallback
        else:
             print("Scraping function returned an unexpected result type.")
             print(result)

        print(f"\nTotal execution time: {end_time - start_time:.2f} seconds")
    print("Script finished.")
