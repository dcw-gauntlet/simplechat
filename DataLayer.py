import uuid
from Models import *


User.create(username="admin", password="admin", profile_picture="")

class DataLayer:
    def __init__(self):
        self.users = {}  # Key: user_id, Value: User object
        self.channels = {}  # Key: channel_id, Value: Channel object
        self.channel_memberships = {}  # Key: (user_id, channel_id), Value: ChannelMembership object
        self.messages = {}  # Key: message_id, Value: Message object

    # Add data to the DataLayer
    def add_user(self, user):
        user_exists = self.get_user_by_username(user.username)
        if user_exists:
            return False
        self.users[user.id] = user
        return True

    def add_channel(self, channel):
        self.channels[channel.id] = channel

    def add_channel_membership(self, membership):
        self.channel_memberships[(membership.user_id, membership.channel_id)] = membership

    def add_message(self, message):
        self.messages[message.id] = message

    # Query functions
    def get_user(self, user_id):
        """Get a user by their ID."""
        return self.users.get(user_id)

    def get_user_by_username(self, username):
        """Get a user by their username."""
        return next((user for user in self.users.values() if user.username == username), None)

    def get_channel(self, channel_id):
        """Get a channel by its ID."""
        return self.channels.get(channel_id)

    def get_messages_in_channel(self, channel_id):
        """Get all messages for a specific channel."""
        return [msg for msg in self.messages.values() if msg.channel_id == channel_id]

    def get_messages_by_user(self, user_id):
        """Get all messages sent by a specific user."""
        return [msg for msg in self.messages.values() if msg.sender.id == user_id]

    def get_users_in_channel(self, channel_id):
        """Get all users in a specific channel."""
        user_ids = [
            membership.user_id
            for membership in self.channel_memberships.values()
            if membership.channel_id == channel_id
        ]
        return [self.users[user_id] for user_id in user_ids]

    def get_channels_for_user(self, user_id):
        """Get all channels a specific user is part of."""
        channel_ids = [
            membership.channel_id
            for membership in self.channel_memberships.values()
            if membership.user_id == user_id
        ]
        return [self.channels[channel_id] for channel_id in channel_ids]

    def get_message(self, message_id):
        """Get a message by its ID."""
        return self.messages.get(message_id)

    def get_user_status(self, user_id):
        """Get the status of a specific user."""
        user = self.get_user(user_id)
        return user.status if user else None

    def get_my_channels(self, user_id):
        """Get all channels a specific user is part of."""
        return self.get_channels_for_user(user_id)

    def get_channel_by_name(self, channel_name):
        """Get a channel by its name."""
        return next((channel for channel in self.channels.values() if channel.name == channel_name), None)

    def get_user_by_username(self, username):
        """Get a user by their username."""
        return next((user for user in self.users.values() if user.username == username), None)

    def create_channel(self, name, channel_type, creator_id):
        """Create a new channel."""
        channel = Channel(
            id=str(uuid.uuid4()),
            created_at=datetime.now().isoformat(),
            name=name, 
            channel_type=channel_type, 
            creator_id=creator_id
        )

        self.add_channel(channel)
        return channel

    def join_channel(self, user_id, channel_id):
        """Join a channel."""
        membership = ChannelMembership(user_id=user_id, channel_id=channel_id)
        self.add_channel_membership(membership)
        return membership

    def send_message(self, message: Message):
        """Send a message to a channel."""
        self.add_message(message)
        return message

    def get_channel_messages(self, channel_id):
        """Get all messages for a specific channel."""
        return [msg for msg in self.messages.values() if msg.channel_id == channel_id]



