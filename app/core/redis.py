import redis.asyncio as redis
from .config import settings
from typing import Optional, Any

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
        print("Redis bağlantısı başarılı.")

    async def close(self):
        if self.redis:
            await self.redis.close()
            print("Redis bağlantısı kapatıldı.")

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
        """Delete all keys matching pattern"""
        if not self.redis:
            await self.connect()
        keys = await self.redis.keys(pattern)
        if keys:
            return await self.redis.delete(*keys)
        return 0

redis_manager = RedisManager()

async def get_redis() -> redis.Redis:
    return await redis_manager.get_redis()
