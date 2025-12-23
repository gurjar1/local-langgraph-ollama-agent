"""Enhanced web search with full page content extraction and browser-use integration.

Primary: SearXNG API (Docker container on localhost:8888)
Enhancement: Fetch full page content from top URLs
Fallback: browser-use when HTTP fails
Deep Research Mode: Force browser-use for thorough content extraction
"""

import os
import asyncio
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup


# Configuration
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8888")
MAX_CONTENT_LENGTH = 8000  # Increased from 4000 to 8000 chars per page
FETCH_TIMEOUT = 20  # seconds


def fetch_page_content(url: str, timeout: int = FETCH_TIMEOUT) -> Optional[str]:
    """
    Fetch and extract readable text content from a URL using HTTP.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
    
    Returns:
        Extracted text content or None if failed
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        
        if response.status_code != 200:
            return None
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'button', 'iframe']):
            element.decompose()
        
        # Try to find main content area
        main_content = (
            soup.find('main') or 
            soup.find('article') or 
            soup.find('div', class_=['content', 'main-content', 'post-content', 'entry-content', 'article-body']) or
            soup.find('div', id=['content', 'main', 'article', 'post'])
        )
        
        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
        else:
            body = soup.find('body')
            text = body.get_text(separator='\n', strip=True) if body else ""
        
        # Clean up
        lines = [line.strip() for line in text.split('\n') if line.strip() and len(line.strip()) > 20]
        text = '\n'.join(lines)
        
        # Truncate
        if len(text) > MAX_CONTENT_LENGTH:
            text = text[:MAX_CONTENT_LENGTH] + "\n... [content truncated]"
        
        return text if len(text) > 100 else None
        
    except Exception as e:
        print(f"[HTTP Fetch] Error {url[:40]}: {str(e)[:40]}")
        return None


def fetch_multiple_pages(urls: List[str], max_pages: int = 3) -> Dict[str, str]:
    """Fetch content from multiple URLs in parallel."""
    results = {}
    urls_to_fetch = urls[:max_pages]
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_url = {executor.submit(fetch_page_content, url): url for url in urls_to_fetch}
        
        for future in as_completed(future_to_url, timeout=45):
            url = future_to_url[future]
            try:
                content = future.result()
                if content:
                    results[url] = content
                    print(f"[HTTP Fetch] Got {len(content)} chars from {url[:50]}...")
            except Exception as e:
                print(f"[HTTP Fetch] Failed: {url[:40]}")
    
    return results


async def fetch_with_browser_use(url: str, model: str = "llama3.1") -> Optional[str]:
    """
    Fetch page content using browser-use for JS-heavy pages.
    
    Args:
        url: URL to fetch
        model: Ollama model for browser control
    
    Returns:
        Extracted content or None
    """
    try:
        from browser_use import Agent, Browser
        from langchain_ollama import ChatOllama
        
        print(f"[browser-use] Fetching content from: {url[:50]}...")
        
        browser = Browser(headless=True)
        llm = ChatOllama(
            model=model,
            temperature=0,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        
        task = f"""
        Go to this URL: {url}
        
        Extract the main content of the page - the article text, not navigation or ads.
        Return ONLY the main text content, up to 8000 characters.
        """
        
        agent = Agent(task=task, llm=llm, browser=browser)
        history = await agent.run(max_steps=10)
        
        result = history.final_result() if history else None
        await browser.close()
        
        if result:
            print(f"[browser-use] Got {len(str(result))} chars")
            return str(result)[:MAX_CONTENT_LENGTH]
        return None
        
    except Exception as e:
        print(f"[browser-use] Error: {str(e)[:50]}")
        return None


def fetch_with_browser_use_sync(url: str, model: str = "llama3.1") -> Optional[str]:
    """Synchronous wrapper for browser-use fetch."""
    try:
        return asyncio.run(fetch_with_browser_use(url, model))
    except Exception as e:
        print(f"[browser-use] Sync error: {str(e)[:50]}")
        return None


def search_searxng(query: str, max_results: int = 5) -> Optional[List[Dict[str, str]]]:
    """Search using local SearXNG instance."""
    try:
        response = requests.get(
            f"{SEARXNG_URL}/search",
            params={"q": query, "format": "json", "categories": "general"},
            headers={
                "X-Forwarded-For": "127.0.0.1",
                "X-Real-IP": "127.0.0.1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"[SearXNG] Error: Status {response.status_code}")
            return None
        
        data = response.json()
        results = []
        
        for item in data.get("results", [])[:max_results]:
            results.append({
                "title": item.get("title", "No title")[:200],
                "url": item.get("url", ""),
                "snippet": item.get("content", "")[:500]
            })
        
        print(f"[SearXNG] Found {len(results)} results for: {query[:50]}...")
        return results
        
    except requests.exceptions.ConnectionError:
        print("[SearXNG] Connection failed - is Docker container running?")
        return None
    except Exception as e:
        print(f"[SearXNG] Error: {e}")
        return None


def search_ddg_fallback(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Fallback search using DuckDuckGo library."""
    try:
        from duckduckgo_search import DDGS
        
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [{
                "title": r.get("title", "")[:200],
                "url": r.get("href", ""),
                "snippet": r.get("body", "")[:500]
            } for r in results]
    except Exception as e:
        print(f"[DDG Fallback] Error: {e}")
        return [{"title": "Search unavailable", "url": "", "snippet": f"Error: {str(e)}"}]


def search_google(
    query: str, 
    max_results: int = 5, 
    headless: bool = True,
    deep_research: bool = False,
    model: str = "llama3.1"
) -> List[Dict[str, str]]:
    """
    Enhanced search with full page content extraction.
    
    Args:
        query: Search query
        max_results: Maximum search results
        headless: Ignored (compatibility)
        deep_research: If True, fetch more pages with longer content
        model: Ignored (browser-use disabled due to async issues)
    
    Returns:
        List of search results with full content
    """
    # Step 1: Get search results
    results = search_searxng(query, max_results)
    
    if not results or len(results) == 0:
        print("[Search] SearXNG unavailable, trying DuckDuckGo...")
        results = search_ddg_fallback(query, max_results)
    
    if not results:
        return [{"title": "No results", "url": "", "snippet": "Search returned no results."}]
    
    # Step 2: Fetch full content via HTTP (browser-use disabled due to LangGraph async issues)
    urls = [r['url'] for r in results if r.get('url')]
    
    # Deep research = fetch more pages
    max_pages = 5 if deep_research else 3
    mode = "DEEP" if deep_research else "Standard"
    print(f"[{mode}] Fetching content from top {max_pages} URLs...")
    
    page_contents = fetch_multiple_pages(urls, max_pages=max_pages)
    
    # Enhance results with full content
    for result in results:
        url = result.get('url', '')
        if url in page_contents:
            result['full_content'] = page_contents[url]
            result['snippet'] = page_contents[url][:500]
    
    return results


# For backwards compatibility
def deep_research_with_browser(task: str, model: str = "llama3.1") -> str:
    """Legacy function - use search_google with deep_research=True instead."""
    return asyncio.run(fetch_with_browser_use(task, model)) or "No result"


# Quick test
if __name__ == "__main__":
    print("Testing enhanced search with 8000 char limit...")
    results = search_google("latest AI news December 2024", max_results=3, deep_research=False)
    print(f"\nFound {len(results)} results:")
    for i, r in enumerate(results):
        print(f"\n{i+1}. {r['title']}")
        content = r.get('full_content', r.get('snippet', ''))
        print(f"   Content length: {len(content)} chars")
        print(f"   Preview: {content[:150]}...")
