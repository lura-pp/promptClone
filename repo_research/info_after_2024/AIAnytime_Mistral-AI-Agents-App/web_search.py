import streamlit as st
import json
from mistralai import Mistral
from utils import copy_to_clipboard, download_button, display_chat_message

def create_web_search_agent(api_key, premium=False):
    """Create a web search agent using Mistral API"""
    try:
        client = Mistral(api_key=api_key)
        
        tool_type = "web_search_premium" if premium else "web_search"
        
        web_search_agent = client.beta.agents.create(
            model="mistral-medium-latest",
            name="Web Search Agent",
            description="Agent used to search information over the web.",
            instructions="You have the ability to perform web searches to find up-to-date information. "
                        "Always cite your sources and provide factual, accurate information.",
            tools=[{"type": tool_type}],
            completion_args={
                "temperature": 0.3,
                "top_p": 0.95
            }
        )
        
        return client, web_search_agent
    except Exception as e:
        st.error(f"Failed to create web search agent: {str(e)}")
        return None, None

def display_web_search_page():
    st.title("🔍 Web Search Agent")
    
    st.markdown("""
    The Web Search agent allows you to access the latest information from the internet, overcoming 
    the knowledge cut-off limitations of language models. This agent can search the web to answer 
    your questions with up-to-date information.
    
    ### Capabilities:
    - Retrieving the latest information on a variety of topics
    - Accessing specific websites and news sources
    - Providing factual answers with source citations
    - Significantly improving performance on knowledge-intensive tasks
    
    Try it out with questions about current events, recent developments, or factual queries.
    """)
    
    # API key check
    if not st.session_state.api_key:
        st.warning("Please enter your Mistral API Key in the sidebar to use this feature.")
        return
    
    # Choose between standard and premium web search
    search_type = st.radio(
        "Choose search type:",
        ["Standard Web Search", "Premium Web Search (includes news agencies)"],
        index=0,
        horizontal=True,
        help="Premium includes access to news agencies such as AFP and AP"
    )
    
    premium = search_type == "Premium Web Search (includes news agencies)"
    
    # Example prompts
    examples = [
        "What are the latest developments in AI?",
        "Who won the most recent Olympic Games?",
        "What is the current status of space exploration?",
        "What are the recent breakthroughs in renewable energy?",
        "What are the latest major global economic trends?"
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
            placeholder="Example: What are the latest advancements in quantum computing?",
            height=100
        )
    
    # Submit button
    if st.button("Search Web", key="web_search_submit", type="primary"):
        if not user_prompt:
            st.warning("Please enter a prompt.")
            return
        
        with st.spinner(f"Creating {'premium ' if premium else ''}web search agent..."):
            client, web_search_agent = create_web_search_agent(st.session_state.api_key, premium)
            
            if not client or not web_search_agent:
                return
            
            # Add the user message to the history
            if 'web_search_history' not in st.session_state:
                st.session_state.web_search_history = []
            
            # Add user message to history
            st.session_state.web_search_history.append({
                "role": "user",
                "content": user_prompt
            })
            
            try:
                # Start a conversation with the agent
                with st.spinner("Searching the web... This may take a moment."):
                    response = client.beta.conversations.start(
                        agent_id=web_search_agent.id,
                        inputs=user_prompt
                    )
                
                # Extract and process the agent's response
                response_text = ""
                sources = []
                
                for output in response.outputs:
                    if hasattr(output, 'type') and output.type == "message.output":
                        # Handle string content
                        if isinstance(output.content, str):
                            response_text += output.content
                        # Handle list content
                        elif isinstance(output.content, list):
                            for content_item in output.content:
                                # For dictionary items with get method
                                if hasattr(content_item, 'get'):
                                    if content_item.get("type") == "text":
                                        response_text += content_item.get("text", "")
                                    elif content_item.get("type") == "tool_reference" and content_item.get("tool") in ["web_search", "web_search_premium"]:
                                        sources.append({
                                            "title": content_item.get("title", ""),
                                            "url": content_item.get("url", ""),
                                            "source": content_item.get("source", "")
                                        })
                                # For objects without get method
                                elif hasattr(content_item, 'type'):
                                    # Handle text content
                                    if content_item.type == "text" and hasattr(content_item, 'text'):
                                        response_text += content_item.text
                                    # Handle tool_reference content
                                    elif content_item.type == "tool_reference" and hasattr(content_item, 'tool'):
                                        if hasattr(content_item, 'tool') and content_item.tool in ["web_search", "web_search_premium"]:
                                            source_info = {}
                                            if hasattr(content_item, 'title'):
                                                source_info["title"] = content_item.title
                                            else:
                                                source_info["title"] = ""
                                                
                                            if hasattr(content_item, 'url'):
                                                source_info["url"] = content_item.url
                                            else:
                                                source_info["url"] = ""
                                                
                                            if hasattr(content_item, 'source'):
                                                source_info["source"] = content_item.source
                                            else:
                                                source_info["source"] = ""
                                                
                                            sources.append(source_info)
                
                # Add agent response to history
                st.session_state.web_search_history.append({
                    "role": "assistant",
                    "content": response_text,
                    "sources": sources
                })
            
            except Exception as e:
                st.error(f"Error: {str(e)}")
                # Add error message to history
                st.session_state.web_search_history.append({
                    "role": "assistant",
                    "content": f"Error: {str(e)}",
                    "sources": []
                })
    
    # Display chat history
    st.markdown("### Conversation History")
    
    # Create a chat container with scrolling
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.web_search_history:
            is_user = message["role"] == "user"
            
            # Display the message
            display_chat_message(message["content"], is_user)
            
            # Display sources for assistant messages
            if not is_user and "sources" in message and message["sources"]:
                with st.expander("Sources", expanded=True):
                    for i, source in enumerate(message["sources"]):
                        st.markdown(f"**Source {i+1}:** {source['title']}")
                        st.markdown(f"**URL:** [{source['url']}]({source['url']})")
                        st.markdown(f"**Provider:** {source['source']}")
                        st.markdown("---")
    
    # Clear history button
    if st.session_state.web_search_history and st.button("Clear History", key="clear_web_search_history"):
        st.session_state.web_search_history = []
        st.rerun()
