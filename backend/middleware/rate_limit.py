from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ..redis_client import rate_limit


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent API abuse.
    Limits: 100 requests per minute per IP for general endpoints.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Different limits for different endpoints
        if request.url.path.startswith("/urgent") and request.method == "POST":
            # Stricter limit for creating urgent needs (handled in route)
            pass
        elif request.url.path.startswith("/listings") and request.method == "POST":
            # Limit listing creation: 10 per minute per IP
            key = f"rate_limit:listings:{client_ip}"
            if not rate_limit(key, limit=10, window_seconds=60):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait a moment."
                )
        else:
            # General API limit: 100 requests per minute per IP
            key = f"rate_limit:api:{client_ip}"
            if not rate_limit(key, limit=100, window_seconds=60):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait a moment."
                )
        
        response = await call_next(request)
        return response
