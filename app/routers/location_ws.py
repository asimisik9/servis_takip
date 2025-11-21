from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from typing import Dict, List
from jose import jwt, JWTError
from .auth import SECRET_KEY, ALGORITHM

router = APIRouter()

# Her otobüs için bağlantı listesi tut
active_connections: Dict[str, List[WebSocket]] = {}

def verify_token(token: str) -> bool:
    """JWT token'ı doğrular"""
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return True
    except JWTError:
        return False

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
    URL: ws://localhost:8000/ws/bus/{bus_id}/location?token={jwt_token}
    """
    # Token doğrulama
    if not verify_token(token):
        # Token geçersizse bağlantıyı reddet (Policy Violation)
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
