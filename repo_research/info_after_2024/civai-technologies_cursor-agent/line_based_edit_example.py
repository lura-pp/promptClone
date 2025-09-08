#!/usr/bin/env python3

import os
import sys
import json
import logging
import asyncio
from pathlib import Path

# Add the parent directory to the path to import the agent module
script_dir = Path(__file__).parent
parent_dir = script_dir.parent
sys.path.append(str(parent_dir))

from cursor_agent_tools import create_agent
from cursor_agent_tools import BaseAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set cursor_agent_tools.tools.file_tools logger to DEBUG
file_tools_logger = logging.getLogger("cursor_agent_tools.tools.file_tools")
file_tools_logger.setLevel(logging.DEBUG)

# Create a temporary directory for testing
temp_dir = Path("./temp_line_edit_test").resolve()  # Get absolute path
temp_dir.mkdir(exist_ok=True)

# Create a test file with absolute path
test_file = temp_dir / "test_file.py"
test_file = test_file.resolve()  # Get absolute path
test_file_content = """#!/usr/bin/env python3

def hello_world():
    print("Hello, World!")

def add(a, b):
    # Add two numbers
    return a + b

def multiply(a, b):
    # Multiply two numbers
    return a * b

def main():
    hello_world()
    result1 = add(5, 3)
    result2 = multiply(4, 2)
    print(f"Addition result: {result1}")
    print(f"Multiplication result: {result2}")

if __name__ == "__main__":
    main()
"""

async def main():
    """
    Demonstrate the line-based editing feature using a real agent implementation.
    
    Line-based editing allows precise modifications to specific line ranges
    using a JSON dictionary where keys are line ranges (e.g., "1-5", "7-7")
    and values are the new content for those ranges.
    """
    # Create a test file
    with open(test_file, "w") as f:
        f.write(test_file_content)
    logger.info(f"Created test file at {test_file}")
    
    # Define a system prompt that emphasizes line-based editing with JSON examples
    system_prompt = """You are an expert coding assistant that specializes in precise line-based editing of files.

IMPORTANT: When using the edit_file tool, you MUST provide the code_edit parameter as a proper JSON dictionary string.
The keys should be line ranges (e.g., "6-8") and the values should be the new content for those ranges.

For example, to edit lines 6-8 of a file, you would use:
```
{
  "6-8": "def add(a, b):\\n    # Add two numbers with validation\\n    return a + b"
}
```

Another example for multiple edits:
```
{
  "6-8": "def add(a, b):\\n    # Add two numbers with validation\\n    return a + b",
  "10-12": "def multiply(a, b):\\n    # Multiply two numbers with validation\\n    return a * b"
}
```

To add a new function after line 12, you would use:
```
{
  "12-12": "\\n\\ndef divide(a, b):\\n    # Divide two numbers\\n    if b == 0:\\n        raise ZeroDivisionError(\\"Division by zero\\")\\n    return a / b"
}
```

For complete file replacement, use the code_replace parameter instead.

Always read the file first to determine the correct line numbers."""
    
    # Initialize a real agent with the custom system prompt
    agent = create_agent(model="gpt-4o", system_prompt=system_prompt)
    
    # Register default tools (including file operations)
    agent.register_default_tools()
    
    # Example: Single prompt to edit multiply function
    logger.info("Testing line-based editing with a single function")
    
    prompt = f"""
Read {test_file} and then update the multiply function to add input validation and better documentation.
You need to find the exact line numbers for the multiply function first.

After finding the line numbers, use the edit_file tool with the following parameters:
1. target_file: The absolute path to the file
2. instructions: A brief description of what you're changing
3. code_edit: A JSON dictionary with line ranges as keys and new content as values

Example of how to use edit_file:
```python
edit_file(
    target_file="/path/to/file.py",
    instructions="Update multiply function with validation",
    code_edit={{"10-12": "def multiply(a, b):\\n    # Multiply two numbers with validation\\n    # Parameters: a, b - numeric values to multiply\\n    # Returns: The product of a and b\\n    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):\\n        raise TypeError(\\"Both arguments must be numbers\\")\\n    return a * b"}}
)
```

Do NOT use code_replace as that would replace the entire file.
"""
    
    response = await agent.chat(prompt)
    logger.info(f"Agent response: {response}")
    
    # Display the edited file
    with open(test_file, "r") as f:
        edited_content = f.read()
        logger.info("File after edit:")
        logger.info(edited_content)
    
    # Verify changes were made correctly
    with open(test_file, "r") as f:
        final_content = f.read()
        multiply_improved = "def multiply" in final_content and any(term in final_content for term in ["validation", "parameter", "input"])
        logger.info(f"Multiply function was improved: {multiply_improved}")
    
    # Clean up
    if input("Do you want to clean up the temporary directory? (y/n): ").lower() == "y":
        import shutil
        shutil.rmtree(temp_dir)
        logger.info(f"Removed temporary directory {temp_dir}")


if __name__ == "__main__":
    asyncio.run(main())