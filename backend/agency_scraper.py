import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse, urljoin
import os
import sys
import re # For potentially extracting video IDs
import time # For potential delays if needed

# --- Configuration ---
# Ensure these lists are defined at the top level (global scope)
PROJECT_CARD_SELECTORS = [
    '.project-item',        # Generic item class (Used by Koto)
    '.work-card',           # Common card class
    '.portfolio-item',      # Another common item class
    'article.project',      # Article elements often used
    'li.project',           # List items
    'div.work-item',        # Div based item
    '.card',                # Generic card
    'article[class*="post"]', # Articles with 'post' in class (common in blogs/CMS)
    'li[class*="item"]'     # List items with 'item' in class
]

# Selectors to try for finding the main link within/around a project card
LINK_SELECTORS = [
    'a',                    # Direct link wrapping the card (or first link inside)
    '.project-link a',      # Specific link class
    '.card-link a',
    'h2 a',                 # Link within the main heading
    'h3 a',
    '.title a'
]

# Selectors to try for finding the title within a project card
TITLE_SELECTORS = [
    '.project-title',       # Specific title class
    '.card-title',
    'h2',                   # Common heading tags (Used by Koto)
    'h3',
    'h4',
    '.title',
    '.heading'
]

# Selectors/Attributes to try for finding image/video within a project card
MEDIA_SELECTORS = {
    "image": [
        'img.work-background--image[src]', # Koto specific image class
        'img[src]',                 # Standard image tag
        'div[data-bg-src]',         # Div with background image data attribute
        'img[data-src]'             # Lazy loaded images
    ],
    "video_attr": [
        # Prioritize Koto's specific attribute first in extract_video_url logic
        # '[data-work-page-thumbnail-video]', # Handled separately below
        '[data-video-src]',         # Common data attribute for video URL
        '[data-video-id]',          # Common data attribute for video ID (Vimeo/YT)
        '[data-vimeo-id]',
        '[data-youtube-id]',
        '[data-vimeo-url]',
        '[data-video]'              # Generic video data attribute (Used by Koto for Vimeo ID)
    ],
    "video_tag": [
        'iframe[src*="vimeo"]',     # Vimeo iframe (check src attribute)
        'iframe[src*="youtube"]',   # YouTube iframe (check src attribute)
        'iframe[src*="player.vimeo"]',
        'video[src]',               # HTML5 video tag source
    ]
}

OUTPUT_DIR = "data"
# --- End Configuration ---

def clean_text(text):
    """Removes extra whitespace and newlines from text."""
    return ' '.join(text.split()).strip() if text else None

def make_absolute_url(base_url, url):
    """Converts a relative URL to an absolute URL."""
    if not url or url.startswith(('http://', 'https://', '//')):
        if url and url.startswith('//'):
            # Handle protocol-relative URLs
            parsed_base = urlparse(base_url)
            return f"{parsed_base.scheme}:{url}"
        return url # Already absolute or empty
    try:
        # Ensure the base_url ends with a '/' if it refers to a directory-like structure
        parsed_base = urlparse(base_url)
        if '.' not in parsed_base.path.split('/')[-1] and not base_url.endswith('/'):
             base_url += '/'
        return urljoin(base_url, url)
    except ValueError:
        print(f"Warning: Could not make URL absolute: base='{base_url}', url='{url}'")
        return None


def extract_video_url(element, base_url):
    """
    Tries to extract a video URL from various attributes or tags,
    prioritizing Koto's specific data attribute.
    """
    # --- Koto Specific Check ---
    # Find the main link element associated with the card
    main_link_element = None
    if element.name == 'a': # If the card element itself is the link
         main_link_element = element
    else: # Otherwise look for the primary link inside
         main_link_element = element.select_one('a')

    # Check Koto's specific attribute on the main link first
    if main_link_element and main_link_element.has_attr('data-work-page-thumbnail-video'):
        koto_video_url = main_link_element['data-work-page-thumbnail-video']
        if koto_video_url and ('vimeo.com' in koto_video_url or 'youtube.com' in koto_video_url):
            # print(f"  [Debug] Found video via data-work-page-thumbnail-video: {koto_video_url}")
            return make_absolute_url(base_url, koto_video_url)
    # --- End Koto Specific Check ---


    # --- Generic Checks (Fallback) ---
    # Try common data attributes within the card element
    for attr_selector in MEDIA_SELECTORS["video_attr"]:
        target_element = element.select_one(attr_selector)
        if target_element:
            attr_name = attr_selector.strip('[]').split('=')[0]
            if target_element.has_attr(attr_name):
                value = target_element[attr_name]
                if not value: continue

                if 'vimeo.com' in value or 'youtube.com' in value or value.startswith('http'):
                    # print(f"  [Debug] Found video via {attr_name} (URL): {value}")
                    return make_absolute_url(base_url, value)

                if ('vimeo-id' in attr_name or attr_name == 'data-video') and value.isdigit():
                    # print(f"  [Debug] Found video via {attr_name} (Vimeo ID): {value}")
                    return f"https://vimeo.com/{value}"
                if 'youtube-id' in attr_name:
                    # print(f"  [Debug] Found video via {attr_name} (YouTube ID): {value}")
                    return f"https://www.youtube.com/watch?v={value}" # Standard YT URL
                if attr_name == 'data-video-src':
                    # print(f"  [Debug] Found video via {attr_name} (Relative Path): {value}")
                    return make_absolute_url(base_url, value)

    # Try video tags or iframes within the card
    for tag_selector in MEDIA_SELECTORS["video_tag"]:
        video_tag = element.select_one(tag_selector)
        if video_tag and video_tag.has_attr('src'):
             src = video_tag['src']
             if src and ('vimeo.com' in src or 'youtube.com' in src):
                 # print(f"  [Debug] Found video via {tag_selector} src: {src}")
                 # Extract base URL if needed (e.g., from player.vimeo.com/video/ID?params)
                 if 'player.vimeo.com/video/' in src:
                      match = re.search(r'player\.vimeo\.com/video/(\d+)', src)
                      if match:
                           return f"https://vimeo.com/{match.group(1)}"
                 elif 'youtube.com/embed/' in src:
                      match = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]+)', src)
                      if match:
                            return f"https://www.youtube.com/watch?v={match.group(1)}"
                 # Otherwise, return the src directly if it looks like a valid video URL
                 return make_absolute_url(base_url, src)

    # Fallback: Check link href directly for vimeo (less likely for Koto based on HTML)
    if main_link_element and main_link_element.has_attr('href'):
        href = main_link_element['href']
        if 'vimeo.com/' in href:
             match = re.search(r'vimeo\.com/(\d+)', href)
             if match:
                 # print(f"  [Debug] Found video via link href (Vimeo ID): {match.group(1)}")
                 return f"https://vimeo.com/{match.group(1)}"

    # print("  [Debug] No video URL found.")
    return None


def extract_image_url(element, base_url):
    """Tries to extract an image URL from various attributes or tags."""
    for selector in MEDIA_SELECTORS["image"]:
        tag_name = selector.split('[')[0] # e.g., 'img', 'div'
        attr_match = re.search(r'\[(.*?)(?:=.*)?\]', selector) # e.g., 'src', 'data-bg-src'
        attr_name = attr_match.group(1) if attr_match else 'src' # Default to src if no attribute specified

        # Search within the current card element only
        img_tag = element.select_one(selector)
        if img_tag and img_tag.has_attr(attr_name):
            src = img_tag[attr_name]
            if src: # Ensure src is not empty
                 # print(f"  [Debug] Found image via {selector}: {src}")
                 return make_absolute_url(base_url, src)

        # Check style attribute for background-image on the matched tag or the card itself
        target_style_tag = img_tag if img_tag else element # Check the found tag or the card element
        if target_style_tag:
             style = target_style_tag.get('style')
             if style:
                 # More robust regex for background-image url
                 match = re.search(r'background-image:\s*url\((["\']?)(.*?)\1\)', style)
                 if match:
                     bg_url = match.group(2) # Get the URL part
                     if bg_url: # Ensure extracted url is not empty
                         # print(f"  [Debug] Found image via background-image style: {bg_url}")
                         return make_absolute_url(base_url, bg_url)

    # print("  [Debug] No image URL found.")
    return None


def scrape_agency_portfolio(url):
    """
    Fetches and parses an agency portfolio page to extract project details.
    Handles potential 403 errors by using more headers or cloudscraper.

    Args:
        url (str): The URL of the agency's work/portfolio page.

    Returns:
        list: A list of dictionaries, each containing project info,
              or None if an error occurs.
    """
    print(f"Fetching URL: {url}")
    response = None # Initialize response to None
    session = None # Initialize session to None
    scraper = None # Initialize scraper to None

    try:
        # --- Option 1: Enhanced Headers (Try this first) ---
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Sec-Ch-Ua': '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
        session = requests.Session()
        session.headers.update(headers)
        response = session.get(url, timeout=30)
        response.raise_for_status()
        print("Successfully fetched with enhanced headers.")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL with enhanced headers: {e}")
        # --- Option 2: Try Cloudscraper ---
        print("Trying fetch with cloudscraper...")
        try:
            import cloudscraper
            # Use the class directly
            scraper = cloudscraper.CloudScraper()
            # Cloudscraper handles headers/challenges automatically
            response = scraper.get(url, timeout=45)
            response.raise_for_status()
            print("Successfully fetched with cloudscraper.")
        except ImportError:
             print("Cloudscraper library not found. Cannot attempt bypass.")
             print("Install it using: pip install cloudscraper")
             return None
        except requests.exceptions.RequestException as e_cf:
             print(f"Error fetching URL even with cloudscraper: {e_cf}")
             return None
        except Exception as e_cf_other:
             print(f"An unexpected error occurred during cloudscraper fetch: {e_cf_other}")
             return None

    except Exception as e:
         print(f"An unexpected error occurred during initial fetch attempt: {e}")
         return None

    # Ensure we actually got a response
    if response is None:
         print("Failed to get a valid response from the server.")
         return None

    # --- Parsing logic starts here ---
    print("Parsing HTML content...")
    try:
        # Explicitly use the encoding detected by requests/cloudscraper
        effective_encoding = response.encoding if response.encoding else response.apparent_encoding
        soup = BeautifulSoup(response.content, 'html.parser', from_encoding=effective_encoding)
    except Exception as parse_e:
        print(f"Error parsing HTML: {parse_e}")
        return None

    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    agency_domain = urlparse(url).netloc.replace('www.', '')

    projects_data = []
    project_cards = []

    # Try different selectors to find the project cards
    for selector in PROJECT_CARD_SELECTORS:
        try:
            project_cards = soup.select(selector)
            if project_cards:
                print(f"Found {len(project_cards)} potential project cards using selector: '{selector}'")
                break
        except Exception as select_e:
            print(f"Error using selector '{selector}': {select_e}")
            continue # Try next selector
    else: # No break occurred
        print("Could not find project cards using known selectors. Please inspect the page HTML and update PROJECT_CARD_SELECTORS.")
        if response and ("cloudflare" in response.text.lower() or "checking your browser" in response.text.lower()):
             print("Hint: The fetched content might be a Cloudflare challenge page, not the actual portfolio.")
        return None # Stop if no cards found


    print(f"Extracting data from {len(project_cards)} cards...")
    for i, card in enumerate(project_cards):
        # print(f"\n--- Processing Card {i+1} ---") # Debugging: print card separator
        # print(card.prettify()[:500]) # Debugging: print start of card HTML
        project_info = {
            "title": None,
            "url": None,
            "image": None,
            "video": None,
            "source": agency_domain
        }

        try:
            # --- Extract URL ---
            project_url = None
            link_element = None
            if card.name == 'a' and card.has_attr('href'):
                 link_element = card
            else:
                for selector in LINK_SELECTORS:
                    link_element = card.select_one(selector)
                    if link_element and link_element.has_attr('href'):
                         break

            if link_element and link_element.has_attr('href'):
                href = link_element['href'].strip()
                if href and href != '#' and not href.startswith(('javascript:', 'mailto:', 'tel:')):
                     project_url = make_absolute_url(url, href)
                     # print(f"  [Debug] Found URL: {project_url}")

            # --- Extract Title ---
            title_text = None
            for selector in TITLE_SELECTORS:
                title_element = card.select_one(selector)
                if title_element:
                    title_text = clean_text(title_element.get_text(strip=True))
                    if title_text:
                        # print(f"  [Debug] Found Title (via {selector}): {title_text}")
                        break

            if not title_text and link_element:
                 link_text = clean_text(link_element.get_text(strip=True))
                 if link_text and len(link_text) > 3 and not link_text.lower().startswith(("view", "see", "learn", "read")):
                     title_text = link_text
                     # print(f"  [Debug] Found Title (via link text): {title_text}")


            # --- Extract Media (Video preferred) ---
            video_url = extract_video_url(card, url)
            image_url = None
            if not video_url: # Only look for image if no video found
                image_url = extract_image_url(card, url)

            # --- Validate and Store ---
            if title_text and project_url:
                project_info["title"] = title_text
                project_info["url"] = project_url
                project_info["video"] = video_url
                project_info["image"] = image_url
                projects_data.append(project_info)
                # print(f"  + Added: {title_text}")
            else:
                # print(f"  - Skipped card: Missing title or URL. Found title='{title_text}', url='{project_url}'")
                pass

        except Exception as extract_e:
            print(f"Error extracting data from card {i+1}: {extract_e}")
            # Optionally print the card HTML that caused the error
            # print(card.prettify())
            continue # Skip to the next card


    print(f"\nSuccessfully extracted data for {len(projects_data)} projects.")
    return projects_data


def save_to_json(data, filename):
    """Saves data to a JSON file."""
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filepath = os.path.join(OUTPUT_DIR, filename)
        print(f"Saving data to {filepath}...")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("Data saved successfully.")
    except IOError as e:
        print(f"Error saving data to JSON file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during save: {e}")


# --- Main Execution ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_url = sys.argv[1]
    else:
        input_url = "https://koto.studio/work/"

    if not input_url.startswith(('http://', 'https://')):
        print("Invalid URL format. Please include http:// or https://")
        sys.exit(1)

    if 'PROJECT_CARD_SELECTORS' not in globals():
         print("Error: Configuration lists (e.g., PROJECT_CARD_SELECTORS) are not defined.")
         sys.exit(1)

    extracted_data = scrape_agency_portfolio(input_url)

    if extracted_data is not None:
        if extracted_data:
            agency_domain = urlparse(input_url).netloc.replace('www.', '')
            json_filename = f"{agency_domain}.json"
            save_to_json(extracted_data, json_filename)
        else:
            print("No valid project data could be extracted from the page.")
    else:
        print("Scraping process failed.")

