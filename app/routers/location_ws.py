from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List

router = APIRouter()

# Her otobüs için bağlantı listesi tut
active_connections: Dict[str, List[WebSocket]] = {}

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
async def bus_location_ws(websocket: WebSocket, bus_id: str):
    await connect_bus(bus_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # data: {"latitude": float, "longitude": float, "timestamp": str}
            await broadcast_location(bus_id, data)
    except WebSocketDisconnect:
        disconnect_bus(bus_id, websocket)
