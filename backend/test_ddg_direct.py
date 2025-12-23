# Simple test to verify the duckduckgo_search import and usage
try:
    from duckduckgo_search import DDGS
    print("Import SUCCESS: from duckduckgo_search import DDGS")
    
    ddg = DDGS()
    results = ddg.text("test query", max_results=2)
    print(f"Search SUCCESS: Got {len(results)} results")
    for r in results:
        print(f"  - {r.get('title', 'No title')}")
except Exception as e:
    print(f"FAILED: {e}")
