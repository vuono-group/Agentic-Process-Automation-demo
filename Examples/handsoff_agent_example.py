"""
Language Triage Agent Example

Demonstrates agent handoffs between specialized language agents based on the input language.
"""

from agents import Agent

# Create language-specific agents
spanish_agent = Agent(
    name="Spanish agent",
    instructions="You only speak Spanish.",
)

english_agent = Agent(
    name="English agent",
    instructions="You only speak English",
)

# Create a triage agent that can hand off to the language agents
triage_agent = Agent(
    name="Triage agent",
    instructions="Handoff to the appropriate agent based on the language of the request.",
    handoffs=[spanish_agent, english_agent],
)