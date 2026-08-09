from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.services.rate_limit_service import increment_rate_limit

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "GET":
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"
        count = await increment_rate_limit(key)
        if count > 20:
            return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": "Too many requests"})
        response = await call_next(request)
        return response
