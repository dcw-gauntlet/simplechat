from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Dict
from datetime import datetime
import uuid

class UserStatus(str, Enum):
    ONLINE = 'online'
    OFFLINE = 'offline'
    AWAY = 'away'
    DO_NOT_DISTURB = 'do_not_disturb'
    INVISIBLE = 'invisible'

class ChannelType(str, Enum):
    GROUP = 'conversation'
    THREAD = 'thread'
    DM = 'dm'

class User(BaseModel):
    id: str
    created_at: str
    username: str
    password: str
    token: str
    status: UserStatus
    profile_picture: str

    @classmethod
    def create(cls, username, password, profile_picture):
        return cls(id=str(uuid.uuid4()), created_at=datetime.now().isoformat(), username=username, password=password, token="", status=UserStatus.OFFLINE, profile_picture=profile_picture)

class Channel(BaseModel):
    id: str
    created_at: str
    name: str
    channel_type: ChannelType
    description: str
    members_count: int = 0


class ChannelMembership(BaseModel):
    user_id: str
    channel_id: str

class Message(BaseModel):
    id: str
    sent: str
    text: str
    sender: User
    content: str
    channel_id: str
    reactions: Dict[str, int] = {}  # Default to empty dict
    has_thread: bool = False
    has_image: bool = False
    thread: Optional[Channel] = None
    image: Optional[str] = None