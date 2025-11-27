from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from ..database.database import AsyncSessionLocal
from ..core.redis import redis_manager
from ..services.location_service import LocationService
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws/bus/{bus_id}/location")
async def bus_location_ws(
    websocket: WebSocket, 
    bus_id: str,
    token: str = Query(...)
):
    """
    Otobüs konumu için WebSocket bağlantısı.
    Redis Pub/Sub kullanarak ölçeklenebilir yapı.
    """
    async with AsyncSessionLocal() as db:
        service = LocationService(db)
        
        # Token doğrulama ve kullanıcıyı bulma
        user = await service.get_user_from_token(token)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Yetki kontrolü
        if not await service.validate_ws_access(user, bus_id):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await websocket.accept()
    
    redis = await redis_manager.get_redis()
    pubsub = redis.pubsub()
    channel_name = f"bus:{bus_id}:location"
    
    # Redis kanalına abone ol
    await pubsub.subscribe(channel_name)

    async def forward_redis_to_ws():
        """Redis'ten gelen mesajları WebSocket'e iletir"""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    # Mesajı WebSocket üzerinden istemciye gönder
                    await websocket.send_text(message["data"])
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
                # Veriyi doğrula (basitçe JSON olup olmadığına bakıyoruz)
                try:
                    json_data = json.loads(data)
                    # Timestamp ekle veya güncelle
                    # json_data["server_timestamp"] = ...
                    
                    # Redis kanalına yayınla
                    await redis.publish(channel_name, json.dumps(json_data))
                    
                    # TODO: Burada veriyi asenkron olarak veritabanına da kaydetmeliyiz
                    # await save_location_to_db(bus_id, json_data)
                    
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
