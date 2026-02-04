import json
from typing import List
from ..core.redis import redis_manager


class RouteProgressService:
    """Manages per-bus visited student state for multi-device continuity."""

    def __init__(self):
        self.prefix = "route_visited"

    def _key(self, bus_id: str) -> str:
        return f"{self.prefix}:{bus_id}"

    async def get_visited(self, bus_id: str) -> List[str]:
        try:
            raw = await redis_manager.get(self._key(bus_id))
            if not raw:
                return []
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception:
            pass
        return []

    async def add_visited(self, bus_id: str, student_id: str) -> List[str]:
        visited = await self.get_visited(bus_id)
        if student_id not in visited:
            visited.append(student_id)
        await redis_manager.set(self._key(bus_id), json.dumps(visited), ex=60 * 60 * 24)
        return visited

    async def clear(self, bus_id: str) -> None:
        try:
            await redis_manager.delete(self._key(bus_id))
        except Exception:
            pass
