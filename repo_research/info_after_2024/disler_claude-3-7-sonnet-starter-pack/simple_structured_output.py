#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#   "anthropic>=0.45.2",
#   "argparse>=1.4.0",
#   "rich>=13.7.0",
# ]
# ///

"""
Simple Structured Output Example for Claude 3.7 Sonnet

This script demonstrates how to get structured JSON output from Claude 3.7 Sonnet.

Usage:
    uv run simple_structured_output.py --prompt "Analyze this customer feedback: Great buy, I'm happy with my purchase."

    uv run simple_structured_output.py --prompt "Analyze this customer feedback: 'I've been a loyal user for 3 years, but the recent UI update is a disaster.'"

    uv run simple_structured_output.py --prompt "Analyze this customer feedback: 'I've been a loyal user for 3 years, but the recent UI update is a disaster.'" --max_tokens 1000
"""

import os
import sys
import json
import argparse
import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table


def main():
    # Initialize rich console
    console = Console()

    parser = argparse.ArgumentParser(
        description="Claude 3.7 Sonnet structured output example"
    )
    parser.add_argument(
        "--prompt", type=str, required=True, help="The prompt to send to Claude"
    )
    parser.add_argument(
        "--max_tokens",
        type=int,
        default=1000,
        help="Maximum number of tokens in the response",
    )
    args = parser.parse_args()

    # Get API key from environment variable
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] ANTHROPIC_API_KEY environment variable not set"
        )
        sys.exit(1)

    # Initialize the Anthropic client
    client = anthropic.Anthropic(api_key=api_key)

    # Construct the system prompt to request JSON output
    system_prompt = """You're a Customer Insights AI. Analyze the user's feedback and output in JSON format with keys: 
{
    "sentiment": (positive/negative/neutral),
    "key_issues": (list),
    "action_items": (list of dicts with "team" and "task") - create action items for our team to address the key issues
}

Your response should be valid JSON only, with no additional text.
"""

    try:
        # Display request information
        console.print(
            Panel(
                f"[bold]Prompt:[/bold] {args.prompt}\n[bold]Max Tokens:[/bold] {args.max_tokens}",
                title="[bold green]Request to Claude 3.7 Sonnet[/bold green]",
                border_style="green",
            )
        )

        # Create a message with Claude 3.7 Sonnet
        with console.status(
            "[bold green]Sending request to Claude 3.7 Sonnet...", spinner="dots"
        ):
            response = client.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=args.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": args.prompt}],
            )

        # Get the text response
        text_response = response.content[0].text

        # Try to parse as JSON for pretty printing with syntax highlighting
        try:
            json_response = json.loads(text_response)

            # Create a table to display the sentiment
            sentiment_table = Table(title="Customer Feedback Analysis")
            sentiment_table.add_column("Sentiment", style="cyan")
            sentiment_table.add_row(json_response.get("sentiment", "Unknown"))
            console.print(sentiment_table)

            # Display the full JSON response with syntax highlighting
            console.print(
                Panel(
                    Syntax(
                        json.dumps(json_response, indent=2),
                        "json",
                        theme="monokai",
                        word_wrap=True,
                    ),
                    title="[bold blue]Structured JSON Response[/bold blue]",
                    border_style="blue",
                )
            )

            # Create a table for action items if present
            if "action_items" in json_response and json_response["action_items"]:
                action_table = Table(title="Action Items")
                action_table.add_column("Team", style="magenta")
                action_table.add_column("Task", style="green")

                for item in json_response["action_items"]:
                    action_table.add_row(
                        item.get("team", "Unknown"), item.get("task", "Unknown")
                    )

                console.print(action_table)

            # Calculate approximate token usage
            prompt_tokens = len(args.prompt.split())
            response_tokens = len(text_response.split())
            total_tokens = prompt_tokens + response_tokens

            # Calculate approximate costs (Claude 3.7 Sonnet pricing)
            input_cost = prompt_tokens * (3.0 / 1000000)  # $3.00 per million tokens
            output_cost = response_tokens * (
                15.0 / 1000000
            )  # $15.00 per million tokens
            total_cost = input_cost + output_cost

            # Display token usage summary
            token_table = Table(title="Token Usage Summary")
            token_table.add_column("Type", style="cyan")
            token_table.add_column("Count", style="magenta")
            token_table.add_column("Cost ($)", style="green")
            token_table.add_row(
                "Input Tokens", str(prompt_tokens), f"${input_cost:.6f}"
            )
            token_table.add_row(
                "Output Tokens", str(response_tokens), f"${output_cost:.6f}"
            )
            token_table.add_row("Total", str(total_tokens), f"${total_cost:.6f}")
            console.print(token_table)

        except json.JSONDecodeError:
            # If not valid JSON, just print the raw response
            console.print(
                Panel(
                    text_response,
                    title="[bold yellow]Raw Response (Invalid JSON)[/bold yellow]",
                    border_style="yellow",
                )
            )

            # Still calculate token usage even for invalid JSON
            prompt_tokens = len(args.prompt.split())
            response_tokens = len(text_response.split())
            total_tokens = prompt_tokens + response_tokens

            # Calculate approximate costs (Claude 3.7 Sonnet pricing)
            input_cost = prompt_tokens * (3.0 / 1000000)  # $3.00 per million tokens
            output_cost = response_tokens * (
                15.0 / 1000000
            )  # $15.00 per million tokens
            total_cost = input_cost + output_cost

            # Display token usage summary
            token_table = Table(title="Token Usage Summary")
            token_table.add_column("Type", style="cyan")
            token_table.add_column("Count", style="magenta")
            token_table.add_column("Cost ($)", style="green")
            token_table.add_row(
                "Input Tokens", str(prompt_tokens), f"${input_cost:.6f}"
            )
            token_table.add_row(
                "Output Tokens", str(response_tokens), f"${output_cost:.6f}"
            )
            token_table.add_row("Total", str(total_tokens), f"${total_cost:.6f}")
            console.print(token_table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
