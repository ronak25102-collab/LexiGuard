#!/usr/bin/env python3
"""Script 06: Demo - Ask a legal question end-to-end."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from lexiguard.agent.graph import run_agent

console = Console()

SAMPLE_QUESTIONS = [
    "What are the termination conditions in the contracts?",
    "Which contracts have non-compete clauses and what are their durations?",
    "List all parties and their roles across all contracts.",
    "Are there any indemnification clauses that are modified by other clauses?",
    "Which contracts are governed by Delaware law?",
]


def main():
    console.print(Panel.fit(
        "[bold blue]LexiGuard - Legal GraphRAG Demo[/bold blue]\n"
        "Ask natural language questions about your contracts.",
        border_style="blue",
    ))

    # Check for command-line argument or use interactive mode
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        console.print("\n[bold]Sample questions:[/bold]")
        for i, q in enumerate(SAMPLE_QUESTIONS, 1):
            console.print(f"  {i}. {q}")

        console.print("\n[dim]Enter a number (1-5) or type your own question:[/dim]")
        user_input = input("> ").strip()

        if user_input.isdigit() and 1 <= int(user_input) <= len(SAMPLE_QUESTIONS):
            question = SAMPLE_QUESTIONS[int(user_input) - 1]
        else:
            question = user_input

    console.print(f"\n[bold green]Question:[/bold green] {question}\n")
    console.print("[dim]Processing through CRAG pipeline...[/dim]\n")

    # Run the agent
    result = run_agent(question)

    # Display results
    console.print(Panel(
        Markdown(result["answer"]),
        title="[bold green]Answer[/bold green]",
        border_style="green",
    ))

    if result.get("sources"):
        console.print(Panel(
            "\n".join(f"• {s}" for s in result["sources"]),
            title="[bold yellow]Sources[/bold yellow]",
            border_style="yellow",
        ))

    console.print(f"\n[dim]Cypher Query:[/dim] {result.get('cypher_query', 'N/A')}")
    console.print(f"[dim]Relevance:[/dim] {result.get('relevance_score', 'N/A')}")
    console.print(f"[dim]Retries Used:[/dim] {result.get('retries_used', 0)}")


if __name__ == "__main__":
    main()
