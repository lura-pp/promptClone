#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#   "anthropic>=0.45.2",
#   "argparse>=1.4.0",
#   "rich>=13.7.0",
# ]
# ///

"""
Agent with Bash and Editor Tools Example for Claude 3.7 Sonnet

This script demonstrates a complete agent that can execute bash commands and edit files
with extended thinking capabilities. It's based on the Single File Agent pattern.

Usage:
    uv run agent_bash_and_editor_with_extended_thinking.py --prompt "Create a new file called hello.txt with 'Hello World!' in it"
    uv run agent_bash_and_editor_with_extended_thinking.py --prompt "Duplicate whatever text is in hello.txt 10 times on new lines. then create a markdown file, json file, and yaml file with the same content in it formatted for the file type" --max_tokens 4000 --thinking_budget_tokens 2000 --compute 15
    uv run agent_bash_and_editor_with_extended_thinking.py --prompt "List all Python files in the current directory minus this one sorted by size" --max_tokens 4000 --thinking_budget_tokens 2000
    uv run agent_bash_and_editor_with_extended_thinking.py --prompt "Create a new python uv single file script with the header and dependency like the our other python files but leave it empty and just print ready for action" --max_tokens 4000 --thinking_budget_tokens 2000
"""

import os
import sys
import argparse
import json
import traceback
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
import anthropic

# Initialize global console
console = Console()

current_bash_env = os.environ.copy()

AGENT_PROMPT = """<purpose>
    You are an expert integration assistant that can both edit files and execute bash commands.
</purpose>

<instructions>
    <instruction>Use the tools provided to accomplish file editing and bash command execution as needed.</instruction>
    <instruction>When you have completed the user's task, call complete_task to finalize the process.</instruction>
    <instruction>Provide reasoning with every tool call.</instruction>
    <instruction>When constructing paths use /repo to start from the root of the repository. We'll replace it with the current working directory.</instruction>
</instructions>

<tools>
    <tool>
        <name>view_file</name>
        <description>View the content of a file</description>
        <parameters>
            <parameter>
                <name>reasoning</name>
                <type>string</type>
                <description>Why you are viewing the file</description>
                <required>true</required>
            </parameter>
            <parameter>
                <name>path</name>
                <type>string</type>
                <description>Path of the file to view</description>
                <required>true</required>
            </parameter>
        </parameters>
    </tool>

    <tool>
        <name>create_file</name>
        <description>Create a new file with given content</description>
        <parameters>
            <parameter>
                <name>reasoning</name>
                <type>string</type>
                <description>Why the file is being created</description>
                <required>true</required>
            </parameter>
            <parameter>
                <name>path</name>
                <type>string</type>
                <description>Path where to create the file</description>
                <required>true</required>
            </parameter>
            <parameter>
                <name>file_text</name>
                <type>string</type>
                <description>Content for the new file</description>
                <required>true</required>
            </parameter>
        </parameters>
    </tool>

    <tool>
        <name>str_replace</name>
        <description>Replace text in a file</description>
        <parameters>
            <parameter>
                <name>reasoning</name>
                <type>string</type>
                <description>Explain why the replacement is needed</description>
                <required>true</required>
            </parameter>
            <parameter>
                <name>path</name>
                <type>string</type>
                <description>File path</description>
                <required>true</required>
            </parameter>
            <parameter>
                <name>old_str</name>
                <type>string</type>
                <description>The string to be replaced</description>
                <required>true</required>
            </parameter>
            <parameter>
                <name>new_str</name>
                <type>string</type>
                <description>The replacement string</description>
                <required>true</required>
            </parameter>
        </parameters>
    </tool>

    <tool>
        <name>insert_line</name>
        <description>Insert text at a specific line in a file</description>
        <parameters>
            <parameter>
                <name>reasoning</name>
                <type>string</type>
                <description>Reason for inserting the text</description>
                <required>true</required>
            </parameter>
            <parameter>
                <name>path</name>
                <type>string</type>
                <description>File path</description>
                <required>true</required>
            </parameter>
            <parameter>
                <name>insert_line</name>
                <type>integer</type>
                <description>Line number for insertion</description>
                <required>true</required>
            </parameter>
            <parameter>
                <name>new_str</name>
                <type>string</type>
                <description>The text to insert</description>
                <required>true</required>
            </parameter>
        </parameters>
    </tool>

    <tool>
        <name>execute_bash</name>
        <description>Execute a bash command</description>
        <parameters>
            <parameter>
                <name>reasoning</name>
                <type>string</type>
                <description>Explain why this command should be executed</description>
                <required>true</required>
            </parameter>
            <parameter>
                <name>command</name>
                <type>string</type>
                <description>The bash command to run</description>
                <required>true</required>
            </parameter>
        </parameters>
    </tool>

    <tool>
        <name>restart_bash</name>
        <description>Restart the bash session with a fresh environment</description>
        <parameters>
            <parameter>
                <name>reasoning</name>
                <type>string</type>
                <description>Explain why the session is being reset</description>
                <required>true</required>
            </parameter>
        </parameters>
    </tool>

    <tool>
        <name>complete_task</name>
        <description>Finalize the task and exit the agent loop</description>
        <parameters>
            <parameter>
                <name>reasoning</name>
                <type>string</type>
                <description>Explain why the task is complete</description>
                <required>true</required>
            </parameter>
        </parameters>
    </tool>
</tools>

<user-request>
    {{user_request}}
</user-request>
"""

root_path_to_replace_with_cwd = "/repo"


def tool_view_file(tool_input: dict) -> dict:
    try:
        reasoning = tool_input.get("reasoning")
        path = tool_input.get("path")
        if path:
            path = path.replace(root_path_to_replace_with_cwd, os.getcwd())

        if not path or not path.strip():
            error_message = "Invalid file path provided: path is empty."
            console.log(f"[tool_view_file] Error: {error_message}")
            return {"error": error_message}

        console.log(f"[tool_view_file] reasoning: {reasoning}, path: {path}")

        if not os.path.exists(path):
            error_message = f"File {path} does not exist"
            console.log(f"[tool_view_file] Error: {error_message}")
            return {"error": error_message}

        with open(path, "r") as f:
            content = f.read()
        return {"result": content}
    except Exception as e:
        console.log(f"[tool_view_file] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}


def tool_create_file(tool_input: dict) -> dict:
    try:
        reasoning = tool_input.get("reasoning")
        path = tool_input.get("path")
        file_text = tool_input.get("file_text")

        if path:
            path = path.replace(root_path_to_replace_with_cwd, os.getcwd())
        console.log(f"[tool_create_file] reasoning: {reasoning}, path: {path}")

        # Check for an empty or invalid path
        if not path or not path.strip():
            error_message = "Invalid file path provided: path is empty."
            console.log(f"[tool_create_file] Error: {error_message}")
            return {"error": error_message}

        dirname = os.path.dirname(path)
        if not dirname:
            error_message = (
                "Invalid file path provided: directory part of the path is empty."
            )
            console.log(f"[tool_create_file] Error: {error_message}")
            return {"error": error_message}
        else:
            os.makedirs(dirname, exist_ok=True)

        with open(path, "w") as f:
            f.write(file_text or "")
        return {"result": f"File created at {path}"}
    except Exception as e:
        console.log(f"[tool_create_file] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}


def tool_str_replace(tool_input: dict) -> dict:
    try:
        reasoning = tool_input.get("reasoning")
        path = tool_input.get("path")
        old_str = tool_input.get("old_str")
        new_str = tool_input.get("new_str")

        if path:
            path = path.replace(root_path_to_replace_with_cwd, os.getcwd())

        if not path or not path.strip():
            error_message = "Invalid file path provided: path is empty."
            console.log(f"[tool_str_replace] Error: {error_message}")
            return {"error": error_message}

        if not old_str:
            error_message = "No text to replace specified: old_str is empty."
            console.log(f"[tool_str_replace] Error: {error_message}")
            return {"error": error_message}

        console.log(
            f"[tool_str_replace] reasoning: {reasoning}, path: {path}, old_str: {old_str}, new_str: {new_str}"
        )

        if not os.path.exists(path):
            error_message = f"File {path} does not exist"
            console.log(f"[tool_str_replace] Error: {error_message}")
            return {"error": error_message}

        with open(path, "r") as f:
            content = f.read()

        if old_str not in content:
            error_message = f"'{old_str}' not found in {path}"
            console.log(f"[tool_str_replace] Error: {error_message}")
            return {"error": error_message}

        new_content = content.replace(old_str, new_str or "")
        with open(path, "w") as f:
            f.write(new_content)
        return {"result": "Text replaced successfully"}
    except Exception as e:
        console.log(f"[tool_str_replace] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}


def tool_insert_line(tool_input: dict) -> dict:
    try:
        reasoning = tool_input.get("reasoning")
        path = tool_input.get("path")
        insert_line_num = tool_input.get("insert_line")
        new_str = tool_input.get("new_str")

        if path:
            path = path.replace(root_path_to_replace_with_cwd, os.getcwd())

        if not path or not path.strip():
            error_message = "Invalid file path provided: path is empty."
            console.log(f"[tool_insert_line] Error: {error_message}")
            return {"error": error_message}

        if insert_line_num is None:
            error_message = "No line number specified: insert_line is missing."
            console.log(f"[tool_insert_line] Error: {error_message}")
            return {"error": error_message}

        if not new_str:
            error_message = "No text to insert specified: new_str is empty."
            console.log(f"[tool_insert_line] Error: {error_message}")
            return {"error": error_message}

        console.log(
            f"[tool_insert_line] reasoning: {reasoning}, path: {path}, insert_line: {insert_line_num}, new_str: {new_str}"
        )

        if not os.path.exists(path):
            error_message = f"File {path} does not exist"
            console.log(f"[tool_insert_line] Error: {error_message}")
            return {"error": error_message}

        with open(path, "r") as f:
            lines = f.readlines()

        # Check that the index is within acceptable bounds (allowing insertion at end)
        if insert_line_num < 0 or insert_line_num > len(lines):
            error_message = (
                f"Insert line number {insert_line_num} out of range (0-{len(lines)})."
            )
            console.log(f"[tool_insert_line] Error: {error_message}")
            return {"error": error_message}

        lines.insert(insert_line_num, new_str + "\n")
        with open(path, "w") as f:
            f.writelines(lines)
        return {"result": "Line inserted successfully"}
    except Exception as e:
        console.log(f"[tool_insert_line] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}


def tool_execute_bash(tool_input: dict) -> dict:
    try:
        reasoning = tool_input.get("reasoning")
        command = tool_input.get("command")

        if command:
            command = command.replace(root_path_to_replace_with_cwd, os.getcwd())

        if not command or not command.strip():
            error_message = "No command specified: command is empty."
            console.log(f"[tool_execute_bash] Error: {error_message}")
            return {"error": error_message}

        console.log(f"[tool_execute_bash] reasoning: {reasoning}, command: {command}")
        import subprocess

        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, env=current_bash_env
        )
        if result.returncode != 0:
            error_message = (
                result.stderr.strip()
                or "Command execution failed with non-zero exit code."
            )
            console.log(f"[tool_execute_bash] Error: {error_message}")
            return {"error": error_message}
        return {"result": result.stdout.strip()}
    except Exception as e:
        console.log(f"[tool_execute_bash] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}


def tool_restart_bash(tool_input: dict) -> dict:
    global current_bash_env
    try:
        reasoning = tool_input.get("reasoning")

        if not reasoning:
            error_message = "No reasoning provided for restarting bash session."
            console.log(f"[tool_restart_bash] Error: {error_message}")
            return {"error": error_message}

        console.log(f"[tool_restart_bash] reasoning: {reasoning}")
        current_bash_env = os.environ.copy()
        return {"result": "Bash session restarted."}
    except Exception as e:
        console.log(f"[tool_restart_bash] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}


def tool_complete_task(tool_input: dict) -> dict:
    try:
        reasoning = tool_input.get("reasoning")

        if not reasoning:
            error_message = "No reasoning provided for task completion."
            console.log(f"[tool_complete_task] Error: {error_message}")
            return {"error": error_message}

        console.log(f"[tool_complete_task] reasoning: {reasoning}")
        return {"result": "Task completed"}
    except Exception as e:
        console.log(f"[tool_complete_task] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Bash and Editor Agent using Claude 3.7 Sonnet with Extended Thinking"
    )
    parser.add_argument("-p", "--prompt", required=True, help="The prompt to execute")
    parser.add_argument(
        "-c", "--compute", type=int, default=10, help="Maximum compute loops"
    )
    parser.add_argument(
        "--thinking_budget_tokens",
        type=int,
        default=1024,
        help="Budget for thinking tokens (minimum 1024)",
    )
    parser.add_argument(
        "--max_tokens",
        type=int,
        default=4000,
        help="Maximum number of tokens in the response",
    )
    args = parser.parse_args()

    # Validate thinking budget (minimum 1024 tokens)
    if args.thinking_budget_tokens < 1024:
        print("Warning: Minimum thinking budget is 1024 tokens. Setting to 1024.")
        args.thinking_budget_tokens = 1024

    # Get API key from environment variable
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        Console().print(
            "[red]Error: ANTHROPIC_API_KEY environment variable is not set.[/red]"
        )
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Prepare the initial message using the detailed prompt
    initial_message = AGENT_PROMPT.replace("{{user_request}}", args.prompt)
    messages = [{"role": "user", "content": initial_message}]

    compute_iterations = 0

    # Define tools for the agent
    tools = [
        {
            "name": "view_file",
            "description": "View the content of a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Why view the file",
                    },
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["reasoning", "path"],
            },
        },
        {
            "name": "create_file",
            "description": "Create a new file with given content",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Why create the file",
                    },
                    "path": {"type": "string", "description": "File path"},
                    "file_text": {
                        "type": "string",
                        "description": "Content for the file",
                    },
                },
                "required": ["reasoning", "path", "file_text"],
            },
        },
        {
            "name": "str_replace",
            "description": "Replace text in a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Reason for replacement",
                    },
                    "path": {"type": "string", "description": "File path"},
                    "old_str": {
                        "type": "string",
                        "description": "Text to replace",
                    },
                    "new_str": {
                        "type": "string",
                        "description": "Replacement text",
                    },
                },
                "required": ["reasoning", "path", "old_str", "new_str"],
            },
        },
        {
            "name": "insert_line",
            "description": "Insert text at a specific line in a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Reason for insertion",
                    },
                    "path": {"type": "string", "description": "File path"},
                    "insert_line": {
                        "type": "integer",
                        "description": "Line number",
                    },
                    "new_str": {
                        "type": "string",
                        "description": "Text to insert",
                    },
                },
                "required": ["reasoning", "path", "insert_line", "new_str"],
            },
        },
        {
            "name": "execute_bash",
            "description": "Execute a bash command",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Reason for command execution",
                    },
                    "command": {
                        "type": "string",
                        "description": "Bash command",
                    },
                },
                "required": ["reasoning", "command"],
            },
        },
        {
            "name": "restart_bash",
            "description": "Restart the bash session with fresh environment",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Why to restart bash",
                    }
                },
                "required": ["reasoning"],
            },
        },
        {
            "name": "complete_task",
            "description": "Complete the task and exit the agent loop",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Why the task is complete",
                    }
                },
                "required": ["reasoning"],
            },
        },
    ]

    # Begin the agent loop.
    # This loop processes Anthropic API responses, executes tool calls for both editor and bash commands,
    # and logs detailed information via rich logging.
    while compute_iterations < args.compute:
        compute_iterations += 1
        console.rule(f"[yellow]Agent Loop {compute_iterations}/{args.compute}[/yellow]")
        try:
            response = client.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=args.max_tokens,
                thinking={
                    "type": "enabled",
                    "budget_tokens": args.thinking_budget_tokens,
                },
                messages=messages,
                tools=tools,
            )
        except Exception as e:
            console.print(f"[red]Error in API call: {str(e)}[/red]")
            console.print(traceback.format_exc())
            break

        # Log the API response with rich formatting
        console.print(
            Panel(
                Syntax(
                    json.dumps(response.model_dump(), indent=2),
                    "json",
                    theme="monokai",
                    word_wrap=True,
                ),
                title="[bold green]API Response[/bold green]",
                border_style="green",
            )
        )

        # Extract and print the thinking block if present
        thinking_blocks = [
            block for block in response.content if block.type == "thinking"
        ]
        if thinking_blocks:
            console.print(
                Panel(
                    thinking_blocks[0].thinking,
                    title="[bold blue]Claude's Thinking Process[/bold blue]",
                    border_style="blue",
                )
            )

        tool_calls = [
            block
            for block in response.content
            if hasattr(block, "type") and block.type == "tool_use"
        ]
        if tool_calls:
            # Map tool names to their corresponding functions
            tool_functions = {
                "view_file": tool_view_file,
                "create_file": tool_create_file,
                "str_replace": tool_str_replace,
                "insert_line": tool_insert_line,
                "execute_bash": tool_execute_bash,
                "restart_bash": tool_restart_bash,
                "complete_task": tool_complete_task,
            }
            # Add the assistant's response to messages
            messages.append({"role": "assistant", "content": response.content})

            for tool in tool_calls:
                console.print(
                    f"[blue]Tool Call:[/blue] {tool.name}({json.dumps(tool.input)})"
                )
                func = tool_functions.get(tool.name)
                if func:
                    output = func(tool.input)
                    result_text = output.get("error") or output.get("result", "")
                    console.print(f"[green]Tool Result:[/green] {result_text}")

                    # Format the tool result message according to Claude API requirements
                    tool_result_message = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool.id,
                                "content": result_text,
                            }
                        ],
                    }
                    messages.append(tool_result_message)
                    if tool.name == "complete_task":
                        console.print(
                            "[green]Task completed. Exiting agent loop.[/green]"
                        )
                        return
                else:
                    raise ValueError(f"Unknown tool: {tool.name}")

    console.print("[yellow]Reached compute limit without completing task.[/yellow]")

    # Calculate approximate token usage
    prompt_tokens = len(initial_message.split())
    thinking_tokens = sum(
        len(block.thinking.split())
        for msg in messages
        if msg["role"] == "assistant"
        for block in msg.get("content", [])
        if hasattr(block, "type") and block.type == "thinking"
    )
    response_tokens = sum(
        len(block.text.split())
        for msg in messages
        if msg["role"] == "assistant"
        for block in msg.get("content", [])
        if hasattr(block, "type") and block.type == "text"
    )
    tool_result_tokens = sum(
        len(str(content_item["content"]).split())
        for msg in messages
        if msg["role"] == "user" and isinstance(msg.get("content"), list)
        for content_item in msg["content"]
        if content_item.get("type") == "tool_result"
    )

    total_input_tokens = prompt_tokens + tool_result_tokens
    total_output_tokens = response_tokens
    total_tokens = total_input_tokens + total_output_tokens + thinking_tokens

    # Calculate approximate costs (Claude 3.7 Sonnet pricing)
    input_cost = total_input_tokens * (3.0 / 1000000)  # $3.00 per million tokens
    output_cost = total_output_tokens * (15.0 / 1000000)  # $15.00 per million tokens
    thinking_cost = thinking_tokens * (
        15.0 / 1000000
    )  # $15.00 per million tokens (thinking tokens are billed as output)
    total_cost = input_cost + output_cost + thinking_cost

    # Display token usage summary
    token_table = Table(title="Token Usage Summary")
    token_table.add_column("Type", style="cyan")
    token_table.add_column("Count", style="magenta")
    token_table.add_column("Cost ($)", style="green")
    token_table.add_row("Input Tokens", str(total_input_tokens), f"${input_cost:.6f}")
    token_table.add_row(
        "Output Tokens", str(total_output_tokens), f"${output_cost:.6f}"
    )
    token_table.add_row(
        "Thinking Tokens", str(thinking_tokens), f"${thinking_cost:.6f}"
    )
    token_table.add_row("Total", str(total_tokens), f"${total_cost:.6f}")
    console.print(token_table)


if __name__ == "__main__":
    main()
