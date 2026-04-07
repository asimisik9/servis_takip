from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from ..database.database import AsyncSessionLocal
from ..core.redis import redis_manager
from ..services.location_service import LocationService
from ..database.models.bus_location import BusLocation
from uuid import uuid4
from datetime import datetime, timezone
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── Batch Location Writer ────────────────────────────────────────────────────
# Instead of one DB commit per WS message (blocks the event loop and hammers DB),
# push to an in-memory queue and flush every 5 seconds in a background task.
_location_queue: asyncio.Queue = asyncio.Queue()


async def batch_location_writer():
    """Background task: batch-insert queued location updates every 5 seconds."""
    while True:
        await asyncio.sleep(5)
        if _location_queue.empty():
            continue
        batch = []
        while not _location_queue.empty():
            try:
                batch.append(_location_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if not batch:
            continue
        try:
            async with AsyncSessionLocal() as db:
                db.add_all([
                    BusLocation(
                        id=str(uuid4()),
                        bus_id=item["bus_id"],
                        latitude=item["latitude"],
                        longitude=item["longitude"],
                        speed=item.get("speed"),
                        timestamp=item["timestamp"],
                    )
                    for item in batch
                ])
                await db.commit()
                logger.info(f"Batch wrote {len(batch)} location record(s) to DB")
        except Exception as e:
            logger.error(f"Batch location write failed: {e}")


# ─── Per-connection WS Rate Limiter ──────────────────────────────────────────

def _make_ws_rate_limiter(max_messages: int = 120, window_seconds: int = 60):
    """Returns a per-connection checker. Call it for every incoming message.
    Returns False when the sliding-window limit is exceeded."""
    from collections import deque
    import time
    timestamps: deque = deque()

    def check() -> bool:
        now = time.monotonic()
        while timestamps and timestamps[0] < now - window_seconds:
            timestamps.popleft()
        if len(timestamps) >= max_messages:
            return False
        timestamps.append(now)
        return True

    return check


def _validate_location_data(data: dict) -> bool:
    """Validate incoming WebSocket location data."""
    try:
        lat = data.get('latitude')
        lng = data.get('longitude')
        if lat is None or lng is None:
            return False
        lat, lng = float(lat), float(lng)
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return False
        speed = data.get('speed')
        if speed is not None and (not isinstance(speed, (int, float)) or speed < 0 or speed > 300):
            return False
        return True
    except (TypeError, ValueError):
        return False


def _extract_ws_token(websocket: WebSocket) -> str | None:
    """Extract token from Authorization header only. Query param is not supported —
    tokens in URLs are logged by servers and stored in browser history."""
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


@router.websocket("/ws/driver/location")
async def driver_location_ws(websocket: WebSocket):
    """
    Şoförler için basitleştirilmiş WebSocket endpoint'i.
    Bus ID'yi token'dan bulur.
    """
    # Önce bağlantıyı kabul et, sonra kontrol et.
    # Bu sayede "Connection not upgraded" hatası yerine anlamlı bir WS kapanış kodu döneriz.
    await websocket.accept()

    logger.info("WS Connection accepted. Verifying token...")

    try:
        token = _extract_ws_token(websocket)
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        async with AsyncSessionLocal() as db:
            service = LocationService(db)
            user = await service.get_user_from_token(token)
            
            if not user:
                logger.warning("WS Closing: Invalid token or user not found")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
                
            if user.role.value != "sofor":
                logger.warning(f"WS Closing: User {user.id} is not a driver")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            bus = await service.get_driver_bus(user.id)
            if not bus:
                logger.warning(f"WS Closing: Driver {user.id} has no bus assigned")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
                
            bus_id = bus.id
            logger.info(f"WS Verified: Driver {user.id} for Bus {bus_id}")

        redis = await redis_manager.get_redis()
        channel_name = f"bus:{bus_id}:location"
        rate_check = _make_ws_rate_limiter()

        try:
            while True:
                data = await websocket.receive_text()

                if not rate_check():
                    logger.warning(f"WS rate limit exceeded for driver {user.id} — closing connection")
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    break

                try:
                    json_data = json.loads(data)

                    if not _validate_location_data(json_data):
                        logger.warning(f"Invalid location data from driver {user.id}")
                        continue

                    logger.info(f"Received location from driver {user.id} for bus {bus_id}")

                    # Publish to Redis pub/sub (real-time to subscribers)
                    await redis.publish(channel_name, json.dumps(json_data))

                    # Enqueue for batch DB write (flushed every 5 seconds)
                    _location_queue.put_nowait({
                        "bus_id": bus_id,
                        "latitude": json_data["latitude"],
                        "longitude": json_data["longitude"],
                        "speed": json_data.get("speed"),
                        "timestamp": datetime.now(timezone.utc),
                    })

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received from driver {user.id}")
        except WebSocketDisconnect:
            logger.info(f"Driver {user.id} disconnected from WS")
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            
    except Exception as e:
        logger.error(f"Unexpected error in WS handler: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass

@router.websocket("/ws/bus/{bus_id}/location")
async def bus_location_ws(websocket: WebSocket, bus_id: str):
    """
    Otobüs konumu için WebSocket bağlantısı.
    Redis Pub/Sub kullanarak ölçeklenebilir yapı.
    """
    logger.info(f"Bus WS Connection attempt. Bus: {bus_id}")
    await websocket.accept()

    try:
        token = _extract_ws_token(websocket)
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        async with AsyncSessionLocal() as db:
            service = LocationService(db)
            
            # Token doğrulama ve kullanıcıyı bulma
            user = await service.get_user_from_token(token)
            if not user:
                logger.warning("Bus WS Closing: Invalid token or user not found")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            # Yetki kontrolü
            if not await service.validate_ws_access(user, bus_id):
                logger.warning(f"Bus WS Closing: User {user.id} not authorized for bus {bus_id}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            logger.info(f"Bus WS Verified: User {user.id} listening to Bus {bus_id}")

            # Send last known location immediately
            try:
                query = select(BusLocation).where(BusLocation.bus_id == bus_id).order_by(BusLocation.timestamp.desc())
                last_location = (await db.execute(query)).scalars().first()
                
                if last_location:
                    initial_data = {
                        "latitude": last_location.latitude,
                        "longitude": last_location.longitude,
                        "speed": last_location.speed,
                        "timestamp": last_location.timestamp.isoformat() if last_location.timestamp else None
                    }
                    logger.info(f"Sending last known location to WS: {initial_data}")
                    await websocket.send_text(json.dumps(initial_data))
            except Exception as e:
                logger.error(f"Error sending last location: {e}")

        redis = await redis_manager.get_redis()
        pubsub = redis.pubsub()
        channel_name = f"bus:{bus_id}:location"
        
        # Redis kanalına abone ol
        await pubsub.subscribe(channel_name)
        logger.info(f"Subscribed to Redis channel: {channel_name}")

        async def forward_redis_to_ws():
            """Redis'ten gelen mesajları WebSocket'e iletir"""
            try:
                logger.info("Starting Redis listener loop...")
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        # Mesajı WebSocket üzerinden istemciye gönder
                        data = message["data"]
                        logger.info(f"Forwarding data to WS: {data}")
                        await websocket.send_text(data)
            except Exception as e:
                logger.error(f"Error forwarding Redis message: {e}")

        # Redis dinleyicisini arka plan görevi olarak başlat
        redis_reader_task = asyncio.create_task(forward_redis_to_ws())
        rate_check = _make_ws_rate_limiter()
        try:
            while True:
                # WebSocket'ten mesaj bekle (Genellikle şoförden gelir)
                data = await websocket.receive_text()

                if not rate_check():
                    logger.warning(f"WS rate limit exceeded for user {user.id} — closing connection")
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    break

                # Eğer gönderen şoför ise, konumu Redis'e yayınla
                if user.role.value == "sofor":
                    # Veriyi doğrula
                    try:
                        json_data = json.loads(data)

                        if not _validate_location_data(json_data):
                            logger.warning(f"Invalid location data from driver {user.id}")
                            continue

                        # Publish to Redis pub/sub (real-time to subscribers)
                        await redis.publish(channel_name, json.dumps(json_data))

                        # Enqueue for batch DB write (flushed every 5 seconds)
                        _location_queue.put_nowait({
                            "bus_id": bus_id,
                            "latitude": json_data["latitude"],
                            "longitude": json_data["longitude"],
                            "speed": json_data.get("speed"),
                            "timestamp": datetime.now(timezone.utc),
                        })

                    except json.JSONDecodeError:
                        pass
                
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            # Temizlik işlemleri
            redis_reader_task.cancel()
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
            
    except Exception as e:
        logger.error(f"Unexpected error in Bus WS handler: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass
