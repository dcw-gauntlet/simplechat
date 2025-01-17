from fastapi import FastAPI, HTTPException, Depends, Query, File, UploadFile, BackgroundTasks, Form
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
from fastapi.responses import FileResponse, Response as FastAPIResponse
import shutil
import os
import hashlib
from UserPresence import UserPresence
import tempfile
import pdfplumber
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.docstore.document import Document
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from Agent import Agent, Tools

load_dotenv()  # This should be at the start of the file

app = FastAPI()
dl = DataLayer()

# Get API key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY2")
print(OPENAI_API_KEY)
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

embeddings = OpenAIEmbeddings(
    api_key=OPENAI_API_KEY,
    model="text-embedding-3-small"
)
llm = ChatOpenAI(
    api_key=OPENAI_API_KEY,
    model="gpt-4-turbo-preview"  # Updated to the correct model name
)

tools = Tools(dl)
agent = Agent(  
    'google-gla:gemini-2.0-flash-exp',
    system_prompt='You are an AI agent that helps to manage worker chat details.',
    tools=tools.tools
)

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
    # Get the channel
    user = dl.get_user_by_username(request.username)
    if not user:
        return JoinChannelResponse(message="User not found", ok=False, channel_membership=None)

    channel = dl.get_channel_by_name(request.channel_name)
    if not channel:
        return JoinChannelResponse(message="Channel not found", ok=False, channel_membership=None)

    # Create membership
    membership = dl.join_channel(user.id, channel.id)
    if not membership:
        raise HTTPException(status_code=500, detail="Failed to join channel")

    return Response(message="Successfully joined channel", ok=True)

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
    file_id: Optional[str] = None

class SendMessageResponse(Response):
    sent_message: Optional[Message] = None

@app.post("/send_message")
async def send_message(request: SendMessageRequest, background_tasks: BackgroundTasks) -> SendMessageResponse:
    # Get the full user object
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
        image=None,
        file_id=request.file_id,
        file_name=None,
        file_content_type=None
    )
    
    saved_message = dl.send_message(message)

    # if the message starts with @ai, add the agent response to background tasks
    if message.content.startswith("@ai"):
        background_tasks.add_task(agent_response, message)

    channel = dl.get_channel(message.channel_id)
    if channel.channel_type == ChannelType.DM:
        # if the other user is ai, add the agent response to background tasks
        all_users = dl.get_users_in_channel(message.channel_id)
        for user in all_users:
            if user.username == "ai":
                print("Adding conversation response to background tasks")
                background_tasks.add_task(conversation_response, message)

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
    print(f"Adding reaction '{request.reaction}' to message {request.message_id}")
    
    message = dl.get_message(request.message_id)
    if not message:
        print(f"Message {request.message_id} not found")
        raise HTTPException(status_code=404, detail="Message not found")
    
    print(f"Found message: {message.dict()}")
    
    # Initialize reactions dict if it doesn't exist
    if not hasattr(message, 'reactions'):
        message.reactions = {}
    
    # Increment the reaction count
    if request.reaction in message.reactions:
        message.reactions[request.reaction] += 1
    else:
        message.reactions[request.reaction] = 1
    
    # Save the updated reactions
    success = dl.update_message_reactions(request.message_id, message.reactions)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update reactions")
    
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
    dl.update_channel_members_count(channel.id, channel.members_count)

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


class FileUploadRequest(BaseModel):
    file: UploadFile
    associated_channel: str

class FileUploadResponse(Response):
    file_id: str


@app.post("/upload_file")
async def upload_file(
    file: UploadFile = File(...),  # Changed to accept file directly
    associated_channel: str = Form(...)  # Use Form for text data
) -> FileUploadResponse:
    """
    Upload a file and get a file ID back.
    The file ID can then be used in a message to reference this file.
    """
    try:
        file_id = str(uuid.uuid4())
        file_content = await file.read()  # Read binary content directly
        
        success = dl.save_file(
            file_id=file_id,
            filename=file.filename,
            content_type=file.content_type,
            data=file_content,  # Pass binary data directly
            associated_channel=associated_channel
        )
        
        if not success:
            return FileUploadResponse(message="Failed to save file", ok=False, file_id=None)
            
        return FileUploadResponse(
            message="File uploaded successfully",
            ok=True,
            file_id=file_id
        )
        
    except Exception as e:
        return FileUploadResponse(
            message=f"Error uploading file: {str(e)}",
            ok=False,
            file_id=None
        )


class AssociatedFilesRequest(BaseModel):
    channel_id: str

class AssociatedFilesResponse(Response):
    files: List[FileDescription]

@app.post("/associated_files")
async def associated_files(request: AssociatedFilesRequest) -> AssociatedFilesResponse:
    files = dl.get_associated_files(request.channel_id)
    return AssociatedFilesResponse(message="Files fetched successfully", ok=True, files=files)

@app.get("/download_file/{file_id}")
async def download_file(file_id: str):
    """
    Download a file by its ID.
    """
    file_data = dl.get_file(file_id)
    if not file_data:
        raise HTTPException(status_code=404, detail="File not found")
        
    return FastAPIResponse(
        content=file_data['data'],
        media_type=file_data['content_type'],
        headers={
            'Content-Disposition': f'attachment; filename="{file_data["filename"]}"'
        }
    )

class SearchRequest(BaseModel):
    search_query: str

class SearchResult(BaseModel):
    channel_id: str
    channel_name: str
    message: Message
    previous_message: Optional[Message] = None
    next_message: Optional[Message] = None
    score: float

class SearchResponse(Response):
    results: List[SearchResult]

@app.post("/search")
async def search(request: SearchRequest) -> SearchResponse:
    """
    Search for messages containing the search query.
    Returns messages with context (previous and next messages) and relevance score.
    """
    try:
        search_results = dl.search_messages(request.search_query)
        return SearchResponse(
            message="Search completed successfully",
            ok=True,
            results=[SearchResult(**result) for result in search_results]
        )
    except Exception as e:
        return SearchResponse(
            message=f"Search failed: {str(e)}",
            ok=False,
            results=[]
        )


class RAGIngestRequest(BaseModel):
    file_id: str
    channel_id: Optional[str] = None
@app.post("/rag_ingest")
async def rag_ingest(request: RAGIngestRequest) -> Response:
    try:
        # Get the file from storage
        file = dl.get_file(request.file_id)
        if not file:
            return Response(message="File not found", ok=False)

        # Check file type
        content_type = file['content_type'].lower()
        file_extension = os.path.splitext(file['filename'])[1].lower()

        # Validate file type
        allowed_types = {
            'application/pdf': '.pdf',
            'text/plain': '.txt',
            'text/markdown': '.md'
        }
        
        if content_type not in allowed_types and file_extension not in ['.pdf', '.txt', '.md']:
            return Response(message="Unsupported file type. Only PDF, TXT, and MD files are supported.", ok=False)

        # Extract text based on file type
        documents = []
        
        if content_type == 'application/pdf' or file_extension == '.pdf':
            # Handle PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file['data'])
                temp_filename = temp_file.name

            with pdfplumber.open(temp_filename) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        documents.append(Document(
                            page_content=text,
                            metadata={"page": i + 1}
                        ))
            os.unlink(temp_filename)
            
        else:
            # Handle TXT and MD
            text = file['data'].decode('utf-8')
            documents.append(Document(
                page_content=text,
                metadata={"page": 1}
            ))

        # Chunk the documents
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=4_000, chunk_overlap=500)
        text_chunks = text_splitter.split_documents(documents)

        # Create embeddings
        chunks = [
            Chunk(
                embedding=embeddings.embed_query(chunk.page_content), 
                file_id=request.file_id, 
                file_chunk=i,
                text=chunk.page_content,
                channel_id=request.channel_id
            ) for i, chunk in enumerate(text_chunks)
        ]

        # Store chunks in database
        success = dl.add_chunks(chunks)
        
        if not success:
            return Response(message="Failed to store chunks", ok=False)

        return Response(message=f"Successfully processed {len(chunks)} chunks", ok=True)

    except Exception as e:
        print(f"Error in RAG ingest: {e}")
        return Response(message=f"Error processing file: {str(e)}", ok=False)


class RAGSearchRequest(BaseModel):
    query: str
    channel_id: Optional[str] = None

class RAGSearchResponse(Response):
    result: str

@app.post("/rag_search")
async def rag_search(request: RAGSearchRequest) -> RAGSearchResponse:
    try:
        # Get embedding for the query
        query_vector = embeddings.embed_query(request.query)
        
        if request.channel_id:
            # Get similar chunks from the specific channel
            chunks = dl.similarity_search_in_channel(
                query_vector, 
                request.channel_id,
                top_k=3
            )
        else:
            # Get similar chunks from all channels
            chunks = dl.similarity_search(query_vector, top_k=3)
        
        if not chunks:
            return RAGSearchResponse(
                message="No relevant content found",
                ok=True,
                result="I couldn't find any relevant information to answer your question."
            )
        
        # Format the chunks into a string for the LLM
        rag_string_parts = [f"# Result {n}\n{chunk.text}" for n, chunk in enumerate(chunks[:3])]
        rag_string = "Search results from documents:\n" + "\n".join(rag_string_parts)
        
        # Create the prompt with instructions
        prefix_instruction = f"User asks: {request.query}\n"
        
        # Get response from LLM
        response = llm.invoke(f"{prefix_instruction}{rag_string}\n# Instructions: Use the search results to answer the user's query.")
        
        if not response or not response.content:
            return RAGSearchResponse(
                message="Failed to generate response",
                ok=False,
                result="Sorry, I couldn't generate a response at this time."
            )
        
        return RAGSearchResponse(
            message="Search completed successfully",
            ok=True,
            result=response.content
        )
        
    except Exception as e:
        print(f"Error during RAG search: {e}")  # Add logging
        return RAGSearchResponse(
            message=f"Error during RAG search: {str(e)}",
            ok=False,
            result="An error occurred while processing your request."
        )



async def agent_response(message, n_previous_messages=5):
    """
    Given a message, the agent composes a response to it.
    """
    ai_user = dl.get_user('1')

    # select previous n messages in the channel
    channel = dl.get_channel(message.channel_id)
    messages = dl.get_channel_messages(message.channel_id)
    previous_messages = messages[-n_previous_messages:]

    recent_history = "# Recent messages\n" + "\n".join([f"{message.sender.username}: {message.content}" for message in previous_messages])

    build_rag_query = f"# Instructions\n Given the recent messages, and the user's specific question, build a query for the RAG search."

    build_rag_query = f"{build_rag_query}\n{recent_history}\n# User's question\n {message.content}"

    rag_query = llm.invoke(build_rag_query).content

    # Create a proper RAGSearchRequest object
    rag_request = RAGSearchRequest(
        query=rag_query,
        channel_id=message.channel_id
    )
    
    rag_search_response = await rag_search(rag_request)  # Pass the request object

    build_response = f"""# Instructions
    The user has sent a message asking for AI assistance.  You should construct a *high quality* response.
    Answer what the user asked, and think deeper - answer also what they should have asked or likely meant to ask.
    Be concise - 1-3 sentences.
    If you don't know, or don't have enough information, say so.  That's okay.
    # RAG search results
    {rag_search_response}
    # Recent messages
    {recent_history}
    # User's question
    {message.content}
    """

    response = llm.invoke(build_response).content

    # Create a proper SendMessageRequest object
    send_message_request = SendMessageRequest(
        channel_id=message.channel_id,
        user_id=ai_user.id,
        content=response
    )

    await send_message(send_message_request, BackgroundTasks())  # Pass an empty BackgroundTasks instance


async def conversation_response(message, n_previous_messages=25):
    # Get recent messages
    messages = dl.get_channel_messages(message.channel_id)
    recent_messages = messages[-n_previous_messages:]
    
    # Format conversation history
    conversation_history = "\n".join([
        f"{msg.sender.username}: {msg.content}" 
        for msg in recent_messages
    ])
    
    # Create context-aware prompt
    context_prompt = f"""You are an AI agent that helps to manage worker chat details.

Recent conversation:
{conversation_history}

Current message:
{message.content}"""

    # Run agent with updated prompt
    result = await agent.run(context_prompt)
    print("Agent response: ", result)

    # Send response
    ai_user = dl.get_user('1')
    if result:
        send_message_request = SendMessageRequest(
            channel_id=message.channel_id,
            user_id=ai_user.id,
            content=str(result.data)
        )
        await send_message(send_message_request, BackgroundTasks())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8080, workers=4)  # Add workers parameter