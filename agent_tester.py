"""
Agent Tester

A script for testing individual agents in the project using the OpenAI Agent SDK.
This is primarily for development and testing purposes.
"""

import asyncio
from agents import Runner, Agent

def list_available_agents():
    """List all available agents in the project."""
    agents = {
        "hello": "Basic agent without tools (hello_world.py)",
        "weather": "Weather agent with function tool (function_example.py)",
        "triage": "Language triage agent with handoffs (handsoff_example.py)",
        "email": "Email agent with multiple tools (email_agent.py)",
        "order": "Order identification agent with GPT-4o vision (order_agent.py)",
        "bc": "Business Central agent for posting orders (bc_agent.py)"
    }
    
    print("Available agents for testing:")
    for key, description in agents.items():
        print(f"  - {key}: {description}")
    print("\nUsage: python agent_tester.py <agent_name> [input_text]")
    print("Example: python agent_tester.py weather \"What's the weather in Tokyo?\"")
    print("Example: python agent_tester.py triage \"Hola, ¿cómo estás?\"")
    print("Example: python agent_tester.py order \"Identify orders from all emails\"")
    print("Example: python agent_tester.py bc \"Post order from emails/email_20250314_112347/identified_order.json\"")
    print("\nNote: For orchestration workflow, use orchestration_runner.py instead.")

def run_agent_sync(agent, input_text):
    """Run an agent synchronously using the OpenAI Agent SDK Runner.run_sync method."""
    print(f"Running agent: {agent.name}")
    print(f"Input: {input_text}")
    print("-" * 50)
    
    # Use the Runner.run_sync method from the OpenAI Agent SDK
    result = Runner.run_sync(agent, input_text)
    
    print("\nResult:")
    print(result.final_output)
    return result

async def run_agent_async(agent, input_text):
    """Run an agent asynchronously using the OpenAI Agent SDK Runner.run method."""
    print(f"Running agent: {agent.name}")
    print(f"Input: {input_text}")
    print("-" * 50)
    
    # Use the Runner.run method from the OpenAI Agent SDK
    result = await Runner.run(agent, input=input_text)
    
    print("\nResult:")
    print(result.final_output)
    return result

def get_agent(agent_name):
    """Import and return the specified agent."""
    try:
        if agent_name == "hello":
            from hello_world_agent_example import agent
            return agent, False  # False indicates sync is preferred
        elif agent_name == "weather":
            from function_agent_example import agent
            return agent, True  # True indicates async is preferred
        elif agent_name == "triage":
            from handsoff_agent_example import triage_agent
            return triage_agent, True
        elif agent_name == "email":
            from email_agent import email_agent
            return email_agent, True
        elif agent_name == "order":
            from order_agent import order_agent
            return order_agent, True
        elif agent_name == "bc":
            from bc_agent import bc_agent
            return bc_agent, True
        else:
            print(f"Error: Unknown agent '{agent_name}'")
            list_available_agents()
            return None, None
    except ImportError as e:
        print(f"Error importing agent: {e}")
        return None, None

# Example usage:
if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    if len(sys.argv) < 2:
        list_available_agents()
        sys.exit(0)
    
    agent_name = sys.argv[1].lower()
    
    # Check if user is trying to run the orchestration agent
    if agent_name == "orchestrate":
        print("\nFor orchestration workflow, please use the dedicated script:")
        print("  python orchestration_runner.py [input_text]")
        sys.exit(0)
    
    # Get the agent
    agent, use_async = get_agent(agent_name)
    if not agent:
        sys.exit(1)
    
    # Get the input text
    if len(sys.argv) > 2:
        input_text = " ".join(sys.argv[2:])
    else:
        # Default inputs for each agent
        if agent_name == "hello":
            input_text = "Write a haiku about recursion in programming."
        elif agent_name == "weather":
            input_text = "What's the weather in Tokyo?"
        elif agent_name == "triage":
            input_text = "Hola, ¿cómo estás?"
        elif agent_name == "email":
            input_text = "Fetch 5 emails from my inbox using credentials_path='credentials.json'"
        elif agent_name == "order":
            input_text = "Identify orders from all emails in the emails directory"
        elif agent_name == "bc":
            input_text = "Post all identified orders to Business Central"
    
    # Run the agent
    if use_async:
        asyncio.run(run_agent_async(agent, input_text))
    else:
        run_agent_sync(agent, input_text) 