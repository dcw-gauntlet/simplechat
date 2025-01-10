from fastapi import FastAPI, HTTPException, Depends, Query, File, UploadFile, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
from datetime import datetime, timedelta
import jwt
import uuid
import bcrypt
from typing import Dict
from DataLayer import DataLayer
from Models import *
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import shutil
import os
import hashlib
from UserPresence import UserPresence

app = FastAPI()
dl = DataLayer()

@app.on_event("startup")
async def startup_event():
    print("Starting UserPresence WebSocket server...")
    await up.start()
    print("UserPresence WebSocket server started")

up = UserPresence(port=8887)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all HTTP headers
)

class Response(BaseModel):
    message: str
    ok: bool

class RegisterRequest(BaseModel):
    username: str
    password: str
    profile_picture: str = "https://placecats.com/100/100"

class RegisterResponse(Response):
    user: Optional[User] = None

# Ensure pictures directory exists
if not os.path.exists("pictures"):
    os.makedirs("pictures")

@app.post("/register")
async def register(
    username: str,
    password: str,
    profile_picture: UploadFile = File(...)
) -> Response:
    # Generate a unique filename
    file_extension = profile_picture.filename.split(".")[-1]
    picture_filename = f"{username}_profile.{file_extension}"
    file_path = f"pictures/{picture_filename}"
    
    # Save the uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(profile_picture.file, buffer)
    
    # Hash the password before storing
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    # Store the complete URL path
    profile_picture_url = f"http://venus:8080/get_picture?picture_url={picture_filename}"
    
    to_add = User.create(
        username=username,
        password=hashed_password,
        profile_picture=profile_picture_url  # Store the complete URL path
    )
    
    add_response = dl.add_user(to_add)
    if not add_response:
        os.remove(file_path)
        return Response(message="User already exists", ok=False)
        
    return Response(message="User registered successfully", ok=True)

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(Response):
    user: Optional[User] = None

@app.post("/login")
async def login(request: LoginRequest) -> LoginResponse:
    actual_user = dl.get_user_by_username(request.username)
    if actual_user is None:
        return LoginResponse(message="Invalid username or password", ok=False, user=None)
    
    # Compare the provided password with the stored hash
    if not bcrypt.checkpw(request.password.encode(), actual_user.password.encode()):
        return LoginResponse(message="Invalid username or password", ok=False, user=None)
    return LoginResponse(message="User logged in successfully", ok=True, user=actual_user)

class CreateChannelRequest(BaseModel):
    name: str
    channel_type: ChannelType
    creator_id: str
    description: str
    recipient_id: Optional[str] = None

class ChannelResponse(Response):
    channel: Channel

@app.post("/create_channel")
async def create_channel(request: CreateChannelRequest) -> ChannelResponse:
    if request.channel_type == ChannelType.DM:
        if not request.recipient_id:
            return ChannelResponse(message="Recipient ID required for DM channels", ok=False, channel=None)
            
        # Sort IDs to ensure same hash regardless of order
        user_ids = sorted([request.creator_id, request.recipient_id])
        dm_string = f"{user_ids[0]}_{user_ids[1]}"
        # Create UUID-like hash (32 chars)
        channel_id = hashlib.md5(dm_string.encode()).hexdigest()[:32]
        
        # Use recipient's username or a generated name
        dm_name = f"DM_{request.recipient_id}"  # You might want to use username instead
    else:
        channel_id = str(uuid.uuid4())
        dm_name = request.name

    # if channel already exists, return the existing channel
    existing_channel = dl.get_channel_by_id(channel_id)
    if existing_channel:
        return ChannelResponse(message="Channel already exists", ok=True, channel=existing_channel)

    channel = dl.create_channel(
        name=dm_name,
        channel_type=request.channel_type,
        creator_id=request.creator_id,
        description=request.description,
        channel_id=channel_id
    )

    return ChannelResponse(message="Channel created successfully", ok=True, channel=channel)

class JoinChannelRequest(BaseModel):
    username: str
    channel_name: str

class JoinChannelResponse(Response):
    channel_membership: Optional[ChannelMembership] = None

@app.post("/join_channel")
async def join_channel(request: JoinChannelRequest) -> JoinChannelResponse:
    user = dl.get_user_by_username(request.username)
    channel = dl.get_channel_by_name(request.channel_name)

    if channel is None:
        return JoinChannelResponse(message="Channel not found", ok=False, channel_membership=None)

    if user is None:
        return JoinChannelResponse(message="User not found", ok=False, channel_membership=None)

    # check if user is already in the channel
    current_members = dl.get_users_in_channel(channel.id)
    if any(member.id == user.id for member in current_members):
        return JoinChannelResponse(message="User already in the channel", ok=False, channel_membership=None)

    # Create the membership
    membership = dl.join_channel(user.id, channel.id)

    # Update the channel's member count
    channel.members_count += 1
    dl.cursor.execute(
        "UPDATE channels SET members_count = %s WHERE id = %s",
        (channel.members_count, channel.id)
    )

    return JoinChannelResponse(message="User joined channel successfully", ok=True, channel_membership=membership)

class MyChannelsRequest(BaseModel):
    user_id: str
    channel_type: ChannelType

class MyChannelsResponse(Response):
    channels: List[Channel]

@app.post("/my_channels")
async def my_channels(request: MyChannelsRequest) -> MyChannelsResponse:
    channels = dl.get_my_channels(request.user_id, request.channel_type)
    return MyChannelsResponse(message="Channels fetched successfully", ok=True, channels=channels)

class GetChannelMessagesRequest(BaseModel):
    channel_id: str

class GetChannelMessagesResponse(Response):
    messages: List[Message]

@app.get("/get_channel_messages")
async def get_channel_messages(channel_id: str = Query(...)) -> GetChannelMessagesResponse:
    messages = dl.get_channel_messages(channel_id)
    return GetChannelMessagesResponse(message="Messages fetched successfully", ok=True, messages=messages)

class SendMessageRequest(BaseModel):
    channel_id: str
    user_id: str
    content: str

class SendMessageResponse(Response):
    sent_message: Optional[Message] = None

@app.post("/send_message")
async def send_message(request: SendMessageRequest) -> SendMessageResponse:
    """
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
        thread_id: Optional[Str] = None
        image: Optional[str] = None
    """
    # Get the full user object
    # print(request.dict())

    user = dl.get_user(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    message = Message(
        id=str(uuid.uuid4()),
        sent=datetime.utcnow().isoformat(),
        text=request.content,
        sender=user,
        content=request.content,
        channel_id=request.channel_id,
        reactions={},
        has_thread=False,
        has_image=False,
        thread_id=None,
        image=None
    )
    
    saved_message = dl.send_message(message)

    return SendMessageResponse(message="Message sent successfully", ok=True, sent_message=saved_message)


# let's make pictures available - query parameter
@app.get("/get_picture")
async def get_picture(picture_url: str = Query(...)):
    file_path = f"pictures/{picture_url}"
    
    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Picture not found")
        
    try:
        return FileResponse(
            file_path,
            media_type="image/*",  # Let the system detect the correct media type
            filename=picture_url   # Original filename for download
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving picture: {str(e)}")

class ReactionRequest(BaseModel):
    message_id: str
    reaction: str  # The emoji
    user_id: str

@app.post("/add_reaction")
async def add_reaction(request: ReactionRequest) -> Response:
    message = dl.get_message(request.message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Initialize reactions dict if it doesn't exist
    if not hasattr(message, 'reactions'):
        message.reactions = {}
    
    # Increment the reaction count
    if request.reaction in message.reactions:
        message.reactions[request.reaction] += 1
    else:
        message.reactions[request.reaction] = 1
    
    return Response(message="Reaction added", ok=True)

@app.post("/remove_reaction")
async def remove_reaction(request: ReactionRequest) -> Response:
    message = dl.get_message(request.message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if request.reaction in message.reactions:
        message.reactions[request.reaction] = max(0, message.reactions[request.reaction] - 1)
        if message.reactions[request.reaction] == 0:
            del message.reactions[request.reaction]
    
    return Response(message="Reaction removed", ok=True)


class SearchChannelsResponse(Response):
    channels: List[Channel]

@app.get("/search_channels")
async def search_channels(prefix: str = Query(...)) -> SearchChannelsResponse:
    channels = dl.search_channels(prefix)
    return SearchChannelsResponse(
        message="Channels found successfully", 
        ok=True, 
        channels=channels
    )


class AddThreadRequest(BaseModel):
    message_id: str
    channel_id: str


@app.post("/add_thread")
async def add_thread(request: AddThreadRequest) -> Response:
    message = dl.get_message(request.message_id)
    channel = dl.get_channel(request.channel_id)

    if not message:
        return Response(message="Message not found", ok=False)

    if message.has_thread:
        return Response(message="Message already has a thread", ok=False)

    if not channel:
        return Response(message="Channel not found", ok=False)

    message.has_thread = True
    message.thread_id = channel.id

    # Add the original message sender to the thread channel
    dl.join_channel(message.sender.id, channel.id)
    
    # Update member count
    channel.members_count += 1
    dl.cursor.execute(
        "UPDATE channels SET members_count = %s WHERE id = %s",
        (channel.members_count, channel.id)
    )

    dl.add_thread(message)

    return Response(message="Thread added successfully", ok=True)


@app.get("/get_channel/{channel_id}")
async def get_channel(channel_id: str) -> ChannelResponse:
    channel = dl.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return ChannelResponse(message="Channel found successfully", ok=True, channel=channel)


class GetUserRequest(BaseModel):
    user_id: str

class GetUserResponse(Response):
    user: User

@app.post("/get_user")
async def get_user(request: GetUserRequest) -> GetUserResponse:
    user = dl.get_user(request.user_id)
    return GetUserResponse(message="User found successfully", ok=True, user=user)


class UserStatusRequest(BaseModel):
    request_user_id: str

class UserStatusResponse(Response):
    user_status: UserStatus

@app.post("/user_status")
async def user_status(request: UserStatusRequest) -> UserStatusResponse:
    user_status = up.get_user_status(request.request_user_id)
    return UserStatusResponse(message="User status fetched successfully", ok=True, user_status=user_status)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8080)