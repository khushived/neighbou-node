import os
import json
from typing import Optional, Any
import redis
from dotenv import load_dotenv

load_dotenv()

# Redis connection
redis_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """Get or create Redis client."""
    global redis_client
    if redis_client is None:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_db = int(os.getenv("REDIS_DB", 0))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True,  # Automatically decode responses to strings
            socket_connect_timeout=5,
        )
        # Test connection
        try:
            redis_client.ping()
        except redis.ConnectionError:
            print("Warning: Redis not available. Caching disabled.")
            redis_client = None
    
    return redis_client


def cache_get(key: str) -> Optional[Any]:
    """Get value from cache."""
    try:
        r = get_redis()
        if r is None:
            return None
        value = r.get(key)
        if value:
            return json.loads(value)
    except Exception as e:
        print(f"Redis get error: {e}")
    return None


def cache_set(key: str, value: Any, expire_seconds: int = 300) -> bool:
    """Set value in cache with expiration."""
    try:
        r = get_redis()
        if r is None:
            return False
        r.setex(key, expire_seconds, json.dumps(value))
        return True
    except Exception as e:
        print(f"Redis set error: {e}")
    return False


def cache_delete(key: str) -> bool:
    """Delete key from cache."""
    try:
        r = get_redis()
        if r is None:
            return False
        r.delete(key)
        return True
    except Exception as e:
        print(f"Redis delete error: {e}")
    return False


def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching pattern."""
    try:
        r = get_redis()
        if r is None:
            return 0
        keys = r.keys(pattern)
        if keys:
            return r.delete(*keys)
        return 0
    except Exception as e:
        print(f"Redis delete pattern error: {e}")
    return 0


def rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """
    Rate limiting: returns True if under limit, False if exceeded.
    Uses sliding window counter.
    """
    try:
        r = get_redis()
        if r is None:
            return True  # If Redis unavailable, allow request
        
        current = r.incr(key)
        if current == 1:
            r.expire(key, window_seconds)
        
        return current <= limit
    except Exception as e:
        print(f"Redis rate limit error: {e}")
        return True  # Fail open if Redis unavailable
