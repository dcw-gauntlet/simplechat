import psycopg
from psycopg.rows import dict_row
from Models import *
import json
import uuid
from datetime import datetime

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
"""

class DataLayer:
    def __init__(self):
        """Establish a connection to the database and print a message"""
        self.conn_string = "host=venus dbname=mydatabase user=user password=password"

        try:
            self.conn = psycopg.connect(self.conn_string, row_factory=dict_row)
            self.conn.autocommit = True
            self.cursor = self.conn.cursor()

            self.cursor.execute("SELECT 1")
            if self.cursor.fetchone():
                print("Successfully connected to the database")
            else:
                raise Exception("Database connection test failed")
            
        except Exception as e:
            print(f"Failed to connect to database: {str(e)}")
            raise

    def get_connection(self):
        return psycopg.connect(self.conn_string, row_factory=dict_row)

    def close_connection(self):
        self.conn.close()

    def __del__(self):
        self.close_connection()

    
    def add_user(self, user: User):
        try:
            self.cursor.execute(
                "INSERT INTO users (id, created_at, username, password, token, status, profile_picture) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (user.id, user.created_at, user.username, user.password, user.token, user.status, user.profile_picture)
            )
            return True  # Indicate success
        except Exception as e:
            print(f"Error adding user: {e}")
            return False
    def get_user(self, user_id: str) -> User | None:
        """Get a user by their ID."""
        self.cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_data = self.cursor.fetchone()
        if user_data:
            user_data['created_at'] = user_data['created_at'].isoformat()
            return User(**user_data)
        return None

    def get_user_by_username(self, username: str) -> User | None:
        """Get a user by their username."""
        self.cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user_data = self.cursor.fetchone()
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
            self.cursor.execute(
                "INSERT INTO channels (id, created_at, name, channel_type, description, members_count, creator_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (channel.id, channel.created_at, channel.name, channel.channel_type, channel.description, channel.members_count, channel.creator_id)
            )
            return True  # Indicate success
        except Exception as e:
            print(f"Error adding channel: {e}")
            return False

    def get_channel(self, channel_id: str) -> Channel | None:
        """Get a channel by its ID."""
        self.cursor.execute("SELECT * FROM channels WHERE id = %s", (channel_id,))
        channel_data = self.cursor.fetchone()
        if channel_data:
            channel_data['created_at'] = channel_data['created_at'].isoformat()
            return Channel(**channel_data)
        return None
    
    def get_channel_by_name(self, channel_name: str) -> Channel | None:
        """Get a channel by its name."""
        self.cursor.execute("SELECT * FROM channels WHERE name = %s", (channel_name,))
        channel_data = self.cursor.fetchone()
        if channel_data:
            # Convert datetime to ISO format string
            channel_data['created_at'] = channel_data['created_at'].isoformat()
            return Channel(**channel_data)
        return None

    def get_channel_by_id(self, channel_id: str) -> Channel | None:
        """Get a channel by its ID."""
        self.cursor.execute("SELECT * FROM channels WHERE id = %s", (channel_id,))
        channel_data = self.cursor.fetchone()
        if channel_data:
            channel_data['created_at'] = channel_data['created_at'].isoformat()
            return Channel(**channel_data)
        return None


    def add_message(self, message: Message):
        thread_id = message.thread.id if message.thread else None
        try:
            self.cursor.execute(
                "INSERT INTO messages (id, sent, text, content, channel_id, sender_id, reactions, has_thread, has_image, thread_id, image) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (message.id, message.sent, message.text, message.content, message.channel_id, message.sender_id, json.dumps(message.reactions), message.has_thread, message.has_image, thread_id, message.image)
            )
            return True  # Indicate success
        except Exception as e:
            print(f"Error adding message: {e}")
            return False

    def add_thread(self, message: Message):
        thread_id = message.thread_id if message.thread_id else None
        try:
            self.cursor.execute("UPDATE messages SET thread_id = %s, has_thread = TRUE WHERE id = %s", (thread_id, message.id))
            return True
        except Exception as e:
            print(f"Error adding thread: {e}")
            return False


    def get_messages_in_channel(self, channel_id: str) -> list[Message]:
        """Get all messages for a specific channel."""
        self.cursor.execute("""
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
                u.id as user_id,
                u.created_at,
                u.username,
                u.password,
                u.token,
                u.status,
                u.profile_picture
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.channel_id = %s
            ORDER BY m.sent ASC
        """, (channel_id,))
        message_data = self.cursor.fetchall()
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

    def get_messages_by_user(self, user_id: str) -> list[Message]:
        """Get all messages sent by a specific user."""
        self.cursor.execute("SELECT * FROM messages WHERE sender_id = %s", (user_id,))
        message_data = self.cursor.fetchall()
        return [Message(**{**msg, 'sent': msg['sent'].isoformat()}) for msg in message_data]

    def add_channel_membership(self, membership: ChannelMembership):
        try:
            self.cursor.execute("INSERT INTO channel_memberships (user_id, channel_id) VALUES (%s, %s)", (membership.user_id, membership.channel_id))
            return True  # Indicate success
        except Exception as e:
            print(f"Error adding channel membership: {e}")
            return False

    def get_users_in_channel(self, channel_id: str) -> list[User]:
        """Get all users in a specific channel."""
        self.cursor.execute("""
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
        user_data = self.cursor.fetchall()
        return [User(**{**user, 'created_at': user['created_at'].isoformat()}) 
                for user in user_data]

    def get_channels_for_user(self, user_id: str, channel_type: ChannelType) -> list[Channel]:
        """Get all channels a specific user is part of."""
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
        
        self.cursor.execute(query, params)
        channel_data = self.cursor.fetchall()
        return [Channel(**{**channel, 'created_at': channel['created_at'].isoformat()}) 
                for channel in channel_data]

    def get_message(self, message_id: str) -> Message | None:
        """Get a message by its ID."""
        self.cursor.execute("""
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
                u.id as user_id,
                u.created_at,
                u.username,
                u.password,
                u.token,
                u.status,
                u.profile_picture
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.id = %s
        """, (message_id,))
        msg = self.cursor.fetchone()
        if msg:
            return Message(
                **{
                    **msg,
                    'id': msg['message_id'],  # Use the aliased message_id
                    'sent': msg['sent'].isoformat(),
                    'sender': User(
                        id=msg['user_id'],    # Use the aliased user_id
                        created_at=msg['created_at'].isoformat(),
                        username=msg['username'],
                        password=msg['password'],
                        token=msg['token'],
                        status=msg['status'],
                        profile_picture=msg['profile_picture']
                    )
                }
            )
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
        channel = Channel(
            id=channel_id if channel_id else str(uuid.uuid4()),
            created_at=datetime.now().isoformat(),
            name=name,
            channel_type=channel_type,
            creator_id=creator_id,
            description=description,
            members_count=0,
        )
        self.add_channel(channel)
        return channel

    def join_channel(self, user_id: str, channel_id: str) -> ChannelMembership:
        """Join a channel."""
        membership = ChannelMembership(user_id=user_id, channel_id=channel_id)
        self.add_channel_membership(membership)
        return membership

    def send_message(self, message: Message):
        """Send a message to a channel."""
        thread_id = message.thread_id if message.has_thread else None
        try:
            self.cursor.execute(
                "INSERT INTO messages (id, sent, text, content, channel_id, sender_id, reactions, has_thread, has_image, thread_id, image) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
                    message.image
                )
            )
            return self.get_message(message.id)  # Return the full message with sender info
        except Exception as e:
            print(f"Error adding message: {e}")
            return None

    def get_channel_messages(self, channel_id: str) -> list[Message]:
        """Get all messages for a specific channel."""
        return self.get_messages_in_channel(channel_id)

    def search_channels(self, prefix: str) -> list[Channel]:
        """Search for channels by name prefix."""
        self.cursor.execute("SELECT * FROM channels WHERE LOWER(name) LIKE %s", (prefix.lower() + "%",))
        channel_data = self.cursor.fetchall()
        return [Channel(
            id=channel['id'],
            created_at=channel['created_at'].isoformat(),
            name=channel['name'],
            channel_type=channel['channel_type'],
            description=channel['description'],
            members_count=channel['members_count'],
            creator_id=channel['creator_id']
        ) for channel in channel_data]



