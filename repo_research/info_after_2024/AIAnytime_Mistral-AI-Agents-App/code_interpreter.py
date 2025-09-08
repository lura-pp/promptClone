import streamlit as st
import json
from mistralai import Mistral
import pandas as pd
import matplotlib.pyplot as plt
import io
from PIL import Image
import base64
from utils import copy_to_clipboard, download_button, display_chat_message

def create_code_agent(api_key):
    """Create a code interpreter agent using Mistral API"""
    try:
        client = Mistral(api_key=api_key)
        
        code_agent = client.beta.agents.create(
            model="mistral-medium-latest",
            name="Code Interpreter Agent",
            description="Agent used to execute code using the interpreter tool.",
            instructions="Use the code interpreter tool when you have to run code. "
                        "You're excellent at data analysis, visualization, and solving computational problems.",
            tools=[{"type": "code_interpreter"}],
            completion_args={
                "temperature": 0.3,
                "top_p": 0.95
            }
        )
        
        return client, code_agent
    except Exception as e:
        st.error(f"Failed to create code agent: {str(e)}")
        return None, None

def display_code_interpreter_page():
    st.title("💻 Code Interpreter Agent")
    
    st.markdown("""
    The Code Interpreter agent allows you to execute Python code in a secure sandbox environment. 
    This is invaluable for tasks requiring computation, data manipulation, or visualization.
    
    ### Capabilities:
    - Mathematical calculation and analysis
    - Data visualization and plotting
    - Scientific computing and simulation
    - Code validation and execution
    
    Try it out with examples like generating Fibonacci sequences, plotting data, or solving mathematical problems.
    """)
    
    # API key check
    if not st.session_state.api_key:
        st.warning("Please enter your Mistral API Key in the sidebar to use this feature.")
        return
    
    # Example prompts
    examples = [
        "Generate the first 20 numbers of the Fibonacci sequence and plot them.",
        "Create a scatter plot with random data and add a trend line.",
        "Calculate the first 50 prime numbers and visualize their distribution.",
        "Create a DataFrame with sample sales data and calculate monthly averages.",
        "Simulate a random walk and visualize it as an animated plot."
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
            placeholder="Example: Analyze a sample dataset with 100 random points and create a histogram of the distribution.",
            height=100
        )
    
    # Submit button
    if st.button("Submit", key="code_submit", type="primary"):
        if not user_prompt:
            st.warning("Please enter a prompt.")
            return
        
        with st.spinner("Creating code interpreter agent..."):
            client, code_agent = create_code_agent(st.session_state.api_key)
            
            if not client or not code_agent:
                return
            
            # Add the user message to the history
            if 'code_interpreter_history' not in st.session_state:
                st.session_state.code_interpreter_history = []
            
            # Add user message to history
            st.session_state.code_interpreter_history.append({
                "role": "user",
                "content": user_prompt
            })
            
            try:
                # Start a conversation with the agent
                with st.spinner("Generating response..."):
                    response = client.beta.conversations.start(
                        agent_id=code_agent.id,
                        inputs=user_prompt
                    )
                
                # Extract and process the agent's response
                code_blocks = []
                outputs = []
                final_text = ""
                
                # Process the response more carefully
                for output in response.outputs:
                    # Handle message outputs
                    if hasattr(output, 'type') and output.type == "message.output":
                        # Handle string content
                        if isinstance(output.content, str):
                            final_text += output.content
                        # Handle list content
                        elif isinstance(output.content, list):
                            for content_item in output.content:
                                # For dictionary items with get method
                                if hasattr(content_item, 'get'):
                                    if content_item.get("type") == "text":
                                        final_text += content_item.get("text", "")
                                # For objects without get method (like ToolFileChunk)
                                elif hasattr(content_item, 'type') and content_item.type == "text":
                                    if hasattr(content_item, 'text'):
                                        final_text += content_item.text
                    
                    # Handle tool executions
                    elif hasattr(output, 'type') and output.type == "tool.execution":
                        if hasattr(output, 'name') and output.name == "code_interpreter":
                            # Handle tool info safely
                            if hasattr(output, 'info'):
                                info = output.info
                                code = ""
                                code_output = ""
                                
                                # Get code and output safely
                                if hasattr(info, 'code'):
                                    code = info.code
                                elif hasattr(info, 'get') and info.get("code"):
                                    code = info.get("code")
                                    
                                if hasattr(info, 'code_output'):
                                    code_output = info.code_output
                                elif hasattr(info, 'get') and info.get("code_output"):
                                    code_output = info.get("code_output")
                                    
                                code_blocks.append({
                                    "code": code,
                                    "output": code_output
                                })
                
                # Add agent response to history
                st.session_state.code_interpreter_history.append({
                    "role": "assistant",
                    "content": final_text,
                    "code_blocks": code_blocks
                })
            
            except Exception as e:
                st.error(f"Error: {str(e)}")
                # Add error message to history
                st.session_state.code_interpreter_history.append({
                    "role": "assistant",
                    "content": f"Error: {str(e)}",
                    "code_blocks": []
                })
    
    # Display chat history
    st.markdown("### Conversation History")
    
    # Create a chat container with scrolling
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.code_interpreter_history:
            is_user = message["role"] == "user"
            
            # Display the message
            display_chat_message(message["content"], is_user)
            
            # Display code blocks for assistant messages
            if not is_user and "code_blocks" in message and message["code_blocks"]:
                for i, code_block in enumerate(message["code_blocks"]):
                    with st.expander(f"Code Execution {i+1}", expanded=True):
                        st.markdown("**Code:**")
                        st.code(code_block["code"], language="python")
                        
                        # Add copy code button
                        copy_to_clipboard(code_block["code"], "Copy Code")
                        
                        st.markdown("**Output:**")
                        st.code(code_block["output"])
                        
                        # Try to detect if the output contains an image (matplotlib plot)
                        if "savefig" in code_block["code"] or "plt.show()" in code_block["code"]:
                            st.info("Note: Visualizations executed in the Mistral sandbox are not directly visible here. The output shows text representation only.")
    
    # Clear history button
    if st.session_state.code_interpreter_history and st.button("Clear History", key="clear_code_history"):
        st.session_state.code_interpreter_history = []
        st.rerun()
