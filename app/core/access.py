"""Optional shared service credential; production mode refuses an unconfigured key."""
import hmac
import os
from starlette.responses import JSONResponse


async def service_access(request, call_next):
    token = os.getenv('PYTHON_SERVICE_TOKEN', '')
    production = os.getenv('APP_ENV', '').lower() == 'production'
    if request.url.path == '/api/v1/health':
        return await call_next(request)
    if production and len(token) < 32:
        return JSONResponse({'detail': {'code': 'SERVICE_ACCESS_NOT_CONFIGURED'}}, status_code=503)
    if token:
        supplied = request.headers.get('authorization', '')
        if len(token)<32 or not hmac.compare_digest(supplied.encode(), ('Bearer '+token).encode()):
            return JSONResponse({'detail': {'code': 'SERVICE_ACCESS_DENIED'}}, status_code=403)
    return await call_next(request)
