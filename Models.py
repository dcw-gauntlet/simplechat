from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Dict, List
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
    ALL = 'all'

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
    creator_id: str


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
    thread_id: Optional[str] = None
    image: Optional[str] = None
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    file_content_type: Optional[str] = None

class Heartbeat(BaseModel):
    user_id: str
    channel_id: Optional[str] = None

class SearchRequest(BaseModel):
    search_query: str

class SearchResult(BaseModel):
    channel_id: str
    channel_name: str
    message: Message
    previous_message: Optional[Message] = None
    next_message: Optional[Message] = None
    score: float
    

class FileDescription(BaseModel):
    id: str
    filename: str
    content_type: str
    size: int
    created_at: str
    channel_id: str

class Chunk(BaseModel):
    id: Optional[int] = None
    embedding: List[float]
    file_id: str
    file_chunk: int
    text: str
    channel_id: str
