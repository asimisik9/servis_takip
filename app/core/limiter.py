from slowapi import Limiter
from slowapi.util import get_remote_address
from .config import settings

# Use Redis for rate limiting storage so limits work across multiple workers/processes.
# Falls back to in-memory if Redis is not available.
_storage_uri = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri,
    default_limits=["200/minute"],  # Global default for all endpoints
)
