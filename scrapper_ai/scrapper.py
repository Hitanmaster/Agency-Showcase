# scrape_dynamic_cloudshell.py

import os
import json
import time
# ... other imports (requests, dotenv, genai, urlparse, BeautifulSoup) ...
from dotenv import load_dotenv
import google.generativeai as genai
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions # Import Options


# --- Configuration ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY") # Make sure you have a .env file or set this
TARGET_URL = "https://www.pentagram.com/arts-culture" # <--- PASTE TARGET URL HERE

if not API_KEY:
    raise ValueError("Gemini API Key not found. Please set the GEMINI_API_KEY environment variable or create a .env file.")
if not TARGET_URL or TARGET_URL == "https://website-with-load-more.com/work":
     print("Warning: TARGET_URL is set to the example. Please update it.")

# --- Gemini Configuration (same as before) ---
genai.configure(api_key=API_KEY)
# ... (generation_config, safety_settings, model initialization) ...
try:
    model = genai.GenerativeModel(model_name="gemini-1.5-flash", # Or your preferred model
                                  generation_config={ "temperature": 0.2, "top_p": 1, "top_k": 1, "max_output_tokens": 8192, "response_mime_type": "application/json"},
                                  safety_settings=[{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, # etc...
                                                   ])
except Exception as e:
    print(f"Error initializing Gemini model: {e}")
    model = None

# --- Helper Functions (get_domain, construct_gemini_prompt - same as before) ---
def get_domain(url):
    # ... (implementation) ...
    try:
        parsed_uri = urlparse(url)
        domain = '{uri.netloc}'.format(uri=parsed_uri)
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception:
        return None

def construct_gemini_prompt(html_content, source_domain):
    # ... (implementation - same as before) ...
    max_html_length = 100000
    if len(html_content) > max_html_length:
        print(f"Warning: HTML content truncated to {max_html_length} characters for Gemini.")
        html_content = html_content[:max_html_length] + "\n... [HTML truncated]"

    instructions = f""" You are a smart website scraper. Given an HTML page from a creative agency website (like Pentagram, Koto Studio, etc.), extract all project listings shown on the page.

Each project should contain:
- title
- url (full link)
- image or video link (prefer thumbnail or preview)
- source domain (e.g., pentagram.com)
- category if available (e.g., design, architecture, etc.)

Return a JSON array like this:
[
  {
    "title": "Project Title",
    "url": "https://agency.com/project-url",
    "image": "https://agency.com/images/preview.jpg",
    "source": "agency.com",
    "category": "Design"
  },
  ...
]

Do not include null or empty values unless necessary. Assume the HTML or structured content will be provided.
"""
{html_content}