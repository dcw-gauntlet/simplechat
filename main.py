from fastapi import FastAPI, HTTPException, Depends, Query, File, UploadFile
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

app = FastAPI()
dl = DataLayer()


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

class ChannelResponse(Response):
    channel: Channel

@app.post("/create_channel")
async def create_channel(request: CreateChannelRequest) -> ChannelResponse:
    channel = dl.create_channel(request.name, request.channel_type, request.creator_id)
    return ChannelResponse(message="Channel created successfully", ok=True, channel=channel)

class JoinChannelRequest(BaseModel):
    username: str
    channel_name: str

class JoinChannelResponse(Response):
    channel_membership: ChannelMembership

@app.post("/join_channel")
async def join_channel(request: JoinChannelRequest) -> JoinChannelResponse:
    user = dl.get_user_by_username(request.username)
    channel = dl.get_channel_by_name(request.channel_name)

    membership = dl.join_channel(user.id, channel.id)
    return JoinChannelResponse(message="User joined channel successfully", ok=True, channel_membership=membership)

class MyChannelsRequest(BaseModel):
    user_id: str

class MyChannelsResponse(Response):
    channels: List[Channel]

@app.get("/my_channels")
async def my_channels(user_id: str = Query(...)) -> MyChannelsResponse:
    channels = dl.get_my_channels(user_id)
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
    sent_message: Message

@app.post("/send_message")
async def send_message(request: SendMessageRequest) -> SendMessageResponse:
    # Get the full user object
    user = dl.get_user(request.user_id)  # Assuming user_id is username
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    message = Message(
        id=str(uuid.uuid4()),
        sent=datetime.utcnow().isoformat(),
        text=request.content,
        sender=user,  # Use the full user object
        content=request.content,
        channel_id=request.channel_id,
        reactions={}
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8080)