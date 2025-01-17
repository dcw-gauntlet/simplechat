import psycopg
from psycopg.rows import dict_row
from Models import *
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict
from dotenv import load_dotenv
import os
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

# load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


"""
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP,
    username VARCHAR(255) UNIQUE,
    password VARCHAR(255),
    token VARCHAR(255),
    status VARCHAR(20),
    profile_picture TEXT
);

CREATE TABLE channels (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP,
    name VARCHAR(255),
    channel_type VARCHAR(20),
    description TEXT,
    members_count INTEGER DEFAULT 0,
    creator_id VARCHAR(36) REFERENCES users(id)
);

CREATE TABLE channel_memberships (
    user_id VARCHAR(36) REFERENCES users(id),
    channel_id VARCHAR(36) REFERENCES channels(id),
    PRIMARY KEY (user_id, channel_id)
);

CREATE TABLE messages (
    id VARCHAR(36) PRIMARY KEY,
    sent TIMESTAMP,
    text TEXT,
    content TEXT,
    channel_id VARCHAR(36) REFERENCES channels(id),
    sender_id VARCHAR(36) REFERENCES users(id),
    reactions JSONB DEFAULT '{}',
    has_thread BOOLEAN DEFAULT FALSE,
    has_image BOOLEAN DEFAULT FALSE,
    thread_id VARCHAR(36),
    image TEXT
);

CREATE TABLE files (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP,
    filename VARCHAR(255),
    content_type VARCHAR(255),
    data BYTEA,
    size INTEGER
);
"""

class DataLayer:
    def __init__(self):
        """Establish a connection to the database and print a message"""
        self.conn_string = f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"

        try:
            self.pool = ConnectionPool(
                self.conn_string, 
                min_size=1, 
                max_size=10,
                timeout=30,
                kwargs={'row_factory': dict_row}
            )
            
            with self.pool.connection() as conn:
                register_vector(conn)  # Register vector type for this connection
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM users")
                count = cursor.fetchone()['count']

                print(f"Successfully connected to the database. {count} users found.")
            
        except Exception as e:
            print(f"Failed to connect to database: {str(e)}")
            raise

    def __del__(self):
        self.pool.close()

    
    def add_user(self, user: User):
        try:
            with self.pool.connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (id, created_at, username, password, token, status, profile_picture) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (user.id, user.created_at, user.username, user.password, user.token, user.status, user.profile_picture)
                )
                conn.commit()
                return True  # Indicate success
        except Exception as e:
            print(f"Error adding user: {e}")
            return False


    def get_user(self, user_id: str) -> User | None:
        """Get a user by their ID."""
        try:
            with self.pool.connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                user_data = cursor.fetchone()
                if user_data:
                    user_data['created_at'] = user_data['created_at'].isoformat()
                    return User(**user_data)
                return None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None


    def get_user_by_username(self, username: str) -> User | None:
        """Get a user by their username."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user_data = cursor.fetchone()
            print(f"User data: {user_data}")
            if not user_data:
                return None

            return User(id=user_data['id'], 
                created_at=str(user_data['created_at']), 
                username=user_data['username'], 
                password=user_data['password'], 
                token=user_data['token'], 
                status=user_data['status'], 
                profile_picture=user_data['profile_picture']
            )


    def add_channel(self, channel: Channel):
        try:
            with self.pool.connection() as conn:
                cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO channels (id, created_at, name, channel_type, description, members_count, creator_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (channel.id, channel.created_at, channel.name, channel.channel_type, channel.description, channel.members_count, channel.creator_id)
            )
            conn.commit()
            return True  # Indicate success
        except Exception as e:
            print(f"Error adding channel: {e}")
            return False


    def get_channel(self, channel_id: str) -> Channel | None:
        """Get a channel by its ID."""
        try:
            with self.pool.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM channels WHERE id = %s", (channel_id,))
                channel_data = cursor.fetchone()
                if channel_data:
                    channel_data['created_at'] = channel_data['created_at'].isoformat()
                    return Channel(**channel_data)
                return None
        except Exception as e:
            print(f"Error getting channel: {e}")
            return None

    
    def get_channel_by_name(self, channel_name: str) -> Channel | None:
        """Get a channel by its name."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM channels WHERE name = %s", (channel_name,))
            channel_data = cursor.fetchone()
            if channel_data:
                # Convert datetime to ISO format string
                channel_data['created_at'] = channel_data['created_at'].isoformat()
                return Channel(**channel_data)
            return None


    def get_channel_by_id(self, channel_id: str) -> Channel | None:
        """Get a channel by its ID."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM channels WHERE id = %s", (channel_id,))
            channel_data = cursor.fetchone()
            if channel_data:
                channel_data['created_at'] = channel_data['created_at'].isoformat()
                return Channel(**channel_data)
            return None


    def add_message(self, message: Message):
        thread_id = message.thread.id if message.thread else None
        try:
            with self.pool.connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (id, sent, text, content, channel_id, sender_id, reactions, has_thread, has_image, thread_id, image) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (message.id, message.sent, message.text, message.content, message.channel_id, message.sender_id, json.dumps(message.reactions), message.has_thread, message.has_image, thread_id, message.image)
                )
                conn.commit()
                return True  # Indicate success
        except Exception as e:
            print(f"Error adding message: {e}")
            return False


    def add_thread(self, message: Message):
        try:
            with self.pool.connection() as conn:
                cursor = conn.cursor()
                thread_id = message.thread_id if message.thread_id else None
                cursor.execute("UPDATE messages SET thread_id = %s, has_thread = TRUE WHERE id = %s", (thread_id, message.id))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding thread: {e}")
            return False


    def get_messages_in_channel(self, channel_id: str) -> list[Message]:
        """Get all messages for a specific channel."""
        try:
            with self.pool.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        m.id as message_id,
                        m.sent,
                        m.text,
                        m.content,
                    m.channel_id,
                    m.sender_id,
                    m.reactions,
                    m.has_thread,
                    m.has_image,
                    m.thread_id,
                    m.image,
                    m.file_id,
                    f.filename as file_name,
                    f.content_type as file_content_type,
                    u.id as user_id,
                    u.created_at,
                    u.username,
                    u.password,
                    u.token,
                    u.status,
                    u.profile_picture
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                LEFT JOIN files f ON m.file_id = f.id
                WHERE m.channel_id = %s
                ORDER BY m.sent ASC
            """, (channel_id,))
            message_data = cursor.fetchall()
            return [Message(
                **{
                    **msg,
                    'id': msg['message_id'],
                    'sent': msg['sent'].isoformat(),
                    'sender': User(
                        id=msg['user_id'],
                        created_at=msg['created_at'].isoformat(),
                        username=msg['username'],
                        password=msg['password'],
                        token=msg['token'],
                        status=msg['status'],
                        profile_picture=msg['profile_picture']
                    )
                }
            ) for msg in message_data]
        except Exception as e:
            print(f"Error getting messages in channel: {e}")
            return []
            

    def get_messages_by_user(self, user_id: str) -> list[Message]:
        """Get all messages sent by a specific user."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    m.id as message_id,
                    m.sent,
                    m.text,
                    m.content,
                    m.channel_id,
                    m.reactions,
                    m.has_thread,
                    m.has_image,
                    m.thread_id,
                    m.image,
                    m.file_id,
                    u.id as user_id,
                    u.created_at,
                    u.username,
                    u.password,
                    u.token,
                    u.status,
                    u.profile_picture
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.sender_id = %s
            """, (user_id,))
            message_data = cursor.fetchall()
            return [Message(
                **{
                    **msg,
                    'id': msg['message_id'],
                    'sent': msg['sent'].isoformat(),
                    'sender': User(
                        id=msg['user_id'],
                        created_at=msg['created_at'].isoformat(),
                        username=msg['username'],
                        password=msg['password'],
                        token=msg['token'],
                        status=msg['status'],
                        profile_picture=msg['profile_picture']
                    )
                }
            ) for msg in message_data]

    def add_channel_membership(self, membership: ChannelMembership):
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    # Add the membership
                    cur.execute("INSERT INTO channel_memberships (user_id, channel_id) VALUES (%s, %s)", 
                              (membership.user_id, membership.channel_id))
                    
                    # Update the channel's member count
                    cur.execute("""
                        UPDATE channels 
                        SET members_count = members_count + 1 
                        WHERE id = %s
                    """, (membership.channel_id,))
                    
                    conn.commit()
            return True
        except Exception as e:
            print(f"Error adding channel membership: {e}")
            return False

    def get_users_in_channel(self, channel_id: str) -> list[User]:
        """Get all users in a specific channel."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    u.id,
                    u.created_at,
                    u.username,
                    u.password,
                    u.token,
                    u.status,
                    u.profile_picture
                FROM users u
                JOIN channel_memberships cm ON u.id = cm.user_id
                WHERE cm.channel_id = %s
            """, (channel_id,))
            user_data = cursor.fetchall()
            return [User(**{**user, 'created_at': user['created_at'].isoformat()}) 
                    for user in user_data]


    def get_channels_for_user(self, user_id: str, channel_type: ChannelType) -> list[Channel]:
        """Get all channels a specific user is part of."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            if channel_type == ChannelType.ALL:
                query = """
                    SELECT DISTINCT
                    c.*
                FROM channels c
                INNER JOIN channel_memberships cm ON c.id = cm.channel_id
                WHERE cm.user_id = %s
                ORDER BY c.created_at DESC
                """
                params = (user_id,)
            else:
                query = """
                    SELECT DISTINCT
                        c.*
                    FROM channels c
                    INNER JOIN channel_memberships cm ON c.id = cm.channel_id
                    WHERE cm.user_id = %s 
                    AND c.channel_type = %s
                    ORDER BY c.created_at DESC
                """
                params = (user_id, channel_type.value)

            cursor.execute(query, params)
            channel_data = cursor.fetchall()
            return [Channel(**{**channel, 'created_at': channel['created_at'].isoformat()}) 
                    for channel in channel_data]


    def get_message(self, message_id: str) -> Message | None:
        """Get a message by its ID."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    m.id as message_id,
                    m.sent,
                    m.text,
                    m.content,
                    m.channel_id,
                    COALESCE(m.reactions::text, '{}') as reactions,
                    m.has_thread,
                    m.has_image,
                    m.thread_id,
                    m.image,
                    m.file_id,
                    f.filename as file_name,
                    f.content_type as file_content_type,
                    u.id as user_id,
                    u.created_at,
                    u.username,
                    u.password,
                    u.token,
                    u.status,
                    u.profile_picture
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                LEFT JOIN files f ON m.file_id = f.id
                WHERE m.id = %s
            """, (message_id,))
            
            msg = cursor.fetchone()
            print(f"Query result: {msg}")
            
            if msg:
                # Parse the reactions JSON string
                reactions = json.loads(msg['reactions']) if msg['reactions'] else {}
                print(f"Parsed reactions: {reactions}")
                
                return Message(
                    id=msg['message_id'],
                    sent=msg['sent'].isoformat(),
                    text=msg['text'],
                    content=msg['content'],
                    channel_id=msg['channel_id'],
                    reactions=reactions,
                    has_thread=msg['has_thread'],
                    has_image=msg['has_image'],
                    thread_id=msg['thread_id'],
                    image=msg['image'],
                    file_id=msg['file_id'],
                    file_name=msg['file_name'],
                    file_content_type=msg['file_content_type'],
                    sender=User(
                        id=msg['user_id'],
                        created_at=msg['created_at'].isoformat(),
                        username=msg['username'],
                        password=msg['password'],
                        token=msg['token'],
                        status=msg['status'],
                        profile_picture=msg['profile_picture']
                    )
                )
            print(f"No message found with ID: {message_id}")
            return None
        
    
    def get_user_status(self, user_id: str) -> str | None:
        """Get the status of a specific user."""
        user = self.get_user(user_id)
        return user.status if user else None

    def get_my_channels(self, user_id: str, channel_type: ChannelType) -> list[Channel]:
       """Get all channels a specific user is part of."""
       return self.get_channels_for_user(user_id, channel_type)
       
    def create_channel(self, name: str, channel_type: str, creator_id: str, description: str, channel_id: str = None) -> Channel:
        """Create a new channel."""
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    channel = Channel(
                        id=channel_id if channel_id else str(uuid.uuid4()),
                        created_at=datetime.now().isoformat(),
                        name=name,
                        channel_type=channel_type,
                        creator_id=creator_id,
                        description=description,
                        members_count=0,
                    )
                    
                    # Create channel only
                    cur.execute(
                        "INSERT INTO channels (id, created_at, name, channel_type, description, members_count, creator_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (channel.id, channel.created_at, channel.name, channel.channel_type, channel.description, channel.members_count, channel.creator_id)
                    )
                    
                    conn.commit()
                    return channel
        except Exception as e:
            print(f"Error creating channel: {e}")
            return None

    def join_channel(self, user_id: str, channel_id: str) -> ChannelMembership:
        """Join a channel."""
        membership = ChannelMembership(user_id=user_id, channel_id=channel_id)
        self.add_channel_membership(membership)
        return membership

    def send_message(self, message: Message):
        """Send a message to a channel."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            thread_id = message.thread_id if message.has_thread else None
            cursor.execute(
                """INSERT INTO messages 
                    (id, sent, text, content, channel_id, sender_id, reactions, 
                     has_thread, has_image, thread_id, image, file_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    message.id,
                    message.sent,
                    message.text,
                    message.content,
                    message.channel_id,
                    message.sender.id,
                    json.dumps(message.reactions),
                    message.has_thread,
                    message.has_image,
                    thread_id,
                    message.image,
                    message.file_id
                )
            )
            conn.commit()
            return self.get_message(message.id)  # Return the full message with sender info
        

    def get_channel_messages(self, channel_id: str) -> list[Message]:
        """Get all messages for a specific channel."""
        return self.get_messages_in_channel(channel_id)

    def search_channels(self, prefix: str) -> list[Channel]:
        """Search for channels by name prefix."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM channels WHERE LOWER(name) LIKE %s", (prefix.lower() + "%",))
            channel_data = cursor.fetchall()
            return [Channel(
                id=channel['id'],
                created_at=channel['created_at'].isoformat(),
                name=channel['name'],
                channel_type=channel['channel_type'],
                description=channel['description'],
                members_count=channel['members_count'],
                creator_id=channel['creator_id']
            ) for channel in channel_data]


    def save_file(self, file_id: str, filename: str, content_type: str, data: bytes, associated_channel: str) -> bool:
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO files (id, created_at, filename, content_type, data, size, associated_channel) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (file_id, datetime.now(), filename, content_type, data, len(data), associated_channel)
            )
            conn.commit()
            return True

    def get_associated_files(self, channel_id: str) -> list[FileDescription]:
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files WHERE associated_channel = %s", (channel_id,))
            file_data = cursor.fetchall()
            return [FileDescription(
                id=file['id'],
                filename=file['filename'],
                content_type=file['content_type'],
                size=file['size'],
                created_at=file['created_at'].isoformat(),  # Convert datetime to string
                channel_id=file['associated_channel']  # Map associated_channel to channel_id
            ) for file in file_data]
        

    def get_file(self, file_id: str) -> dict | None:
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM files WHERE id = %s",
                (file_id,)
            )
            file_data = cursor.fetchone()
            if file_data:
                return {
                    'id': file_data['id'],
                    'filename': file_data['filename'],
                    'content_type': file_data['content_type'],
                    'data': file_data['data'],
                    'size': file_data['size']
                }
            return None


    def search_messages(self, search_query: str) -> List[dict]:
        """
        Search for messages containing the search query using separate queries for clarity.
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            print(f"Searching for: '{search_query}'")
            
            # Query 1: Find matching messages
            cursor.execute("""
                SELECT 
                    m.id as message_id,
                    m.sent,
                    m.text,
                    m.content,
                    m.channel_id,
                    m.reactions,
                    m.has_thread,
                    m.has_image,
                    m.thread_id,
                    m.image,
                    m.file_id,
                    f.filename as file_name,
                    f.content_type as file_content_type,
                    c.name as channel_name,
                    u.id as user_id,
                    u.created_at as user_created_at,
                    u.username,
                    u.password,
                    u.token,
                    u.status,
                    u.profile_picture
                FROM messages m
                JOIN channels c ON m.channel_id = c.id
                JOIN users u ON m.sender_id = u.id
                LEFT JOIN files f ON m.file_id = f.id
                WHERE m.content ILIKE %s OR m.text ILIKE %s
                ORDER BY m.sent DESC
            """, (f"%{search_query}%", f"%{search_query}%"))
            
            results = cursor.fetchall()
            print(f"Found {len(results)} matching messages")
            
            search_results = []
            for result in results:
                print(f"Processing message: {result['content']}")
                
                # Query 2: Find previous message in the same channel
                cursor.execute("""
                    SELECT * FROM messages 
                    WHERE channel_id = %s 
                    AND sent < %s 
                    ORDER BY sent DESC 
                    LIMIT 1
                """, (result['channel_id'], result['sent']))
                prev_msg = cursor.fetchone()
                
                # Query 3: Find next message in the same channel
                cursor.execute("""
                    SELECT * FROM messages 
                    WHERE channel_id = %s 
                    AND sent > %s 
                    ORDER BY sent ASC 
                    LIMIT 1
                """, (result['channel_id'], result['sent']))
                next_msg = cursor.fetchone()
                
                # Get full message objects for previous and next messages
                prev_message = self.get_message(prev_msg['id']) if prev_msg else None
                next_message = self.get_message(next_msg['id']) if next_msg else None
                
                # Construct current message
                current_message = {
                    'id': result['message_id'],
                    'sent': result['sent'].isoformat(),
                    'text': result['text'],
                    'content': result['content'],
                    'channel_id': result['channel_id'],
                    'reactions': result['reactions'],
                    'has_thread': result['has_thread'],
                    'has_image': result['has_image'],
                    'thread_id': result['thread_id'],
                    'image': result['image'],
                    'file_id': result['file_id'],
                    'file_name': result['file_name'],
                    'file_content_type': result['file_content_type'],
                    'sender': {
                        'id': result['user_id'],
                        'created_at': result['user_created_at'].isoformat(),
                        'username': result['username'],
                        'password': result['password'],
                        'token': result['token'],
                        'status': result['status'],
                        'profile_picture': result['profile_picture']
                    }
                }
                
                search_results.append({
                    'channel_id': result['channel_id'],
                    'channel_name': result['channel_name'],
                    'message': current_message,
                    'previous_message': prev_message.dict() if prev_message else None,
                    'next_message': next_message.dict() if next_message else None,
                    'score': 1.0  # Simple score for now
                })
            
            return search_results


    def update_message_reactions(self, message_id: str, reactions: Dict[str, int]) -> bool:
        """Update the reactions for a message"""
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE messages SET reactions = %s WHERE id = %s",
                (json.dumps(reactions), message_id)
            )
            conn.commit()
            return True

    def update_channel_members_count(self, channel_id: str, count: int) -> bool:
        """Update the members count for a channel."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE channels SET members_count = %s WHERE id = %s", (count, channel_id))
            conn.commit()
            return True



    """
    CREATE TABLE IF NOT EXISTS public.chunks
    (
        id integer NOT NULL DEFAULT nextval('chunks_id_seq'::regclass),
        embedding vector(1536),
        file_id character varying(36) COLLATE pg_catalog."default" NOT NULL,
        file_chunk integer NOT NULL,
        CONSTRAINT chunks_pkey PRIMARY KEY (id),
        CONSTRAINT unique_file_chunk UNIQUE (file_id, file_chunk),
        CONSTRAINT fk_file FOREIGN KEY (file_id)
            REFERENCES public.files (id) MATCH SIMPLE
            ON UPDATE NO ACTION
            ON DELETE CASCADE
    )
    """
    def add_chunks(self, chunks: List[Chunk]):
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    chunk_data = [
                        (
                            f'[{",".join(map(str, chunk.embedding))}]',
                            chunk.file_id,
                            chunk.file_chunk,
                            chunk.text,
                            chunk.channel_id
                        ) 
                        for chunk in chunks
                    ]
                    
                    cur.executemany(
                        """
                        INSERT INTO chunks 
                        (embedding, file_id, file_chunk, text, channel_id)
                        VALUES (%s::vector, %s, %s, %s, %s)
                        """,
                        chunk_data
                    )
                    conn.commit()
            return True
        except Exception as e:
            print(f"Error adding chunks: {e}")
            return False

    def similarity_search(self, query_vector: List[float], top_k: int = 10) -> List[Chunk]:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    vector_str = f'[{",".join(map(str, query_vector))}]'
                    cur.execute("""
                        SELECT 
                            c.id,
                            c.embedding::text,  -- Convert to text for proper parsing
                            c.file_id,
                            c.file_chunk,
                            c.text,
                            f.filename,
                            f.content_type
                        FROM chunks c
                        JOIN files f ON c.file_id = f.id
                        ORDER BY c.embedding <=> %s::vector
                        LIMIT %s
                    """, (vector_str, top_k))
                    chunks = cur.fetchall()
                    
                    # Convert database results to Chunk objects
                    return [Chunk(
                        id=chunk['id'],
                        embedding=list(map(float, chunk['embedding'].strip('[]').split(','))),  # Properly parse the vector string
                        file_id=chunk['file_id'],
                        file_chunk=chunk['file_chunk'],
                        text=chunk['text']
                    ) for chunk in chunks]
        except Exception as e:
            print(f"Error in similarity search: {e}")
            return []

    def similarity_search_in_channel(self, query_vector: List[float], channel_id: str, top_k: int = 10) -> List[Chunk]:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    vector_str = f'[{",".join(map(str, query_vector))}]'
                    cur.execute("""
                        SELECT 
                            c.id,
                            c.embedding::text,
                            c.file_id,
                            c.file_chunk,
                            c.text,
                            c.channel_id,
                            f.filename,
                            f.content_type
                        FROM chunks c
                        JOIN files f ON c.file_id = f.id
                        WHERE c.channel_id = %s
                        ORDER BY c.embedding <=> %s::vector
                        LIMIT %s
                    """, (channel_id, vector_str, top_k))
                    chunks = cur.fetchall()
                    
                    return [Chunk(
                        id=chunk['id'],
                        embedding=list(map(float, chunk['embedding'].strip('[]').split(','))),
                        file_id=chunk['file_id'],
                        file_chunk=chunk['file_chunk'],
                        text=chunk['text'],
                        channel_id=chunk['channel_id']
                    ) for chunk in chunks]
        except Exception as e:
            print(f"Error in channel similarity search: {e}")
            return []

    def get_recent_messages(self, hours: int = 24) -> list[Message]:
        """Get all messages from the past specified hours."""
        try:
            with self.pool.connection() as conn:
                cursor = conn.cursor()
                
                query = f"""
                    SELECT 
                        m.id as message_id,
                        m.sent,
                        m.text,
                        m.content,
                        m.channel_id,
                        m.reactions,
                        m.has_thread,
                        m.has_image,
                        m.thread_id,
                        m.image,
                        m.file_id,
                        u.id as user_id,
                        u.created_at,
                        u.username,
                        u.password,
                        u.token,
                        u.status,
                        u.profile_picture
                    FROM messages m
                    JOIN users u ON m.sender_id = u.id
                    WHERE m.sent > NOW() - INTERVAL '{hours} hours'
                    ORDER BY m.sent ASC
                """
                
                cursor.execute(query)
                message_data = cursor.fetchall()
                print(f"Query executed. Found {len(message_data)} messages")
                
                messages = [Message(
                    **{
                        **msg,
                        'id': msg['message_id'],
                        'sent': msg['sent'].isoformat(),
                        'sender': User(
                            id=msg['user_id'],
                            created_at=msg['created_at'].isoformat(),
                            username=msg['username'],
                            password=msg['password'],
                            token=msg['token'],
                            status=msg['status'],
                            profile_picture=msg['profile_picture']
                        )
                    }
                ) for msg in message_data]
                
                return messages
                
        except Exception as e:
            print(f"Error in get_recent_messages: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_messages_for_users(self, user_ids: List[str], start_time: datetime = None, end_time: datetime = None) -> list[Message]:
        """Get all messages from specified users within an optional time frame.
        
        Args:
            user_ids: List of user IDs to get messages for
            start_time: Optional start time to filter messages (inclusive)
            end_time: Optional end time to filter messages (inclusive)
        """
        try:
            with self.pool.connection() as conn:
                cursor = conn.cursor()
                
                # Build the query dynamically based on provided parameters
                query = """
                    SELECT 
                        m.id as message_id,
                        m.sent,
                        m.text,
                        m.content,
                        m.channel_id,
                        m.reactions,
                        m.has_thread,
                        m.has_image,
                        m.thread_id,
                        m.image,
                        m.file_id,
                        u.id as user_id,
                        u.created_at,
                        u.username,
                        u.password,
                        u.token,
                        u.status,
                        u.profile_picture
                    FROM messages m
                    JOIN users u ON m.sender_id = u.id
                    WHERE u.username = ANY(%s)
                """
                params = [user_ids]
                
                # Add time constraints if provided
                if start_time:
                    query += " AND m.sent >= %s"
                    params.append(start_time)
                if end_time:
                    query += " AND m.sent <= %s"
                    params.append(end_time)
                
                query += " ORDER BY m.sent ASC"
                
                cursor.execute(query, params)
                message_data = cursor.fetchall()
                
                return [Message(
                    **{
                        **msg,
                        'id': msg['message_id'],
                        'sent': msg['sent'].isoformat(),
                        'sender': User(
                            id=msg['user_id'],
                            created_at=msg['created_at'].isoformat(),
                            username=msg['username'],
                            password=msg['password'],
                            token=msg['token'],
                            status=msg['status'],
                            profile_picture=msg['profile_picture']
                        )
                    }
                ) for msg in message_data]
                
        except Exception as e:
            print(f"Error getting messages for users: {e}")
            return []
