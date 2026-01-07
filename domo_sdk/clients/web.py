"""
Web scraping utilities client for Domo SDK.
"""
from typing import Union, List, Optional
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Web:
    """Web scraping utilities client."""
    
    def scrape(self, url: str, selector: str = None, timeout: int = 10, 
               user_agent: str = None) -> Union[str, List[str], None]:
        """
        Scrape text content from webpage using CSS selectors.
        
        Args:
            url: URL to scrape
            selector: CSS selector for specific elements (optional)
            timeout: Request timeout in seconds
            user_agent: Custom User-Agent string (optional)
            
        Returns:
            Scraped text content or list of texts
        """
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        try:
            # Allow configurable User-Agent
            default_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            headers = {'User-Agent': user_agent or default_ua}
            
            response = requests.get(url, headers=headers, timeout=timeout, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if selector is None:
                return soup.get_text(strip=True)
            
            elements = soup.select(selector)
            if not elements:
                return None
            
            texts = [elem.get_text(strip=True) for elem in elements]
            return texts[0] if len(texts) == 1 else texts
            
        except Exception as e:
            print(f"Scraping error: {str(e)}")
            return None