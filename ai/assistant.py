"""AI Automation Assistant - a conversational CLI tying together every AI feature in this framework:
test generation (Phase 4), NLP-driven execution (Phase 4), and failure root-cause analysis (Phase 3).
It reuses the same BrowserManager/ContextManager as pytest so behavior stays consistent with test runs.

Run with: python -m ai.assistant
"""
import subprocess
import sys

from ai.nlp_executor import execute_instruction
from ai.root_cause_analyzer import analyze_failure
from ai.test_generator import generate_test
from core.browser_manager import BrowserManager
from core.context_manager import ContextManager
from utils.logger import get_logger

logger = get_logger(__name__)

HELP_TEXT = """
Commands:
  generate <story text>              Generate a pytest test from a user story (Phase 4)
  nlp <instruction>                   Open a browser and execute a plain-English instruction (Phase 4)
  analyze <test_name> | <exception>   Run root-cause analysis on a failure description (Phase 3)
  run <pytest args>                    Run pytest with the given args, e.g. "run tests/ui -m smoke"
  help                                 Show this message
  exit                                 Quit
"""


def _run_pytest(args: str):
    command = [sys.executable, "-m", "pytest"] + (args.split() if args else [])
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command)
    print(f"pytest exited with code {result.returncode}")


def _run_nlp(instruction: str):
    manager = BrowserManager()
    browser = manager.start()
    ctx_manager = ContextManager(browser)
    context = ctx_manager.create_context()
    page = context.new_page()
    try:
        steps = execute_instruction(page, instruction)
        print(f"Executed {len(steps)} step(s): {steps}")
    finally:
        ctx_manager.close_context()
        manager.stop()


def main():
    print("AI Automation Assistant (Ollama-powered). Type 'help' for commands, 'exit' to quit.")
    while True:
        try:
            raw = input("assistant> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue
        if raw in ("exit", "quit"):
            break
        if raw == "help":
            print(HELP_TEXT)
            continue

        try:
            if raw.startswith("generate "):
                story = raw[len("generate "):]
                path = generate_test(story, "generated_test.py")
                print(f"Generated: {path}")
            elif raw.startswith("nlp "):
                _run_nlp(raw[len("nlp "):])
            elif raw.startswith("analyze "):
                body = raw[len("analyze "):]
                test_name, _, exception = body.partition("|")
                result = analyze_failure(test_name.strip(), exception.strip())
                print(result)
            elif raw.startswith("run"):
                _run_pytest(raw[len("run"):].strip())
            else:
                print("Unknown command. Type 'help'.")
        except Exception as e:
            logger.error(f"Command failed: {e}")
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
