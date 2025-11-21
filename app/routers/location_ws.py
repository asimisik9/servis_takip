from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from typing import Dict, List
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .auth import SECRET_KEY, ALGORITHM
from ..database.database import AsyncSessionLocal
from ..database import models

router = APIRouter()

# Her otobüs için bağlantı listesi tut
active_connections: Dict[str, List[WebSocket]] = {}

async def get_user_from_token(token: str, db: AsyncSession):
    """Token'dan kullanıcıyı bulur"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        
        query = select(models.User).where(models.User.email == email)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    except JWTError:
        return None

async def connect_bus(bus_id: str, websocket: WebSocket):
    await websocket.accept()
    if bus_id not in active_connections:
        active_connections[bus_id] = []
    active_connections[bus_id].append(websocket)

def disconnect_bus(bus_id: str, websocket: WebSocket):
    if bus_id in active_connections:
        active_connections[bus_id].remove(websocket)
        if not active_connections[bus_id]:
            del active_connections[bus_id]

async def broadcast_location(bus_id: str, data: dict):
    if bus_id in active_connections:
        for ws in active_connections[bus_id]:
            await ws.send_json(data)

@router.websocket("/ws/bus/{bus_id}/location")
async def bus_location_ws(
    websocket: WebSocket, 
    bus_id: str,
    token: str = Query(...)
):
    """
    Otobüs konumu için WebSocket bağlantısı.
    Bağlanmak için geçerli bir JWT token gereklidir.
    Ayrıca kullanıcının bu otobüsü izleme yetkisi kontrol edilir.
    URL: ws://localhost:8000/ws/bus/{bus_id}/location?token={jwt_token}
    """
    async with AsyncSessionLocal() as db:
        # Token doğrulama ve kullanıcıyı bulma
        user = await get_user_from_token(token, db)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Yetki kontrolü
        if user.role.value == "veli":
            # Veli sadece kendi çocuğunun servisini izleyebilir
            # Parent -> Student -> BusAssignment -> Bus
            stmt = select(models.StudentBusAssignment).join(
                models.ParentStudentRelation,
                models.ParentStudentRelation.student_id == models.StudentBusAssignment.student_id
            ).where(
                models.ParentStudentRelation.parent_id == user.id,
                models.StudentBusAssignment.bus_id == bus_id
            )
            result = await db.execute(stmt)
            if not result.scalar_one_or_none():
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
                
        elif user.role.value == "sofor":
            # Şoför sadece kendi servisine bağlanabilir
            stmt = select(models.Bus).where(
                models.Bus.id == bus_id,
                models.Bus.current_driver_id == user.id
            )
            result = await db.execute(stmt)
            if not result.scalar_one_or_none():
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

    await connect_bus(bus_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # data: {"latitude": float, "longitude": float, "timestamp": str}
            await broadcast_location(bus_id, data)
    except WebSocketDisconnect:
        disconnect_bus(bus_id, websocket)
