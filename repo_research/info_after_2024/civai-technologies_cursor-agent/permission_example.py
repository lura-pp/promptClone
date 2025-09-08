#!/usr/bin/env python3
"""
Permission system demonstration for agent tools.

This script demonstrates the permission system for agent tools,
showing how different operations require different permissions
and how the yolo mode affects permission requests.
"""

import asyncio
import os
import sys
from typing import Dict, Optional

# Add the parent directory to the path so we can import the agent module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cursor_agent_tools import create_agent
from cursor_agent_tools import PermissionOptions


async def demo_normal_mode() -> None:
    """
    Demonstrate the permission system in normal mode (requiring confirmation).
    """
    print("\n✅ NORMAL MODE DEMO ✅")
    
    # Create permission options with standard settings
    permissions = PermissionOptions(
        yolo_mode=False,
        delete_file_protection=True
    )
    
    agent = create_agent(
        model="gpt-4o",  # You can change this to any supported model
        permissions=permissions
    )
    
    # Initialize the agent with tools
    agent.register_default_tools()
    
    # Test file operations
    test_dir = "./test_permission"
    os.makedirs(test_dir, exist_ok=True)
    
    # Create a file
    print("\nCreating a file...")
    try:
        result = agent.available_tools["create_file"]["function"](
            file_path=f"{test_dir}/test.txt",
            content="This is a test file."
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Edit a file
    print("\nEditing a file...")
    try:
        result = agent.available_tools["edit_file"]["function"](
            target_file=f"{test_dir}/test.txt",
            instructions="Add a second line",
            code_replace="This is a test file.\nThis is a second line."
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Delete a file
    print("\nDeleting a file...")
    try:
        result = agent.available_tools["delete_file"]["function"](
            target_file=f"{test_dir}/test.txt"
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Run a command
    print("\nRunning a command...")
    try:
        result = agent.available_tools["run_terminal_command"]["function"](
            command="ls -la",
            explanation="List files in current directory"
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


async def demo_yolo_mode() -> None:
    """
    Demonstrate the permission system in yolo mode (automatic approval).
    """
    print("\n🚀 YOLO MODE DEMO 🚀")
    
    # Create permission options with YOLO settings
    permissions = PermissionOptions(
        yolo_mode=True,
        yolo_prompt="Allow safe file operations and simple commands",
        command_allowlist=["ls", "echo", "cat"],
        command_denylist=["rm -rf", "sudo"],
        delete_file_protection=True
    )
    
    agent = create_agent(
        model="gpt-4o",  # You can change this to any supported model
        permissions=permissions
    )
    
    # Initialize the agent with tools
    agent.register_default_tools()
    
    # Test file operations
    test_dir = "./test_permission"
    os.makedirs(test_dir, exist_ok=True)
    
    # Create a file (should be auto-approved)
    print("\nCreating a file (auto-approved)...")
    try:
        result = agent.available_tools["create_file"]["function"](
            file_path=f"{test_dir}/yolo_test.txt",
            content="This is a YOLO mode test file."
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Run an allowed command (should be auto-approved)
    print("\nRunning an allowed command (auto-approved)...")
    try:
        result = agent.available_tools["run_terminal_command"]["function"](
            command="ls -la",
            explanation="List files in current directory"
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Run a denied command (should be denied despite yolo mode)
    print("\nRunning a denied command (should be denied)...")
    try:
        result = agent.available_tools["run_terminal_command"]["function"](
            command="sudo ls /root",
            explanation="List files in root directory"
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Delete a file (should still require permission despite yolo mode)
    print("\nDeleting a file (should still require permission)...")
    try:
        result = agent.available_tools["delete_file"]["function"](
            target_file=f"{test_dir}/yolo_test.txt"
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


async def main() -> None:
    """
    Run the demonstration.
    """
    print("🔒 AGENT TOOL PERMISSION SYSTEM DEMO 🔒")
    
    # Demo normal mode
    await demo_normal_mode()
    
    # Demo yolo mode
    await demo_yolo_mode()
    
    # Clean up test directory
    try:
        test_dir = "./test_permission"
        if os.path.exists(test_dir):
            for filename in os.listdir(test_dir):
                file_path = os.path.join(test_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(test_dir)
    except Exception as e:
        print(f"Error cleaning up: {e}")
    
    print("\n✅ Demonstration complete ✅")


if __name__ == "__main__":
    asyncio.run(main()) 