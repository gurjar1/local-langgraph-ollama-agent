"""Web search using SearXNG (self-hosted metasearch engine).

Primary: SearXNG API (Docker container on localhost:8888)
Fallback: DuckDuckGo search library
Optional: browser-use for complex multi-step research tasks
"""

import os
import time
import json
from typing import List, Dict, Optional
import requests


# SearXNG Configuration
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8888")


def search_searxng(query: str, max_results: int = 5) -> Optional[List[Dict[str, str]]]:
    """
    Search using local SearXNG instance.
    
    Args:
        query: Search query
        max_results: Maximum results to return
    
    Returns:
        List of results or None if SearXNG unavailable
    """
    try:
        response = requests.get(
            f"{SEARXNG_URL}/search",
            params={
                "q": query,
                "format": "json",
                "categories": "general",
            },
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
    """
    Fallback search using DuckDuckGo library.
    """
    try:
        from duckduckgo_search import DDGS
        
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
            formatted = []
            for r in results:
                formatted.append({
                    "title": r.get("title", "")[:200],
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")[:500]
                })
            
            print(f"[DDG Fallback] Found {len(formatted)} results")
            return formatted
            
    except Exception as e:
        print(f"[DDG Fallback] Error: {e}")
        return [{
            "title": "Search unavailable",
            "url": "",
            "snippet": f"Both SearXNG and DuckDuckGo failed. Error: {str(e)}"
        }]


def search_google(query: str, max_results: int = 5, headless: bool = True) -> List[Dict[str, str]]:
    """
    Main search function. Tries SearXNG first, falls back to DDG.
    
    Args:
        query: Search query
        max_results: Maximum results
        headless: Ignored (compatibility)
    
    Returns:
        List of search results
    """
    # Try SearXNG first
    results = search_searxng(query, max_results)
    
    if results and len(results) > 0:
        return results
    
    # Fallback to DuckDuckGo
    print("[Search] SearXNG unavailable, trying DuckDuckGo...")
    return search_ddg_fallback(query, max_results)


# ============================================
# OPTIONAL: browser-use for deep research
# ============================================

async def deep_research_with_browser(
    task: str,
    model: str = "llama3.1"
) -> str:
    """
    Use browser-use for complex multi-step research tasks.
    This is for tasks like: "Login to X, find Y, extract Z"
    
    Args:
        task: Natural language description of what to do
        model: Ollama model to use for browser control
    
    Returns:
        Result from the browser-use agent
    """
    try:
        from browser_use import Agent, Browser
        from langchain_ollama import ChatOllama
        
        # Create browser
        browser = Browser(headless=True)
        
        # Create LLM for browser control
        llm = ChatOllama(
            model=model,
            temperature=0,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        
        # Create and run agent
        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
        )
        
        history = await agent.run()
        
        result = history.final_result() if history else "No result"
        await browser.close()
        
        return str(result)
        
    except ImportError:
        return "browser-use not installed. Run: pip install browser-use"
    except Exception as e:
        return f"Browser research error: {str(e)}"


# Quick test
if __name__ == "__main__":
    print("Testing SearXNG search...")
    results = search_google("latest AI news December 2024", max_results=3)
    print(f"\nFound {len(results)} results:")
    for i, r in enumerate(results):
        print(f"\n{i+1}. {r['title']}")
        print(f"   URL: {r['url'][:60]}..." if len(r['url']) > 60 else f"   URL: {r['url']}")
        print(f"   Snippet: {r['snippet'][:80]}..." if len(r['snippet']) > 80 else f"   Snippet: {r['snippet']}")
