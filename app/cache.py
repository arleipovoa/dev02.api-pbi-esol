from cachetools import TTLCache

cache = TTLCache(maxsize=10, ttl=60)