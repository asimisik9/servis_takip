import redis.asyncio as redis
from .config import settings

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

redis_manager = RedisManager()

async def get_redis() -> redis.Redis:
    return await redis_manager.get_redis()
