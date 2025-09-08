# memory/use_memory.py
from .force_faiss_config import force_faiss_config
from strands.agent import Agent
from strands import tool
from ...utils.model import get_model
from .user_id_manager import get_persistent_user_id
import json
import sys
import io
import logging


# Initialize configuration (Monkey Patch before tool import)
force_faiss_config()


from strands_tools import mem0_memory



# Global memory agent instance
_memory_agent = None


def _get_memory_agent():
    """Get or create the global memory agent instance."""
    global _memory_agent
    if _memory_agent is None:
        _memory_agent = Agent(
            system_prompt="""You are a memory specialist agent. Store and retrieve information efficiently.""",
            tools=[mem0_memory],
            model=get_model(),
        )
    return _memory_agent


def _silent_memory_operation(operation_func):
    """
    Wrapper to suppress verbose output from mem0_memory tool.
    Captures stdout/stderr and only returns the actual result.
    """
    # Capture stdout and stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    try:
        # Redirect output streams
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        # Execute the operation
        result = operation_func()

        return result

    finally:
        # Always restore original streams
        sys.stdout = old_stdout
        sys.stderr = old_stderr


@tool
def store_memory(content: str) -> str:
    """
    Store important information in persistent memory silently.

    Args:
        content: The information to store in memory

    Returns:
        Simple success/failure message without verbose output
    """
    # Use persistent user ID

    user_id = get_persistent_user_id()

    logging.debug(f"Storing memory for user {user_id} with content: {content}")

    def operation():
        agent = _get_memory_agent()
        return agent.tool.mem0_memory(action="store", content=content, user_id=user_id)

    try:
        result = _silent_memory_operation(operation)

        # Check if result indicates success
        if (isinstance(result, dict) and result.get("status") == "success") or (
            hasattr(result, "status") and result.status == "success"
        ):
            return "stored"  # Simple, quiet confirmation
        else:
            return "failed"

    except Exception:
        return "error"


@tool
def recall_memory(query: str, max_results: int = 5) -> str:
    """
    Retrieve relevant memories based on a search query without verbose output.
    """
    user_id = get_persistent_user_id()
    logging.debug(f"Recalling memory for user {user_id} with query: {query}")

    def operation():
        agent = _get_memory_agent()
        return agent.tool.mem0_memory(action="retrieve", query=query, user_id=user_id)

    try:
        result = _silent_memory_operation(operation)

        if isinstance(result, dict) and result.get("status") == "success":
            content_text = result["content"][0]["text"]
            try:
                memories_data = json.loads(content_text)

                # Much more permissive filtering
                filtered_memories = []
                for mem in memories_data:
                    score = mem.get("score", float("inf"))
                    if score <= 2.0:  # Very permissive threshold
                        filtered_memories.append(mem)

                # If no results with 2.0, show everything
                if not filtered_memories:
                    filtered_memories = memories_data

                # Sort by score (lower is better in FAISS)
                sorted_memories = sorted(
                    filtered_memories, key=lambda x: x.get("score", float("inf"))
                )
                top_memories = sorted_memories[:max_results]

                if not top_memories:
                    return f"No memories found for: '{query}'"

                # Format memories cleanly
                formatted_memories = []
                for i, mem in enumerate(top_memories, 1):
                    memory_text = mem.get("memory", "No content")
                    formatted_memories.append(f"• {memory_text}")

                return f"Relevant memories for '{query}':\n" + "\n".join(
                    formatted_memories
                )

            except json.JSONDecodeError:
                return f"Error parsing memory data for: '{query}'"
        else:
            return f"No memories found for: '{query}'"

    except Exception as e:
        return f"Error retrieving memories: {str(e)}"


@tool
def generate_memory_response(query: str) -> str:
    """
    Generate a contextual response using stored memories as background knowledge quietly.

    Args:
        query: The user's question or request
        user_id: Unique identifier for the user (if None, uses persistent user ID)

    Returns:
        AI-generated response enhanced with relevant stored memories
    """
    # Use persistent user ID

    user_id = get_persistent_user_id()

    def retrieve_operation():
        agent = _get_memory_agent()
        return agent.tool.mem0_memory(action="retrieve", query=query, user_id=user_id)

    try:
        # First, retrieve relevant memories quietly
        result = _silent_memory_operation(retrieve_operation)

        memories_context = ""
        if isinstance(result, dict) and result.get("status") == "success":
            content_text = result["content"][0]["text"]
            try:
                memories_data = json.loads(content_text)

                # Filter for relevant memories
                relevant_memories = []
                for mem in memories_data:
                    score = mem.get("score", float("inf"))
                    if score <= 0.5:  # Good relevance threshold
                        relevant_memories.append(mem)

                if relevant_memories:
                    # Sort by relevance and take top 5
                    sorted_memories = sorted(
                        relevant_memories, key=lambda x: x.get("score", float("inf"))
                    )
                    top_memories = sorted_memories[:5]

                    memories_context = "\n".join(
                        [f"- {mem['memory']}" for mem in top_memories]
                    )

            except json.JSONDecodeError:
                pass

        # Generate response using memory context
        if memories_context:
            prompt = f"""
User ID: {user_id}
User question: "{query}"

Relevant stored memories:
{memories_context}

Please generate a helpful response using the stored memories as context.
Be natural and conversational while incorporating relevant information from memory.
"""
        else:
            prompt = f"""
User ID: {user_id}  
User question: "{query}"

No relevant stored memories found. Please provide a helpful direct response.
"""

        # Use the agent to generate a contextual response (this might still have some output)
        def generate_operation():
            agent = _get_memory_agent()
            return agent(
                prompt=prompt,
                system_prompt="""You are an assistant that creates helpful responses based on retrieved memories.
Use the provided memories to create a natural, conversational response to the user's question.""",
            )

        response = _silent_memory_operation(generate_operation)
        return str(response["content"][0]["text"])

    except Exception as e:
        return f"Error generating memory-enhanced response: {str(e)}"


@tool
def list_recent_memories(limit: int = 10) -> str:
    """
    List recent memories for review without verbose output.

    Args:
        user_id: Unique identifier for the user (if None, uses persistent user ID)
        limit: Maximum number of recent memories to show (default: 10)

    Returns:
        Clean formatted list of recent memories
    """
    # Use persistent user ID

    user_id = get_persistent_user_id()

    def operation():
        agent = _get_memory_agent()
        return agent.tool.mem0_memory(action="list", user_id=user_id)

    try:
        result = _silent_memory_operation(operation)

        # Check if result is a dict with status key OR has status attribute
        if (isinstance(result, dict) and result.get("status") == "success") or (
            hasattr(result, "status") and result.status == "success"
        ):
            try:
                # Handle both dict and object formats
                if isinstance(result, dict):
                    content_text = result["content"][0]["text"]
                else:
                    content_text = result.content[0].text

                memories_data = json.loads(content_text)

                if not memories_data:
                    return f"No memories found for user: {user_id}"

                # Show most recent memories (limit the output)
                recent_memories = (
                    memories_data[-limit:]
                    if len(memories_data) > limit
                    else memories_data
                )

                formatted = []
                for i, mem in enumerate(recent_memories, 1):
                    memory_text = mem.get("memory", "No content")
                    # Truncate long memories for readability
                    truncated = (
                        memory_text[:100] + "..."
                        if len(memory_text) > 100
                        else memory_text
                    )
                    formatted.append(f"{i}. {truncated}")

                return (
                    f"Recent memories for {user_id} ({len(recent_memories)} of {len(memories_data)} total):\n"
                    + "\n".join(formatted)
                )

            except (json.JSONDecodeError, IndexError, KeyError, AttributeError) as e:
                return f"Error parsing memory list: {str(e)}"
        else:
            return f"No memories found for user: {user_id}"

    except Exception as e:
        return f"Error listing memories: {str(e)}"
