import asyncio
import websockets
import json

# Token from user logs
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkcml2ZXIxQGV4YW1wbGUuY29tIiwiaWQiOiIyZDI4ZThiZC1mOGYxLTRiM2MtOTc2Mi04M2QyOWFjOTQxZjkiLCJyb2xlIjoic29mb3IiLCJleHAiOjE3NjQ2NjQwODd9.-7l0z6VkTvg8UFrExfJa8ri0prSB2YVozDrkdGlKO98"
URI = f"ws://127.0.0.1:8000/ws/driver/location?token={TOKEN}"

async def test_connection():
    print(f"Connecting to {URI}")
    try:
        async with websockets.connect(URI) as websocket:
            print("Connected successfully!")
            
            # Send a test location
            data = {
                "latitude": 41.0082,
                "longitude": 28.9784,
                "speed": 50.0,
                "heading": 90.0,
                "timestamp": "2025-12-02T12:00:00"
            }
            await websocket.send(json.dumps(data))
            print(f"Sent data: {data}")
            
            # Keep open for a bit
            await asyncio.sleep(2)
            print("Closing connection")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
