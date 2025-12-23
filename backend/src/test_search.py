# Test the browser search
from agent.browser_search import search_google

print("Testing search...")
results = search_google("latest AI news December 2024", max_results=3)
print(f"Found {len(results)} results:")
for i, r in enumerate(results):
    print(f"\n{i+1}. {r['title']}")
    print(f"   URL: {r['url'][:60]}..." if len(r['url']) > 60 else f"   URL: {r['url']}")
    print(f"   Snippet: {r['snippet'][:80]}..." if len(r['snippet']) > 80 else f"   Snippet: {r['snippet']}")
