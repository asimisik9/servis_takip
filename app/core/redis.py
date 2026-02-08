import redis.asyncio as redis
from .config import settings
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class RedisManager:
    def __init__(self):
        self.redis: redis.Redis | None = None

    async def connect(self):
        self.redis = redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
            encoding="utf-8",
            decode_responses=True
        )
        await self.redis.ping()
        logger.info("Redis bağlantısı başarılı.")

    async def close(self):
        if self.redis:
            await self.redis.close()
            logger.info("Redis bağlantısı kapatıldı.")

    async def get_redis(self) -> redis.Redis:
        if not self.redis:
            await self.connect()
        return self.redis
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        if not self.redis:
            await self.connect()
        return await self.redis.get(key)
    
    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set value in Redis with optional expiration"""
        if not self.redis:
            await self.connect()
        return await self.redis.set(key, value, ex=ex)
    
    async def delete(self, key: str) -> int:
        """Delete key from Redis"""
        if not self.redis:
            await self.connect()
        return await self.redis.delete(key)
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern using SCAN (non-blocking)"""
        if not self.redis:
            await self.connect()
        deleted = 0
        async for key in self.redis.scan_iter(match=pattern, count=100):
            await self.redis.delete(key)
            deleted += 1
        return deleted

redis_manager = RedisManager()

async def get_redis() -> redis.Redis:
    return await redis_manager.get_redis()
