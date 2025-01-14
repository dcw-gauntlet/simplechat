import websockets
import asyncio
from datetime import datetime
from Models import UserStatus
from collections import defaultdict
import json
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS")

class HeartbeatRecord(BaseModel):
    user_id: str
    timestamp: datetime
    connected: bool

    @classmethod
    def default_record(cls, user_id: str):
        return cls(
            user_id=user_id,
            timestamp=datetime(1970, 1, 1),
            connected=False
        )


class UserPresence:
    """
    Open a websocket server.
    Allow users to connect and send heartbeat messages.
    """

    def __init__(self, port: int):
        self.port = port
        self.server = None
        # Default to a record with epoch time and disconnected status
        self.users = defaultdict(lambda: HeartbeatRecord.default_record(""))


    async def start(self):
        print(f"Attempting to start WebSocket server on port {self.port}...")
        self.server = await websockets.serve(
            self.handle_connection, 
            "0.0.0.0",  # Listen on all interfaces
            self.port,
            # Add CORS headers
            origins=ALLOWED_ORIGINS
        )
        print(f"WebSocket server is now running on port {self.port}")
        # No need to run_forever() as this will be run by the calling context


    async def handle_connection(self, websocket):
        client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        print(f"New WebSocket connection attempt from {client_address}")
        try:
            while True:
                message = await websocket.recv()
                print(f"Raw message received from {client_address}: {message}")
                data = json.loads(message)
                user_id = data['user_id']
                self.users[user_id] = HeartbeatRecord(
                    user_id=user_id,
                    timestamp=datetime.now(),
                    connected=True
                )
                print(f"Heartbeat processed for user {user_id} at {self.users[user_id].timestamp}")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"WebSocket connection closed for {client_address}: code={e.code} reason='{e.reason}'")
            # Mark user as disconnected but keep their last timestamp
            if 'user_id' in locals():
                record = self.users[user_id]
                self.users[user_id] = HeartbeatRecord(
                    user_id=user_id,
                    timestamp=record.timestamp,
                    connected=False
                )
        except Exception as e:
            print(f"Error handling connection from {client_address}: {str(e)}")
            import traceback
            traceback.print_exc()


    def get_last_heartbeat(self, user_id: str) -> datetime:
        return self.users[user_id].timestamp

    def get_user_status(self, user_id: str) -> UserStatus:
        record = self.users[user_id]
        now = datetime.now()
        
        if not record.connected:
            return UserStatus.OFFLINE
        
        # If last heartbeat was more than 30 seconds ago but still connected, consider user away
        if (now - record.timestamp).total_seconds() > 30:
            return UserStatus.AWAY
        
        return UserStatus.ONLINE

