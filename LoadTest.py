import requests
import argparse
import random
import threading
import time
import uuid
from typing import List

class LoadTestUser:
    def __init__(self, username: str, base_url: str = "http://localhost:8080"):
        self.username = username
        self.base_url = base_url
        self.user_id = None
        self.channel_id = None
    
    def register(self):
        """Register the user with a default profile picture"""
        # Create a small text file as profile picture
        files = {'profile_picture': ('profile.txt', b'test')}
        
        # Send as multipart form data
        response = requests.post(
            f"{self.base_url}/register",
            files=files,
            params={
                'username': self.username,
                'password': 'password123'
            }
        )
        if response.status_code != 200:
            raise Exception(f"Failed to register user {self.username}: {response.text}")
        
        # Login to get user details
        response = requests.post(
            f"{self.base_url}/login",
            json={"username": self.username, "password": "password123"}
        )
        if response.status_code != 200:
            raise Exception(f"Failed to login user {self.username}: {response.text}")
        
        self.user_id = response.json()["user"]["id"]
        return self.user_id

    def join_channel(self, channel_name: str):
        """Join a channel by name"""
        response = requests.post(
            f"{self.base_url}/join_channel",
            json={"username": self.username, "channel_name": channel_name}
        )
        if response.status_code != 200:
            raise Exception(f"Failed to join channel {channel_name}: {response.text}")
        self.channel_id = response.json()["channel_membership"]["channel_id"]
        return self.channel_id

    def send_message(self):
        """Send a message to the channel"""
        if not self.channel_id:
            raise Exception("Not in a channel")
        
        response = requests.post(
            f"{self.base_url}/send_message",
            json={
                "channel_id": self.channel_id,
                "user_id": self.user_id,
                "content": f"Load test message from {self.username} at {time.time()}"
            }
        )
        if response.status_code != 200:
            raise Exception(f"Failed to send message: {response.text}")

def message_sender(user: LoadTestUser, stop_event: threading.Event):
    """Thread function to send messages periodically"""
    while not stop_event.is_set():
        try:
            user.send_message()
            # Random sleep between 0.8 and 1.2 seconds (jitter)
            time.sleep(random.uniform(0.8, 1.2))
        except Exception as e:
            print(f"Error sending message for {user.username}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Run load test with N users')
    parser.add_argument('n', type=int, help='Number of users to create')
    args = parser.parse_args()

    # Generate a test run ID
    test_run_id = str(uuid.uuid4())[:8]
    print(f"Starting load test {test_run_id} with {args.n} users")

    # Create users
    users: List[LoadTestUser] = []
    for i in range(args.n):
        username = f"loadtest_{test_run_id}_{i+1}"
        user = LoadTestUser(username)
        try:
            user.register()
            users.append(user)
            print(f"Created user {username}")
        except Exception as e:
            print(f"Failed to create user {username}: {e}")

    if not users:
        print("No users were created successfully. Exiting.")
        return

    # Create load test channel
    channel_name = f"LoadTest_{test_run_id}"
    response = requests.post(
        "http://localhost:8080/create_channel",
        json={
            "name": channel_name,
            "channel_type": "conversation",
            "creator_id": users[0].user_id,
            "description": f"Load test channel for run {test_run_id}"
        }
    )
    if response.status_code != 200:
        raise Exception(f"Failed to create channel: {response.text}")

    # Have all users join the channel
    for user in users:
        try:
            user.join_channel(channel_name)
            print(f"User {user.username} joined channel {channel_name}")
        except Exception as e:
            print(f"Failed to join channel for {user.username}: {e}")

    # Start message sending threads
    stop_event = threading.Event()
    threads = []
    for user in users:
        thread = threading.Thread(target=message_sender, args=(user, stop_event))
        thread.start()
        threads.append(thread)

    try:
        # Run for a while (or until Ctrl+C)
        print("Press Ctrl+C to stop the load test")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping load test...")
        stop_event.set()
        for thread in threads:
            thread.join()
        print("Load test completed")

if __name__ == "__main__":
    main()
