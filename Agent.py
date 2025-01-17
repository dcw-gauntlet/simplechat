from typing import Annotated, Literal, TypedDict, List

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool, StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph, MessagesState
from langgraph.prebuilt import ToolNode

from pydantic import BaseModel
from dotenv import load_dotenv
from DataLayer import DataLayer
import os

load_dotenv()

class Agent:
    def __init__(self, dl: DataLayer):
        # Create tools with proper docstrings
        self.tools = [
            StructuredTool.from_function(
                func=lambda usernames: get_messages_for_users(dl, usernames),
                name="get_messages_for_users",
                description="Get all messages from specified users within an optional time frame."
            ),
            StructuredTool.from_function(
                func=lambda hours: get_recent_messages(dl, hours),
                name="get_recent_messages",
                description="Get all messages from the past specified hours."
            )
        ]
        
        workflow = StateGraph(MessagesState)
        self.tool_node = ToolNode(self.tools)

        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", self.tool_node)

        workflow.add_edge(START, "agent")
        workflow.add_edge("tools", "agent")

        workflow.add_conditional_edges(
            "agent",
            self.should_continue
        )

        checkpointer = MemorySaver()
        self.app = workflow.compile(checkpointer=checkpointer)

        self.model = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY2"),
        ).bind_tools(self.tools)

    def call_model(self, state: MessagesState):
        messages = state['messages']
        response = self.model.invoke(messages)
        return {"messages": [response]}

    def should_continue(self, state: MessagesState):
        last_message = state['messages'][-1]
        print("Last message:", last_message)
        if last_message.tool_calls:
            return "tools"
        return END

    def run(self, message: str):
        return self.app.invoke(
            {"messages": [HumanMessage(content=message)]},
            config={"configurable": {"thread_id": 42}}
        )

# Tool functions defined outside the class
def get_messages_for_users(dl: DataLayer, usernames: List[str]):
    """Get all messages from specified users within an optional time frame."""
    print("Getting messages for users", usernames)
    messages = dl.get_messages_by_user(usernames)
    return [f"{message.sender.username}, {message.sent}: {message.text}" for message in messages]

def get_recent_messages(dl: DataLayer, hours: int = 24) -> list[str]:
    """Get all messages from the past specified hours."""
    print(f"Getting recent messages for the last {hours} hours")
    messages = dl.get_recent_messages(hours)
    return [f"{message.sender.username}, {message.sent}: {message.text}" for message in messages]



