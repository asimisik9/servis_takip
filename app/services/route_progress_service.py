import json
from datetime import date
from typing import List
from ..core.redis import redis_manager


class RouteProgressService:
    """Manages per-bus visited student state for multi-device continuity."""

    def __init__(self):
        self.prefix = "route_visited"

    def _key(self, bus_id: str, trip_type: str, service_date: date | None = None) -> str:
        resolved_date = (service_date or date.today()).isoformat()
        return f"{self.prefix}:{bus_id}:{resolved_date}:{trip_type}"

    async def get_visited(self, bus_id: str, trip_type: str) -> List[str]:
        try:
            raw = await redis_manager.get(self._key(bus_id, trip_type))
            if not raw:
                return []
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception:
            pass
        return []

    async def add_visited(self, bus_id: str, trip_type: str, student_id: str) -> List[str]:
        visited = await self.get_visited(bus_id, trip_type)
        if student_id not in visited:
            visited.append(student_id)
        await redis_manager.set(self._key(bus_id, trip_type), json.dumps(visited), ex=60 * 60 * 24)
        return visited

    async def remove_visited(self, bus_id: str, trip_type: str, student_id: str) -> bool:
        visited = await self.get_visited(bus_id, trip_type)
        if student_id not in visited:
            return False
        updated = [current_id for current_id in visited if current_id != student_id]
        await redis_manager.set(self._key(bus_id, trip_type), json.dumps(updated), ex=60 * 60 * 24)
        return True

    async def clear(self, bus_id: str, trip_type: str) -> None:
        try:
            await redis_manager.delete(self._key(bus_id, trip_type))
        except Exception:
            pass
