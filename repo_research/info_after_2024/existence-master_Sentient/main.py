import os
import asyncio
import json
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP, Context
from qwen_agent.agents import Assistant
from json_extractor import JsonExtractor
from fastmcp.utilities.logging import configure_logging, get_logger

from . import auth, prompts, utils

# --- Standardized Logging Setup ---
configure_logging(level="INFO")
logger = get_logger(__name__)

# --- LLM and Environment Configuration ---
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev-local')
if ENVIRONMENT == 'dev-local':
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)

OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE_URL", "http://localhost:11434/v1/")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "qwen3:4b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "ollama")

def get_generator_agent(username: str):
    system_prompt = prompts.JSON_GENERATOR_SYSTEM_PROMPT.format(username=username)
    llm_cfg = {
        'model': OPENAI_MODEL_NAME,
        'model_server': OPENAI_API_BASE_URL,
        'api_key': OPENAI_API_KEY,
    }
    return Assistant(llm=llm_cfg, system_message=system_prompt, function_list=[])

mcp = FastMCP(
    name="GSlidesServer",
    instructions="Provides a two-step workflow to generate and create complete Google Slides presentations from a simple topic.",
)

@mcp.resource("prompt://gslides-agent-system")
def get_gslides_system_prompt() -> str:
    return prompts.MAIN_AGENT_SYSTEM_PROMPT

@mcp.tool()
async def generate_presentation_json(ctx: Context, topic: str, previous_tool_response: Optional[str] = "{}") -> Dict[str, Any]:
    """
    Step 1 of 2 for creating a presentation. Generates a structured JSON outline for a presentation based on a given `topic`.
    An internal AI designs the slide titles, content, and suggests images or charts. The output is used by `execute_presentation_creation`.
    """
    logger.info(f"Executing tool: generate_presentation_json with topic='{topic}'")
    try:
        user_id = auth.get_user_id_from_context(ctx)
        user_profile = await auth.users_collection.find_one({"user_id": user_id})
        username = user_profile.get("userData", {}).get("personalInfo", {}).get("name", "User") if user_profile else "User"

        agent = get_generator_agent(username)
        # Correctly pass the username to the internal prompt
        user_prompt = prompts.gslides_internal_user_prompt.format(
            topic=topic,
            username=username,
            previous_tool_response=previous_tool_response
        )
        messages = [{'role': 'user', 'content': user_prompt}]
        
        final_content_str = ""
        for chunk in agent.run(messages=messages):
            if isinstance(chunk, list) and chunk:
                last_message = chunk[-1]
                if last_message.get("role") == "assistant" and isinstance(last_message.get("content"), str):
                    final_content_str = last_message["content"]
        
        if not final_content_str:
            raise Exception("The presentation generator agent returned an empty response.")
        
        outline_json_obj = JsonExtractor.extract_valid_json(final_content_str)
        if not outline_json_obj:
            raise Exception(f"Generator agent failed to produce valid JSON. Response: {final_content_str}")

        return {"status": "success", "result": {"outline_json": json.dumps(outline_json_obj)}}
    except Exception as e:
        logger.error(f"Tool generate_presentation_json failed: {e}", exc_info=True)
        return {"status": "failure", "error": str(e)}

@mcp.tool()
async def execute_presentation_creation(ctx: Context, outline_json: str) -> Dict[str, Any]:
    """
    Step 2 of 2 for creating a presentation. Takes the `outline_json` from `generate_presentation_json` and builds the actual Google Slides file, populating it with titles, content, and images.
    """
    logger.info(f"Executing tool: execute_presentation_creation")
    try:
        user_id = auth.get_user_id_from_context(ctx)
        creds = await auth.get_google_creds(user_id)
        slides_service = auth.authenticate_gslides(creds)
        drive_service = auth.authenticate_gdrive(creds)
        
        outline = JsonExtractor.extract_valid_json(outline_json)
        if not outline:
            raise ToolError("Invalid outline_json provided.")

        presentation_result = await utils.create_presentation_from_outline(
            slides_service, drive_service, outline
        )
        
        return presentation_result
    except Exception as e:
        logger.error(f"Tool execute_presentation_creation failed: {e}", exc_info=True)
        return {"status": "failure", "error": str(e)}

if __name__ == "__main__":
    host = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_SERVER_PORT", 9014))
    
    print(f"Starting GSlides MCP Server on http://{host}:{port}")
    mcp.run(transport="sse", host=host, port=port)