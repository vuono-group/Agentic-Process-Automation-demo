"""
Orchestration Runner

A script for running the sales order processing workflow using the OpenAI Agent SDK.
This script implements an explicit handoff mechanism for OpenAI Agent SDK version 0.0.3.
"""

import asyncio
import sys
from agents import Runner
from agents.tracing import trace

# Import the specialized agents
from email_agent import email_agent
from order_agent import order_agent
from bc_agent import bc_agent
from orchestration_agent import orchestration_agent

def print_usage() -> None:
    """Print usage information for the script."""
    print("\nUsage:")
    print("  python orchestration_runner.py [input_text]")
    print("\nExamples:")
    print("  python orchestration_runner.py \"Run the complete workflow\"")
    print("  python orchestration_runner.py \"Fetch emails and identify orders\"")
    print("  python orchestration_runner.py \"Check for new orders and post to Business Central\"")
    print("\nIf no input is provided, the default is to run the complete workflow.")

async def run_explicit_workflow() -> None:
    """Run the workflow with explicit handoffs between agents."""
    print("\n================================================================================")
    print("RUNNING ORCHESTRATION WITH EXPLICIT HANDOFFS")
    print("================================================================================")
    
    with trace(workflow_name="Explicit Orchestration") as current_trace:
        try:
            # Step 1: Start with the orchestration agent
            print("\n--- Step 1: Orchestration Agent - Initial Instructions ---")
            orchestration_result = await Runner.run(
                orchestration_agent, 
                input="Run the complete workflow"
            )
            print(f"\nOrchestration Agent Initial Response:\n{orchestration_result.final_output}")
            
            # Step 2: Run the email agent
            print("\n--- Step 2: Email Agent - Fetch Emails ---")
            email_result = await Runner.run(
                email_agent, 
                input="Fetch all emails from my inbox using credentials_path='credentials.json'"
            )
            print(f"\nEmail Agent Result:\n{email_result.final_output}")
            
            # Step 3: Return to orchestration agent with email results
            print("\n--- Step 3: Orchestration Agent - Process Email Results ---")
            orchestration_email_result = await Runner.run(
                orchestration_agent, 
                input=f"The Email Agent has completed its task with the following result: {email_result.final_output}"
            )
            print(f"\nOrchestration Agent Response:\n{orchestration_email_result.final_output}")
            
            # Step 4: Run the order identification agent
            print("\n--- Step 4: Order Identification Agent - Identify Orders ---")
            order_result = await Runner.run(
                order_agent, 
                input="Identify orders from all emails in the emails directory"
            )
            print(f"\nOrder Identification Agent Result:\n{order_result.final_output}")
            
            # Step 5: Return to orchestration agent with order results
            print("\n--- Step 5: Orchestration Agent - Process Order Results ---")
            orchestration_order_result = await Runner.run(
                orchestration_agent, 
                input=f"The Order Identification Agent has completed its task with the following result: {order_result.final_output}"
            )
            print(f"\nOrchestration Agent Response:\n{orchestration_order_result.final_output}")
            
            # Step 6: Run the Business Central agent
            print("\n--- Step 6: Business Central Agent - Post Orders ---")
            bc_result = await Runner.run(
                bc_agent, 
                input="Post all identified orders to Business Central"
            )
            print(f"\nBusiness Central Agent Result:\n{bc_result.final_output}")
            
            # Step 7: Return to orchestration agent with BC results
            print("\n--- Step 7: Orchestration Agent - Final Summary ---")
            final_result = await Runner.run(
                orchestration_agent, 
                input=f"The Business Central Agent has completed its task with the following result: {bc_result.final_output}"
            )
            
            # Print the final result
            print("\n================================================================================")
            print("ORCHESTRATION COMPLETED")
            print("================================================================================")
            print("\nFinal Result:")
            print(final_result.final_output)
            
        except Exception as e:
            print("\n================================================================================")
            print("ORCHESTRATION ERROR")
            print("================================================================================")
            print(f"\nError: {str(e)}")
            print("\nPlease check your network connection and try again.")

async def run_specific_task(input_text: str) -> None:
    """Run a specific task using the appropriate agent."""
    print("\n================================================================================")
    print("RUNNING SPECIFIC TASK")
    print("================================================================================")
    print(f"Input: {input_text}")
    print("--------------------------------------------------------------------------------")
    
    with trace(workflow_name="Specific Task") as current_trace:
        try:
            # Determine which agent to use based on the input
            if "fetch email" in input_text.lower() or "check email" in input_text.lower():
                print("\nUsing Email Agent for this task...")
                result = await Runner.run(email_agent, input=input_text)
            elif "identify order" in input_text.lower() or "find order" in input_text.lower():
                print("\nUsing Order Identification Agent for this task...")
                result = await Runner.run(order_agent, input=input_text)
            elif "post order" in input_text.lower() or "business central" in input_text.lower():
                print("\nUsing Business Central Agent for this task...")
                result = await Runner.run(bc_agent, input=input_text)
            else:
                print("\nUsing Orchestration Agent for this task...")
                result = await Runner.run(orchestration_agent, input=input_text)
            
            # Print the final result
            print("\n================================================================================")
            print("TASK COMPLETED")
            print("================================================================================")
            print("\nResult:")
            print(result.final_output)
            
        except Exception as e:
            print("\n================================================================================")
            print("TASK ERROR")
            print("================================================================================")
            print(f"\nError: {str(e)}")
            print("\nPlease check your network connection and try again.")

async def main(input_text: str) -> None:
    """Main function to determine which mode to run."""
    if input_text.lower() == "run the complete workflow":
        # Run the workflow with explicit handoffs
        await run_explicit_workflow()
    else:
        # Run a specific task
        await run_specific_task(input_text)

if __name__ == "__main__":
    # Get the input text from command line arguments
    if len(sys.argv) > 1:
        input_text = " ".join(sys.argv[1:])
    else:
        # Default input
        input_text = "Run the complete workflow"
    
    try:
        # Run the main function
        asyncio.run(main(input_text))
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        # Print the error message with clear formatting
        print("\n================================================================================")
        print("RUNNER ERROR")
        print("================================================================================")
        print(f"\nError: {str(e)}")
        print_usage()
        sys.exit(1) 