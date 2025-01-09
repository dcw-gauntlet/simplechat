import websockets
import asyncio

PORT = 8887

async def handle_connection(websocket, path):
    while True:
        message = await websocket.recv()
        print(message)
