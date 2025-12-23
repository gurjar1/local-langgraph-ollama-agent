try:
    import ddgs
    print("Direct import 'import ddgs': SUCCESS")
except ImportError as e:
    print(f"Direct import 'import ddgs': FAILED ({e})")

try:
    from duckduckgo_search import DDGS
    print("From import 'from duckduckgo_search import DDGS': SUCCESS")
except ImportError as e:
    print(f"From import 'from duckduckgo_search import DDGS': FAILED ({e})")

import pkg_resources
try:
    ver = pkg_resources.get_distribution("duckduckgo-search").version
    print(f"Installed version: {ver}")
except Exception as e:
    print(f"Could not get version: {e}")
