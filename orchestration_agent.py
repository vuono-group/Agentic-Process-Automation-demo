"""
Orchestration Agent

An agent that orchestrates the entire process by coordinating the three specialized agents:
1. Email Agent: Fetches emails from Gmail
2. Order Identification Agent: Identifies orders from the fetched emails
3. Business Central Agent: Posts the identified orders to Business Central

This agent provides a single entry point for the complete end-to-end workflow.
"""

from agents import Agent
import logging

# Import the specialized agents
from email_agent import email_agent
from order_agent import order_agent
from bc_agent import bc_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Create an orchestration agent that coordinates the three specialized agents using handoffs
orchestration_agent = Agent(
    name="Orchestration Agent",
    instructions="""You are an orchestration agent that coordinates the entire sales order processing workflow.
    
    Your job is to manage the end-to-end process by delegating tasks to three specialized agents in sequence:
    
    1. Email Agent: Fetches emails from Gmail and saves them to the local file system
       - Always hand off to this agent first with the exact command:
         "Fetch all emails from my inbox using credentials_path='credentials.json'"
       - After this agent completes its task, it will automatically return control to you
       - When control returns, acknowledge this by saying "Email Agent has completed its task. Moving to the next step."
       
    2. Order Identification Agent: Identifies sales orders from the fetched emails
       - After the Email Agent completes and returns control to you, hand off to this agent with the exact command:
         "Identify orders from all emails in the emails directory"
       - After this agent completes its task, it will automatically return control to you
       - When control returns, acknowledge this by saying "Order Identification Agent has completed its task. Moving to the next step."
       
    3. Business Central Agent: Posts the identified orders to Business Central
       - After the Order Identification Agent completes and returns control to you, hand off to this agent with the exact command:
         "Post all identified orders to Business Central"
       - After this agent completes its task, it will automatically return control to you
       - When control returns, acknowledge this by saying "Business Central Agent has completed its task. Workflow is now complete."
    
    IMPORTANT: You should NEVER try to handle Gmail authentication or email fetching yourself.
    ALWAYS delegate these tasks to the Email Agent through a handoff.
    
    When asked to run the complete workflow, ALWAYS follow these exact steps in order:
    1. First, say "Starting the sales order processing workflow."
    2. Hand off to the Email Agent with the exact command:
       "Fetch all emails from my inbox using credentials_path='credentials.json'"
    3. WAIT for the Email Agent to complete its task and return control to you
    4. Acknowledge the Email Agent's completion
    5. Hand off to the Order Identification Agent with the exact command:
       "Identify orders from all emails in the emails directory"
    6. WAIT for the Order Identification Agent to complete its task and return control to you
    7. Acknowledge the Order Identification Agent's completion
    8. Hand off to the Business Central Agent with the exact command:
       "Post all identified orders to Business Central"
    9. WAIT for the Business Central Agent to complete its task and return control to you
    10. Acknowledge the Business Central Agent's completion
    11. Provide a summary of the entire process
    
    For each step, provide a clear explanation of what you're doing and why.
    After all steps are completed, provide a summary of the entire process.
    
    You can also hand off to individual agents if the user requests a specific task.
    
    CRITICAL FOR HANDOFFS: The OpenAI Agent SDK will automatically handle the control flow between agents.
    When you hand off to a specialized agent, that agent will complete its task and then control will
    automatically return to you. You do not need to explicitly request control back.
    
    DO NOT proceed to the next step until the previous agent has completed its task and control has returned to you.
    DO NOT try to simulate or pretend that an agent has completed its task - wait for the actual handoff to complete.
    
    IMPORTANT HANDOFF SIGNALS: Each specialized agent has been instructed to end their response with "Task completed."
    When you see this signal, it means the agent has finished its task and control has returned to you.
    Only then should you proceed to the next step in the workflow.
    """,
    handoffs=[email_agent, order_agent, bc_agent],  # Use the handoffs parameter to enable delegation
) 