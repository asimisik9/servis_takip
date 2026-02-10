from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
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

async def save_location_to_db(bus_id: str, data: dict):
    try:
        async with AsyncSessionLocal() as db:
            new_location = BusLocation(
                id=str(uuid4()),
                bus_id=bus_id,
                latitude=data['latitude'],
                longitude=data['longitude'],
                speed=data.get('speed'),
                timestamp=datetime.now(timezone.utc)
            )
            db.add(new_location)
            await db.commit()
    except Exception as e:
        logger.error(f"Error saving location to DB for bus {bus_id}: {e}")


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


def _extract_ws_token(websocket: WebSocket, query_token: str | None) -> str | None:
    """Prefer Authorization header token, keep query token as backward-compatible fallback."""
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return query_token


@router.websocket("/ws/driver/location")
async def driver_location_ws(
    websocket: WebSocket,
    token: str | None = Query(default=None)
):
    """
    Şoförler için basitleştirilmiş WebSocket endpoint'i.
    Bus ID'yi token'dan bulur.
    """
    # Önce bağlantıyı kabul et, sonra kontrol et.
    # Bu sayede "Connection not upgraded" hatası yerine anlamlı bir WS kapanış kodu döneriz.
    await websocket.accept()
    
    logger.info("WS Connection accepted. Verifying token...")
    
    try:
        token = _extract_ws_token(websocket, token)
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
        
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    json_data = json.loads(data)
                    
                    if not _validate_location_data(json_data):
                        logger.warning(f"Invalid location data from driver {user.id}")
                        continue
                    
                    logger.info(f"Received location from driver {user.id} for bus {bus_id}")
                    
                    # Redis kanalına yayınla
                    await redis.publish(channel_name, json.dumps(json_data))
                    
                    # Apply backpressure: wait for DB persist before accepting next message.
                    await save_location_to_db(bus_id, json_data)
                    
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
async def bus_location_ws(
    websocket: WebSocket, 
    bus_id: str,
    token: str | None = Query(default=None)
):
    """
    Otobüs konumu için WebSocket bağlantısı.
    Redis Pub/Sub kullanarak ölçeklenebilir yapı.
    """
    logger.info(f"Bus WS Connection attempt. Bus: {bus_id}")
    await websocket.accept()
    
    try:
        token = _extract_ws_token(websocket, token)
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
        try:
            while True:
                # WebSocket'ten mesaj bekle (Genellikle şoförden gelir)
                data = await websocket.receive_text()
                
                # Eğer gönderen şoför ise, konumu Redis'e yayınla
                if user.role.value == "sofor":
                    # Veriyi doğrula
                    try:
                        json_data = json.loads(data)
                        
                        if not _validate_location_data(json_data):
                            logger.warning(f"Invalid location data from driver {user.id}")
                            continue
                        
                        # Redis kanalına yayınla
                        await redis.publish(channel_name, json.dumps(json_data))
                        
                        # Apply backpressure: wait for DB persist before accepting next message.
                        await save_location_to_db(bus_id, json_data)
                        
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
