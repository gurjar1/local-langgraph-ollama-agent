# Debug script to see DDG HTML structure
import requests

url = "https://html.duckduckgo.com/html/?q=latest+AI+news"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")
print(f"Content length: {len(response.text)}")

# Save to file for inspection
with open("ddg_debug.html", "w", encoding="utf-8") as f:
    f.write(response.text)
print("Saved to ddg_debug.html")

# Try to find result elements
from bs4 import BeautifulSoup
soup = BeautifulSoup(response.text, 'html.parser')

# Check for common result selectors
selectors = ['.result', '.web-result', '.results_links', 'div[data-result]', 'article', '.result__body']
for sel in selectors:
    elements = soup.select(sel)
    print(f"Selector '{sel}': found {len(elements)} elements")

# Print first 500 chars of body for context
body = soup.find('body')
if body:
    print(f"\nBody preview (first 1000 chars):\n{body.get_text()[:1000]}")
