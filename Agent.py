from dotenv import load_dotenv
import random
from pydantic_ai import Agent, RunContext
from Models import Message

from pydantic_ai import Agent

from DataLayer import DataLayer

load_dotenv()

class Tools:

    def __init__(self, dl: DataLayer):
        self.tools = [ self.roll, self.get_messages, self.get_recent_messages ]
        self.dl = dl

    def roll(self, ctx: RunContext[str], min_value: int, max_value: int) -> int:
        """
        Roll a die - producing a random number between min_value and max_value.

        :param min_value: The minimum value of the die.
        :param max_value: The maximum value of the die.

        :return: The random number between min_value and max_value.
        """
        print(ctx)
        roll = random.randint(1, 6)
        print(f"Min value: {min_value}, Max value: {max_value}, Roll: {roll}")
        return roll


    def get_messages(self, ctx: RunContext[str], username: str) -> list[Message]:
        """
        Get all messages sent by a specific user.

        :param username: The username of the user.

        :return: A list of messages sent by the user.
        """
        print(username)
        user = self.dl.get_user_by_username(username)
        messages = self.dl.get_messages_by_user(user.id)
        print("Found messages", messages)
        return messages

    def get_recent_messages(self, ctx: RunContext[str], hours: int = 24) -> list[Message]:
        """
        Get all messages from the past specified hours.

        :param hours: Number of hours to look back (default: 24)
        :return: List of messages from the specified time period
        """
        messages = self.dl.get_recent_messages(hours)

        return "\n".join([ f"{message.sender.username}: {message.content}" for message in messages ])

