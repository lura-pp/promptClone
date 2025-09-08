import streamlit as st
import json
from mistralai import Mistral
from utils import copy_to_clipboard, download_button, display_chat_message

def create_orchestration_agents(api_key):
    """Create multiple specialized agents for orchestration"""
    try:
        client = Mistral(api_key=api_key)
        
        # Create the main finance agent that can hand off to other agents
        finance_agent = client.beta.agents.create(
            model="mistral-large-latest",
            name="Finance Agent",
            description="Agent specialized in financial analysis and advice",
            instructions="You're an expert in finance who can analyze financial data, provide investment advice, "
                       "and explain financial concepts. You can hand off specialized tasks to other agents.",
            completion_args={
                "temperature": 0.3,
                "top_p": 0.95
            }
        )
        
        # Create a web search agent for retrieving current information
        web_search_agent = client.beta.agents.create(
            model="mistral-medium-latest",
            name="Web Search Agent",
            description="Agent used to search information over the web",
            instructions="You search the web for the latest financial data and market information.",
            tools=[{"type": "web_search"}],
            completion_args={
                "temperature": 0.3,
                "top_p": 0.95
            }
        )
        
        # Create a calculator agent for financial calculations
        calculator_agent = client.beta.agents.create(
            model="mistral-medium-latest",
            name="Calculator Agent",
            description="Agent used for complex financial calculations",
            instructions="You perform financial calculations using the code interpreter.",
            tools=[{"type": "code_interpreter"}],
            completion_args={
                "temperature": 0.3,
                "top_p": 0.95
            }
        )
        
        # Create a graph plotting agent
        graph_agent = client.beta.agents.create(
            model="mistral-medium-latest",
            name="Graph Agent",
            description="Agent used to create visual representations of financial data",
            instructions="You create graphs and visualizations of financial data.",
            tools=[{"type": "code_interpreter"}],
            completion_args={
                "temperature": 0.3,
                "top_p": 0.95
            }
        )
        
        # Set up handoffs for the finance agent
        client.beta.agents.update(
            agent_id=finance_agent.id,
            handoffs=[web_search_agent.id, calculator_agent.id, graph_agent.id]
        )
        
        # Set up handoffs for the web search agent
        client.beta.agents.update(
            agent_id=web_search_agent.id,
            handoffs=[calculator_agent.id, graph_agent.id]
        )
        
        # Set up handoffs for the calculator agent
        client.beta.agents.update(
            agent_id=calculator_agent.id,
            handoffs=[graph_agent.id]
        )
        
        return client, finance_agent, {
            "finance": finance_agent.id,
            "web_search": web_search_agent.id,
            "calculator": calculator_agent.id,
            "graph": graph_agent.id
        }
    
    except Exception as e:
        st.error(f"Failed to create orchestration agents: {str(e)}")
        return None, None, None

def display_agent_orchestration_page():
    st.title("🔄 Agent Orchestration")
    
    st.markdown("""
    Agent Orchestration allows multiple specialized agents to collaborate on complex, multi-faceted problems.
    Each agent brings their own capabilities and can hand off tasks to other agents as needed.
    
    ### How it works:
    1. Your request is sent to a primary agent
    2. The primary agent may delegate parts of the task to specialized agents
    3. Each specialized agent performs its part and returns results
    4. The primary agent consolidates the results into a comprehensive response
    
    This demonstration uses a financial advisory scenario with multiple specialized agents working together.
    """)
    
    # API key check
    if not st.session_state.api_key:
        st.warning("Please enter your Mistral API Key in the sidebar to use this feature.")
        return
    
    # Example prompts
    examples = [
        "What are the current interest rates and how would they affect my investments over the next 5 years?",
        "Compare the performance of tech stocks versus energy stocks over the past year and create a graph.",
        "What is compound interest and how much would $10,000 grow to in 10 years at the current average savings rate?",
        "What are the best retirement investment strategies given the current economic outlook?",
        "Analyze the current inflation rate and show how it impacts different asset classes."
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
            placeholder="Example: How should I diversify my portfolio given the current market conditions?",
            height=100
        )
    
    # Handoff execution options
    handoff_execution = st.radio(
        "Handoff Execution:",
        ["Server-side (automatic)", "Client-side (manual)"],
        index=0,
        horizontal=True,
        help="Server-side handoffs are handled automatically by Mistral's servers. Client-side gives more control but requires manual intervention."
    )
    
    handoff_mode = "server" if handoff_execution == "Server-side (automatic)" else "client"
    
    # Submit button
    if st.button("Start Orchestration", key="orchestration_submit", type="primary"):
        if not user_prompt:
            st.warning("Please enter a prompt.")
            return
        
        with st.spinner("Creating orchestration agents..."):
            client, finance_agent, agent_ids = create_orchestration_agents(st.session_state.api_key)
            
            if not client or not finance_agent or not agent_ids:
                return
            
            # Add the user message to the history
            if 'orchestration_history' not in st.session_state:
                st.session_state.orchestration_history = []
            
            # Add user message to history
            st.session_state.orchestration_history.append({
                "role": "user",
                "content": user_prompt
            })
            
            try:
                # Start a conversation with the primary agent
                with st.spinner("Processing your request with multiple agents... This may take a moment."):
                    response = client.beta.conversations.start(
                        agent_id=finance_agent.id,
                        inputs=user_prompt,
                        handoff_execution=handoff_mode
                    )
                
                # Extract and process the agent's response
                primary_response = ""
                handoffs = []
                tool_executions = []
                
                for output in response.outputs:
                    if hasattr(output, 'type') and output.type == "message.output":
                        # Handle string content
                        if isinstance(output.content, str):
                            primary_response += output.content
                        # Handle list content
                        elif isinstance(output.content, list):
                            for content_item in output.content:
                                # For dictionary items with get method
                                if hasattr(content_item, 'get'):
                                    if content_item.get("type") == "text":
                                        primary_response += content_item.get("text", "")
                                # For objects without get method
                                elif hasattr(content_item, 'type'):
                                    # Handle text content
                                    if content_item.type == "text" and hasattr(content_item, 'text'):
                                        primary_response += content_item.text
                    
                    # Track handoffs
                    elif hasattr(output, 'type') and output.type == "handoff.execution":
                        handoff_agent_id = ""
                        handoff_inputs = ""
                        
                        if hasattr(output, 'agent_id'):
                            handoff_agent_id = output.agent_id
                        
                        if hasattr(output, 'inputs'):
                            handoff_inputs = output.inputs
                            
                        handoff_agent_name = next((name for name, id in agent_ids.items() if id == handoff_agent_id), "Unknown Agent")
                        
                        handoffs.append({
                            "agent_name": handoff_agent_name,
                            "agent_id": handoff_agent_id,
                            "inputs": handoff_inputs
                        })
                    
                    # Track tool executions
                    elif hasattr(output, 'type') and output.type == "tool.execution":
                        tool_name = ""
                        tool_info = {}
                        
                        if hasattr(output, 'name'):
                            tool_name = output.name
                            
                        if hasattr(output, 'info'):
                            # Process tool info safely
                            if hasattr(output.info, '__dict__'):
                                # Convert object to dict
                                try:
                                    tool_info = output.info.__dict__
                                except:
                                    # If that fails, use empty dict
                                    tool_info = {}
                            else:
                                # Use the info directly
                                tool_info = output.info
                                
                        tool_executions.append({
                            "tool_name": tool_name,
                            "info": tool_info
                        })
                
                # Add agent response to history
                st.session_state.orchestration_history.append({
                    "role": "assistant",
                    "content": primary_response,
                    "handoffs": handoffs,
                    "tool_executions": tool_executions
                })
            
            except Exception as e:
                st.error(f"Error: {str(e)}")
                # Add error message to history
                st.session_state.orchestration_history.append({
                    "role": "assistant",
                    "content": f"Error: {str(e)}",
                    "handoffs": [],
                    "tool_executions": []
                })
    
    # Display chat history
    st.markdown("### Conversation & Orchestration Flow")
    
    # Create a chat container with scrolling
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.orchestration_history:
            is_user = message["role"] == "user"
            
            # Display the message
            display_chat_message(message["content"], is_user)
            
            # Display orchestration details for assistant messages
            if not is_user:
                # Show handoffs
                if "handoffs" in message and message["handoffs"]:
                    with st.expander("Agent Handoffs", expanded=True):
                        for i, handoff in enumerate(message["handoffs"]):
                            st.markdown(f"**Handoff {i+1}:** Primary Agent → {handoff['agent_name']}")
                            st.markdown(f"**Input:** {handoff['inputs']}")
                            st.markdown("---")
                
                # Show tool executions
                if "tool_executions" in message and message["tool_executions"]:
                    with st.expander("Tool Executions", expanded=True):
                        for i, tool in enumerate(message["tool_executions"]):
                            st.markdown(f"**Tool {i+1}:** {tool['tool_name']}")
                            
                            # Show code interpreter executions
                            if tool["tool_name"] == "code_interpreter" and "code" in tool.get("info", {}):
                                st.markdown("**Code:**")
                                st.code(tool["info"]["code"], language="python")
                                
                                st.markdown("**Output:**")
                                st.code(tool["info"].get("code_output", "No output"))
                            
                            st.markdown("---")
    
    # Clear history button
    if st.session_state.orchestration_history and st.button("Clear History", key="clear_orchestration_history"):
        st.session_state.orchestration_history = []
        st.rerun()
