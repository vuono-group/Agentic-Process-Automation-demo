"""
Simple Handoff Example

A minimal example demonstrating the handoff mechanism in the OpenAI Agent SDK.
"""

import asyncio
import sys
from agents import Agent, Runner

# Create a specialized agent
specialist_agent = Agent(
    name="Specialist",
    instructions="""You are a specialist agent.
    
    When asked to perform a specialized task:
    1. Say: "I am the Specialist agent. I'm performing the specialized task."
    2. Say: "Task completed successfully."
    
    DO NOT ask follow-up questions. Simply complete your task.
    """,
)

# Create a coordinator agent with a handoff to the specialist
coordinator_agent = Agent(
    name="Coordinator",
    instructions="""You are a coordinator agent.
    
    Your job is to:
    1. Say: "I am the Coordinator agent. I'll handle this request."
    2. If the user asks for a specialized task, hand off to the Specialist agent by saying:
       "I'll transfer you to our Specialist agent who can help with this specialized task."
    3. After the Specialist completes their task, say: "I see the Specialist has completed their task. Control has returned to me."
    4. Say: "Is there anything else you need?"
    
    IMPORTANT: The OpenAI Agent SDK will automatically handle the control flow between agents.
    When you hand off to the Specialist agent, that agent will complete its task and then control will
    automatically return to you. You do not need to explicitly request control back.
    """,
    handoffs=[specialist_agent],
)

async def main():
    """Run the simple handoff example."""
    print("\n=== STARTING SIMPLE HANDOFF EXAMPLE ===\n")
    
    # First run with a request that should trigger a handoff
    print("--- First run: Request that should trigger a handoff ---")
    result1 = await Runner.run(
        coordinator_agent, 
        input="I need a specialized task performed."
    )
    print("\nFinal output from first run:")
    print(result1.final_output)
    
    # Second run with a request that should not trigger a handoff
    print("\n--- Second run: Request that should not trigger a handoff ---")
    result2 = await Runner.run(
        coordinator_agent, 
        input="Can you tell me about your role as a coordinator?"
    )
    print("\nFinal output from second run:")
    print(result2.final_output)
    
    print("\n=== SIMPLE HANDOFF EXAMPLE COMPLETED ===\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1) 