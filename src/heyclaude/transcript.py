"""Parse Claude Code JSONL transcripts."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_transcript(transcript_path: str, max_lines: int = 20) -> str | None:
    """
    Parse a Claude Code JSONL transcript and extract the last question/context.

    Looks for AskUserQuestion tool calls first, then falls back to last assistant message.

    Args:
        transcript_path: Path to the JSONL transcript file
        max_lines: Maximum number of lines to return from the message

    Returns:
        The question with options, or last assistant message text, or None
    """
    path = Path(transcript_path)
    if not path.exists():
        logger.warning(f"Transcript not found: {transcript_path}")
        return None

    last_question = None
    last_assistant_message = None

    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") == "assistant":
                    message = entry.get("message", {})
                    content = message.get("content", [])

                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get("type", "")

                            # Check for tool_use blocks (AskUserQuestion)
                            if block_type == "tool_use":
                                tool_name = block.get("name", "")
                                if tool_name == "AskUserQuestion":
                                    question_text = _format_ask_user_question(block.get("input", {}))
                                    if question_text:
                                        last_question = question_text

                            # Regular text blocks
                            elif block_type == "text":
                                text_parts.append(block.get("text", ""))

                        elif isinstance(block, str):
                            text_parts.append(block)

                    if text_parts:
                        last_assistant_message = "\n".join(text_parts)

    except Exception as e:
        logger.error(f"Error parsing transcript: {e}")
        return None

    # Prefer question with options over plain text
    result = last_question or last_assistant_message

    if result:
        # max_lines >= 100 means "All" - no truncation
        if max_lines < 100:
            lines = result.split("\n")
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + "\n..."
        return result

    return None


def _format_ask_user_question(input_data: dict) -> str | None:
    """Format an AskUserQuestion tool input for display."""
    questions = input_data.get("questions", [])
    if not questions:
        return None

    parts = []
    for q in questions:
        question_text = q.get("question", "")
        if question_text:
            parts.append(f"❓ {question_text}")

        options = q.get("options", [])
        for i, opt in enumerate(options, 1):
            label = opt.get("label", "")
            desc = opt.get("description", "")
            if label:
                if desc:
                    parts.append(f"  {i}. {label} - {desc}")
                else:
                    parts.append(f"  {i}. {label}")

    return "\n".join(parts) if parts else None


def get_project_name(cwd: str) -> str:
    """Extract project name from working directory path."""
    path = Path(cwd)
    return path.name
