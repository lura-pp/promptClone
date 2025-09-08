import streamlit as st
import json
from datetime import datetime
import pandas as pd
from mistralai import Mistral
from utils import copy_to_clipboard, download_button, display_chat_message

def create_function_call_agent(api_key):
    """Create an agent with custom function calls using Mistral API"""
    try:
        client = Mistral(api_key=api_key)
        
        # Define a custom function for getting interest rates
        function_agent = client.beta.agents.create(
            model="mistral-medium-latest",
            name="Function Call Agent",
            description="Agent that can call custom functions to retrieve information.",
            instructions="You can use custom functions to get interest rates and perform financial calculations.",
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "get_interest_rate",
                        "description": "Get the current interest rate for a specific region or central bank.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "region": {
                                    "type": "string",
                                    "description": "The region or central bank to get the interest rate for (e.g., US, ECB, UK, Japan)"
                                },
                                "date": {
                                    "type": "string",
                                    "description": "The date for which to fetch the rate, in YYYY-MM-DD format"
                                }
                            },
                            "required": ["region"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "calculate_loan_payment",
                        "description": "Calculate monthly payment for a loan with given parameters.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "principal": {
                                    "type": "number",
                                    "description": "The loan amount (principal)"
                                },
                                "annual_interest_rate": {
                                    "type": "number",
                                    "description": "Annual interest rate as a percentage (e.g., 5.2 for 5.2%)"
                                },
                                "term_years": {
                                    "type": "number",
                                    "description": "Loan term in years"
                                }
                            },
                            "required": ["principal", "annual_interest_rate", "term_years"]
                        }
                    }
                }
            ],
            completion_args={
                "temperature": 0.3,
                "top_p": 0.95
            }
        )
        
        return client, function_agent
    except Exception as e:
        st.error(f"Failed to create function call agent: {str(e)}")
        return None, None

def get_interest_rate(region, date=None):
    """Mock function to get interest rates for different regions"""
    # In a real application, this would call an external API
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    rates = {
        "us": {"rate": 5.5, "name": "Federal Reserve", "last_updated": "2023-12-13"},
        "ecb": {"rate": 4.0, "name": "European Central Bank", "last_updated": "2023-12-14"},
        "uk": {"rate": 5.25, "name": "Bank of England", "last_updated": "2023-12-15"},
        "japan": {"rate": -0.1, "name": "Bank of Japan", "last_updated": "2023-12-10"},
        "australia": {"rate": 4.35, "name": "Reserve Bank of Australia", "last_updated": "2023-12-05"},
        "canada": {"rate": 5.0, "name": "Bank of Canada", "last_updated": "2023-12-06"},
    }
    
    region_lower = region.lower()
    if region_lower in rates:
        return {
            "region": region,
            "date": date,
            "interest_rate": f"{rates[region_lower]['rate']}%",
            "central_bank": rates[region_lower]['name'],
            "last_updated": rates[region_lower]['last_updated']
        }
    else:
        return {
            "error": f"No interest rate data available for {region}",
            "available_regions": list(rates.keys())
        }

def calculate_loan_payment(principal, annual_interest_rate, term_years):
    """Calculate monthly payment for a loan"""
    # Convert annual interest rate to monthly
    monthly_rate = annual_interest_rate / 100 / 12
    
    # Calculate total number of payments
    payments = term_years * 12
    
    # Calculate monthly payment using the loan formula
    if monthly_rate == 0:
        monthly_payment = principal / payments
    else:
        monthly_payment = principal * (monthly_rate * (1 + monthly_rate) ** payments) / ((1 + monthly_rate) ** payments - 1)
    
    # Calculate total payment and interest
    total_payment = monthly_payment * payments
    total_interest = total_payment - principal
    
    return {
        "principal": principal,
        "annual_interest_rate": f"{annual_interest_rate}%",
        "term_years": term_years,
        "monthly_payment": round(monthly_payment, 2),
        "total_payment": round(total_payment, 2),
        "total_interest": round(total_interest, 2),
        "number_of_payments": payments
    }

def display_function_calls_page():
    st.title("📞 Function Calls")
    
    st.markdown("""
    Function Calls allow agents to interact with external APIs, databases, or proprietary systems by defining 
    JSON schemas for custom functions. This gives agents the ability to perform specific actions or retrieve 
    specialized information beyond their built-in capabilities.
    
    ### How it works:
    1. Define custom functions with parameters, descriptions, and JSON schemas
    2. The agent decides when to call these functions based on user queries
    3. The application executes the function calls and returns results to the agent
    4. The agent incorporates the results into its response
    
    This demonstration includes functions for retrieving financial data and performing calculations.
    """)
    
    # API key check
    if not st.session_state.api_key:
        st.warning("Please enter your Mistral API Key in the sidebar to use this feature.")
        return
    
    # Example prompts
    examples = [
        "What is the current interest rate in the US?",
        "Calculate the monthly payment for a $300,000 loan at 5.2% interest over 30 years.",
        "Compare the interest rates between the ECB and the Bank of England.",
        "What would be my monthly payment for a $50,000 car loan at 4.5% for 5 years?",
        "Get me the interest rate from the Bank of Japan and explain what negative rates mean."
    ]
    
    # Select example or custom prompt
    prompt_type = st.radio(
        "Choose a prompt type:",
        ["Example Prompts", "Custom Prompt"],
        index=0,
        horizontal=True
    )
    
    if prompt_type == "Example Prompts":
        user_prompt = st.selectbox("Select an example prompt:", examples)
    else:
        user_prompt = st.text_area(
            "Enter your custom prompt:",
            placeholder="Example: What is the current interest rate in Australia?",
            height=100
        )
    
    # Submit button
    if st.button("Submit Query", key="function_call_submit", type="primary"):
        if not user_prompt:
            st.warning("Please enter a prompt.")
            return
        
        with st.spinner("Creating function call agent..."):
            client, function_agent = create_function_call_agent(st.session_state.api_key)
            
            if not client or not function_agent:
                return
            
            # Add the user message to the history
            if 'function_calls_history' not in st.session_state:
                st.session_state.function_calls_history = []
            
            # Add user message to history
            st.session_state.function_calls_history.append({
                "role": "user",
                "content": user_prompt
            })
            
            try:
                # Start a conversation with the agent
                with st.spinner("Processing your query... This may take a moment."):
                    response = client.beta.conversations.start(
                        agent_id=function_agent.id,
                        inputs=user_prompt
                    )
                
                # Initialize variables to track conversation flow
                conversation_id = response.conversation_id
                current_response = ""
                function_calls = []
                function_results = []
                final_response = ""
                
                # Process initial response and any function calls
                for output in response.outputs:
                    if hasattr(output, 'type') and output.type == "message.output":
                        # Handle string content
                        if isinstance(output.content, str):
                            current_response += output.content
                        # Handle list content
                        elif isinstance(output.content, list):
                            for content_item in output.content:
                                # For dictionary items with get method
                                if hasattr(content_item, 'get'):
                                    if content_item.get("type") == "text":
                                        current_response += content_item.get("text", "")
                                # For objects without get method
                                elif hasattr(content_item, 'type'):
                                    # Handle text content
                                    if content_item.type == "text" and hasattr(content_item, 'text'):
                                        current_response += content_item.text
                    
                    elif hasattr(output, 'type') and output.type == "tool.calls":
                        if hasattr(output, 'tool_calls'):
                            for tool_call in output.tool_calls:
                                if hasattr(tool_call, 'function') and tool_call.function:
                                    # Extract function information safely
                                    function_name = ""
                                    function_args = {}
                                    tool_call_id = ""
                                    
                                    if hasattr(tool_call, 'id'):
                                        tool_call_id = tool_call.id
                                        
                                    if hasattr(tool_call.function, 'name'):
                                        function_name = tool_call.function.name
                                        
                                    if hasattr(tool_call.function, 'arguments'):
                                        try:
                                            # Try to parse arguments as JSON
                                            function_args = json.loads(tool_call.function.arguments)
                                        except:
                                            # If parsing fails, use as string
                                            function_args = {"raw_args": tool_call.function.arguments}
                                    
                                    function_calls.append({
                                        "tool_call_id": tool_call_id,
                                        "function_name": function_name,
                                        "arguments": function_args
                                    })
                
                # Execute function calls and continue conversation
                for function_call in function_calls:
                    function_name = function_call["function_name"]
                    args = function_call["arguments"]
                    result = None
                    
                    # Execute the appropriate function
                    if function_name == "get_interest_rate":
                        region = args.get("region", "")
                        date = args.get("date", None)
                        result = get_interest_rate(region, date)
                    
                    elif function_name == "calculate_loan_payment":
                        principal = args.get("principal", 0)
                        annual_interest_rate = args.get("annual_interest_rate", 0)
                        term_years = args.get("term_years", 0)
                        result = calculate_loan_payment(principal, annual_interest_rate, term_years)
                    
                    if result:
                        function_results.append({
                            "tool_call_id": function_call["tool_call_id"],
                            "function_name": function_name,
                            "result": result
                        })
                        
                        # Continue the conversation with the function result
                        with st.spinner(f"Processing function result for {function_name}..."):
                            continue_response = client.beta.conversations.continued(
                                conversation_id=conversation_id,
                                tool_call_id=function_call["tool_call_id"],
                                result=json.dumps(result)
                            )
                            
                            # Extract the final response
                            for output in continue_response.outputs:
                                if output.type == "message.output":
                                    if isinstance(output.content, str):
                                        final_response += output.content
                                    elif isinstance(output.content, list):
                                        for content_item in output.content:
                                            if content_item.get("type") == "text":
                                                final_response += content_item.get("text", "")
                
                # If there were no function calls, use the initial response
                if not function_calls:
                    final_response = current_response
                
                # Add agent response to history
                st.session_state.function_calls_history.append({
                    "role": "assistant",
                    "content": final_response,
                    "function_calls": function_calls,
                    "function_results": function_results
                })
            
            except Exception as e:
                st.error(f"Error: {str(e)}")
                # Add error message to history
                st.session_state.function_calls_history.append({
                    "role": "assistant",
                    "content": f"Error: {str(e)}",
                    "function_calls": [],
                    "function_results": []
                })
    
    # Display chat history
    st.markdown("### Conversation & Function Calls")
    
    # Create a chat container with scrolling
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.function_calls_history:
            is_user = message["role"] == "user"
            
            # Display the message
            display_chat_message(message["content"], is_user)
            
            # Display function call details for assistant messages
            if not is_user:
                # Show function calls
                if "function_calls" in message and message["function_calls"]:
                    with st.expander("Function Calls", expanded=True):
                        for i, call in enumerate(message["function_calls"]):
                            st.markdown(f"**Function Call {i+1}:** {call['function_name']}")
                            st.markdown("**Arguments:**")
                            st.json(call["arguments"])
                            st.markdown("---")
                
                # Show function results
                if "function_results" in message and message["function_results"]:
                    with st.expander("Function Results", expanded=True):
                        for i, result in enumerate(message["function_results"]):
                            st.markdown(f"**Function Result {i+1}:** {result['function_name']}")
                            st.markdown("**Result:**")
                            
                            # Format the result as a table if it's a suitable type
                            if result['function_name'] == "calculate_loan_payment":
                                # Create a more user-friendly display for loan calculations
                                loan_data = result['result']
                                
                                # Main metrics in columns
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Monthly Payment", f"${loan_data['monthly_payment']}")
                                with col2:
                                    st.metric("Total Interest", f"${loan_data['total_interest']}")
                                with col3:
                                    st.metric("Total Payment", f"${loan_data['total_payment']}")
                                
                                # Additional details
                                st.markdown(f"**Loan Details:**")
                                st.markdown(f"- Principal: ${loan_data['principal']}")
                                st.markdown(f"- Interest Rate: {loan_data['annual_interest_rate']}")
                                st.markdown(f"- Term: {loan_data['term_years']} years ({loan_data['number_of_payments']} payments)")
                                
                            elif result['function_name'] == "get_interest_rate" and "error" not in result['result']:
                                # Create a card-like display for interest rate
                                rate_data = result['result']
                                
                                st.markdown(f"""
                                <div style="padding: 15px; border-radius: 10px; background-color: #f0f7ff; margin-bottom: 10px;">
                                    <h3 style="margin-top: 0;">{rate_data['central_bank']}</h3>
                                    <h2 style="color: #1E88E5;">{rate_data['interest_rate']}</h2>
                                    <p>Region: {rate_data['region']}</p>
                                    <p>Last Updated: {rate_data['last_updated']}</p>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                # Default to JSON display
                                st.json(result["result"])
                            
                            st.markdown("---")
    
    # Clear history button
    if st.session_state.function_calls_history and st.button("Clear History", key="clear_function_calls_history"):
        st.session_state.function_calls_history = []
        st.rerun()
