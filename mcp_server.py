"""
MCP Server for AI Meeting Assistant.

Exposes a single tool ``process_meeting_query`` that runs the full meeting
assistant pipeline.  It accepts a user query (which may include a transcript
or an audio file path), generates a summary, extracts action items, and
returns the combined result.

The server communicates over stdin/stdout using the JSON-RPC based
Model Context Protocol (MCP).
"""

import json
import logging
import os
import sys
import tempfile

import requests
from mcp.server.mcpserver import MCPServer as FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [mcp_server] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)

logger = logging.getLogger("mcp_server")


GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
DEFAULT_MODEL = "gemini-2.5-flash-lite"

mcp = FastMCP(
    "AI Meeting Assistant",
    version="1.0.0",
    description="MCP server exposing the full AI Meeting Assistant pipeline",
)


def _call_gemini(prompt: str) -> str:
    """Send a prompt to the Gemini API and return the text response."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    model_name = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    if not api_key:
        logger.error("GOOGLE_API_KEY environment variable is not set")
        raise RuntimeError(
            "GOOGLE_API_KEY environment variable is not set. "
            "Please set it before using this tool."
        )

    logger.info("Calling Gemini API (model=%s, prompt_length=%d)", model_name, len(prompt))

    response = requests.post(
        GEMINI_API_URL.format(model=model_name),
        headers={"Content-Type": "application/json"},
        params={"key": api_key},
        json={
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                    ]
                }
            ]
        },
        timeout=120,
    )

    try:
        response.raise_for_status()
        logger.info("Gemini API responded with status %d", response.status_code)
    except requests.HTTPError as exc:
        body = response.text[:500]
        logger.error("Gemini request failed (status=%d): %s", response.status_code, body[:200])
        raise RuntimeError(
            f"Gemini request failed ({response.status_code}): {body}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        logger.error("Gemini returned a non-JSON response")
        raise RuntimeError("Gemini returned a non-JSON response") from exc

    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        logger.info("Gemini response received (length=%d)", len(text))
        return text
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Unexpected Gemini response format: %s", str(payload)[:200])
        raise RuntimeError(
            f"Unexpected Gemini response format: {payload}"
        ) from exc


def _transcribe_audio(audio_file_path: str) -> str:
    """Transcribe an audio file using OpenAI Whisper."""
    logger.info("Transcribing audio file: %s", audio_file_path)

    if not os.path.exists(audio_file_path):
        logger.error("Audio file not found: %s", audio_file_path)
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    try:
        import whisper
    except ImportError:
        logger.error("openai-whisper is not installed")
        raise RuntimeError(
            "openai-whisper is not installed. Install with: pip install openai-whisper"
        )

    logger.info("Loading Whisper model (base)...")
    model = whisper.load_model("base")
    logger.info("Whisper model loaded. Starting transcription...")
    result = model.transcribe(audio_file_path)
    transcript = result["text"]
    logger.info("Transcription complete (length=%d chars)", len(transcript))
    return transcript


@mcp.tool()
def process_meeting_query(query: str, audio_file_path: str = "") -> str:
    """
    Run the full AI Meeting Assistant pipeline.

    Accepts a user query that may contain a meeting transcript, a general
    meeting-related question, or an audio file path to transcribe first.

    The tool will:
      1. If audio_file_path is provided, transcribe the audio to text.
      2. Generate a concise meeting summary from the transcript.
      3. Extract action items with owners and deadlines.
      4. Answer any specific question the user asked.

    If the query contains a transcript (or audio was transcribed), summary
    and action items are generated.
    If it is a general question, only the answer is returned.

    Args:
        query: The user's input — either a meeting transcript to process
               or a question about meetings.
        audio_file_path: Optional path to an audio file to transcribe.
                         If provided, the transcription is used as the
                         transcript for processing.

    Returns:
        A JSON string with keys ``transcript`` (if audio was provided),
        ``summary``, ``action_items``, and ``answer``
        (each present only when applicable).
    """
    logger.info("process_meeting_query called (query_length=%d, audio_file_path='%s')",
                len(query) if query else 0, audio_file_path or "")

    if (not query or not query.strip()) and not audio_file_path:
        logger.warning("Empty query received — returning error")
        return json.dumps({"error": "Query is empty. Please provide a meeting transcript, question, or audio file."})

    result: dict = {}
    transcript_text = query.strip() if query else ""

    # ----- Step 0: Transcribe audio if provided -----
    if audio_file_path and audio_file_path.strip():
        logger.info("Audio file provided — starting transcription step")
        try:
            transcript_text = _transcribe_audio(audio_file_path.strip())
            result["transcript"] = transcript_text
            logger.info("Audio transcription successful (length=%d)", len(transcript_text))
        except Exception as exc:
            logger.error("Audio transcription failed: %s", exc)
            return json.dumps({"error": f"Audio transcription failed: {exc}"})

    is_transcript = len(transcript_text) > 200
    logger.info("Input classified as %s (length=%d)",
                "TRANSCRIPT" if is_transcript else "QUESTION", len(transcript_text))

    if is_transcript:
        # --- Step 1: Summary ---
        logger.info("Step 1: Generating meeting summary...")
        summary_prompt = f"""Summarize the following meeting transcript.
Provide a clear, concise summary highlighting key discussion points,
decisions made, and important topics covered.

Transcript:
{transcript_text}
"""
        try:
            result["summary"] = _call_gemini(summary_prompt)
            logger.info("Summary generated successfully")
        except Exception as exc:
            logger.error("Error generating summary: %s", exc)
            result["summary"] = f"Error generating summary: {exc}"

        # --- Step 2: Action Items ---
        logger.info("Step 2: Extracting action items...")
        action_prompt = f"""Extract all action items from the following meeting
transcript. Return them as a numbered list with the responsible person
(if mentioned) and any deadlines.

Transcript:
{transcript_text}
"""
        try:
            result["action_items"] = _call_gemini(action_prompt)
            logger.info("Action items extracted successfully")
        except Exception as exc:
            logger.error("Error extracting action items: %s", exc)
            result["action_items"] = f"Error extracting action items: {exc}"

    else:
        # --- General question ---
        logger.info("Answering general question...")
        answer_prompt = f"""You are an AI Meeting Assistant. Answer the
following question or fulfil the request. Be helpful, concise, and
professional.

Question / Request:
{transcript_text}
"""
        try:
            result["answer"] = _call_gemini(answer_prompt)
            logger.info("Question answered successfully")
        except Exception as exc:
            logger.error("Error processing query: %s", exc)
            result["answer"] = f"Error processing query: {exc}"

    logger.info("process_meeting_query completed — returning result with keys: %s", list(result.keys()))
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    logger.info("Starting MCP server (transport=stdio)...")
    mcp.run(transport="stdio")
