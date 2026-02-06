import trafilatura
from langchain_core.tools import tool
import requests
from bs4 import BeautifulSoup
import time

def robust_scrape(url: str) -> str:
    """
    Scrapes a URL using a 3-layer fallback strategy:
    1. Trafilatura (Fast, best for articles)
    2. BeautifulSoup (Static HTML fallback)
    3. Playwright (Dynamic JS fallback)
    """
    
    # Common Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # 1. Trafilatura
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        text = trafilatura.extract(response.text)
        if text and len(text) > 200:
            return text
    except:
        pass # Fallthrough

    # 2. BeautifulSoup (Static)
    try:
        if 'response' in locals() and response.ok:
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style", "nav", "footer"]):
                script.extract()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            if len(text) > 300:
                return text + "\n(Extracted via Static BS4)"
    except:
        pass

    # 3. Playwright (Dynamic)
    try:
        print(f"Switching to Playwright for {url}...")
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=headers["User-Agent"])
            page.goto(url, timeout=45000)
            
            # Wait for content to stabilize
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except:
                pass # Continue even if timeout, page might be mostly loaded
            
            # Try Trafilatura on rendered HTML first
            content = page.content()
            text = trafilatura.extract(content)
            if text and len(text) > 200:
                browser.close()
                return text + "\n(Extracted via Playwright)"
            
            # If still nothing, brute force text from body
            el = page.query_selector("body")
            if el:
                text = el.inner_text()
                browser.close()
                return text + "\n(Extracted via Playwright Raw)"
            
            browser.close()
    except Exception as e:
        return f"All scrape methods failed. Playwright error: {str(e)}"
    
    return "Failed to extract text from URL."

@tool
def scrape_webpage(url: str) -> str:
    """Scrapes the content of a specific webpage URL. Handles dynamic JS sites."""
    return robust_scrape(url)
