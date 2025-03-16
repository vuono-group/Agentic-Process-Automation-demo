"""
Function Tool Agent Example

Demonstrates an agent that uses a function tool to retrieve weather information.
"""

from agents import Agent
from tools import get_weather

# Create a weather agent with the get_weather tool
agent = Agent(
    name="Weather Assistant",
    instructions="You are a helpful agent that provides weather information.",
    tools=[get_weather],
)