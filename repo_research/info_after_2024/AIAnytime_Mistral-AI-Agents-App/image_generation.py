import streamlit as st
import json
import base64
import io
from PIL import Image
from mistralai import Mistral
from utils import copy_to_clipboard, download_image_button, display_chat_message

def create_image_agent(api_key):
    """Create an image generation agent using Mistral API"""
    try:
        client = Mistral(api_key=api_key)
        
        image_agent = client.beta.agents.create(
            model="mistral-medium-latest",
            name="Image Generation Agent",
            description="Agent used to generate images based on text prompts.",
            instructions="Use the image generation tool when you have to create images. "
                        "You're excellent at generating detailed, high-quality images from user prompts.",
            tools=[{"type": "image_generation"}],
            completion_args={
                "temperature": 0.7,
                "top_p": 0.95
            }
        )
        
        return client, image_agent
    except Exception as e:
        st.error(f"Failed to create image generation agent: {str(e)}")
        return None, None

def display_image_generation_page():
    st.title("🖼️ Image Generation Agent")
    
    st.markdown("""
    The Image Generation agent allows you to create diverse and detailed images based on text prompts.
    Powered by Black Forest Lab FLUX1.1 [pro] Ultra, this agent can generate a wide range of visual content.
    
    ### Capabilities:
    - Creating artistic images and illustrations
    - Generating visual aids for educational content
    - Designing custom graphics for marketing materials
    - Visualizing concepts and ideas
    
    Try it out with descriptive prompts for the kinds of images you want to generate.
    """)
    
    # API key check
    if not st.session_state.api_key:
        st.warning("Please enter your Mistral API Key in the sidebar to use this feature.")
        return
    
    # Example prompts
    examples = [
        "A futuristic city with flying cars and neon lights at sunset.",
        "A serene mountain landscape with a crystal clear lake reflecting the sky.",
        "An orange cat wearing a business suit in an office.",
        "A steampunk-style robot playing a violin on a Victorian street.",
        "A magical library with floating books and glowing orbs of light."
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
            placeholder="Example: A beautiful Japanese garden with cherry blossoms and a small bridge over a koi pond.",
            height=100
        )
    
    # Submit button
    if st.button("Generate Image", key="image_submit", type="primary"):
        if not user_prompt:
            st.warning("Please enter a prompt.")
            return
        
        with st.spinner("Creating image generation agent..."):
            client, image_agent = create_image_agent(st.session_state.api_key)
            
            if not client or not image_agent:
                return
            
            # Add the user message to the history
            if 'image_generation_history' not in st.session_state:
                st.session_state.image_generation_history = []
            
            # Add user message to history
            st.session_state.image_generation_history.append({
                "role": "user",
                "content": user_prompt
            })
            
            try:
                # Start a conversation with the agent
                with st.spinner("Generating image... This may take a moment."):
                    response = client.beta.conversations.start(
                        agent_id=image_agent.id,
                        inputs=user_prompt
                    )
                
                # Extract and process the agent's response
                response_text = ""
                image_file_id = None
                image_file_name = None
                image_file_type = None
                
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
                                    elif content_item.get("type") == "tool_file" and content_item.get("tool") == "image_generation":
                                        image_file_id = content_item.get("file_id")
                                        image_file_name = content_item.get("file_name")
                                        image_file_type = content_item.get("file_type")
                                # For objects without get method
                                elif hasattr(content_item, 'type'):
                                    # Handle text content
                                    if content_item.type == "text" and hasattr(content_item, 'text'):
                                        response_text += content_item.text
                                    # Handle tool_file content
                                    elif content_item.type == "tool_file" and hasattr(content_item, 'tool'):
                                        if content_item.tool == "image_generation":
                                            if hasattr(content_item, 'file_id'):
                                                image_file_id = content_item.file_id
                                            if hasattr(content_item, 'file_name'):
                                                image_file_name = content_item.file_name
                                            if hasattr(content_item, 'file_type'):
                                                image_file_type = content_item.file_type
                
                # Download the image if file_id is available
                image_data = None
                if image_file_id:
                    with st.spinner("Downloading generated image..."):
                        try:
                            file_response = client.beta.files.download(file_id=image_file_id)
                            image_data = file_response.read()
                        except Exception as e:
                            st.error(f"Failed to download image: {str(e)}")
                
                # Add agent response to history
                st.session_state.image_generation_history.append({
                    "role": "assistant",
                    "content": response_text,
                    "image_data": image_data,
                    "image_file_name": image_file_name,
                    "image_file_type": image_file_type
                })
            
            except Exception as e:
                st.error(f"Error: {str(e)}")
                # Add error message to history
                st.session_state.image_generation_history.append({
                    "role": "assistant",
                    "content": f"Error: {str(e)}",
                    "image_data": None
                })
    
    # Display chat history
    st.markdown("### Conversation & Generated Images")
    
    # Create a chat container with scrolling
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.image_generation_history:
            is_user = message["role"] == "user"
            
            # Display the message
            display_chat_message(message["content"], is_user)
            
            # Display image for assistant messages
            if not is_user and "image_data" in message and message["image_data"]:
                try:
                    # Create a unique key for this image
                    image_key = f"img_{hash(message['content'])}"
                    
                    # Convert bytes to PIL Image
                    image = Image.open(io.BytesIO(message["image_data"]))
                    
                    # Display the image
                    st.image(image, caption="Generated Image", use_column_width=True)
                    
                    # Add download button for the image
                    if message.get("image_file_name") and message.get("image_file_type"):
                        filename = f"{message['image_file_name']}.{message['image_file_type']}"
                        download_image_button(message["image_data"], filename, "Download Image")
                except Exception as e:
                    st.error(f"Error displaying image: {str(e)}")
    
    # Clear history button
    if st.session_state.image_generation_history and st.button("Clear History", key="clear_image_history"):
        st.session_state.image_generation_history = []
        st.rerun()
