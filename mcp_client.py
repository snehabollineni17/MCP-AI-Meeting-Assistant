"""
MCP Client for AI Meeting Assistant.

Spawns the MCP server (mcp_server.py) as a subprocess and communicates
with it over stdin/stdout using the JSON-RPC based Model Context Protocol.

"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [mcp_client] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mcp_client")


_MCP_TOOL_NAME = "process_meeting_query"
_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "ai-meeting-assistant-client", "version": "1.0.0"}

_DEFAULT_TIMEOUT = 120.0


def _write_message(proc: subprocess.Popen, msg: dict) -> None:
    """Write a single JSON-RPC message to the server's stdin."""
    line = json.dumps(msg) + "\n"
    proc.stdin.write(line)
    proc.stdin.flush()


def _read_message(proc: subprocess.Popen, timeout: float) -> dict:

    result_holder: Dict[str, Any] = {}
    error_holder: Dict[str, Any] = {}

    def _readline_worker():
        try:
            while True:
                line = proc.stdout.readline()
                if not line:
                    error_holder["error"] = "MCP server closed stdout unexpectedly"
                    return

                text = line.strip()
                if not text:
                    continue

                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    logger.debug("Non-JSON line from MCP server: %s", text[:200])
                    continue

                # Skip notifications (no id field)
                if "id" not in msg:
                    logger.debug("Notification received: %s", msg.get("method", "unknown"))
                    continue

                result_holder["msg"] = msg
                return
        except Exception as e:
            error_holder["error"] = str(e)

    reader_thread = threading.Thread(target=_readline_worker, daemon=True)
    reader_thread.start()
    reader_thread.join(timeout=timeout)

    if reader_thread.is_alive():
        raise TimeoutError("MCP server did not respond in time")

    if "error" in error_holder:
        raise ConnectionError(error_holder["error"])

    return result_holder.get("msg", {})


def _get_server_script_path() -> str:
    return str(Path(__file__).parent / "mcp_server.py")


def _invoke_mcp_sync(
    query: str,
    audio_file_path: str = "",
    timeout: float = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:

    server_script = _get_server_script_path()
    logger.info("MCP server script path: %s", server_script)

    if not Path(server_script).exists():
        logger.error("MCP server script not found at: %s", server_script)
        raise RuntimeError(
            f"MCP server script not found at: {server_script}. "
            "Ensure mcp_server.py is in the same directory as mcp_client.py."
        )

    sub_env = os.environ.copy()

    logger.info("Spawning MCP server subprocess: %s %s", sys.executable, server_script)
    proc = subprocess.Popen(
        [sys.executable, server_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=sub_env,
    )

    try:
        # --- Step 1: Initialize ---
        logger.info("Step 1: Sending 'initialize' request...")
        _write_message(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": _CLIENT_INFO,
            },
        })
        init_response = _read_message(proc, timeout=timeout)

        if "error" in init_response:
            logger.error("MCP initialize failed: %s", init_response["error"])
            raise RuntimeError(
                f"MCP initialize failed: {init_response['error']}"
            )
        logger.info("MCP initialize successful")

        # --- Step 2: Send initialized notification ---
        logger.info("Step 2: Sending 'notifications/initialized'...")
        _write_message(proc, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })

        # --- Step 3: Call the tool ---
        logger.info("Step 3: Calling tool '%s' (query_length=%d, audio='%s')...",
                     _MCP_TOOL_NAME, len(query) if query else 0, audio_file_path or "")
        tool_arguments = {
            "query": query,
        }
        if audio_file_path:
            tool_arguments["audio_file_path"] = audio_file_path

        _write_message(proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": _MCP_TOOL_NAME,
                "arguments": tool_arguments,
            },
        })
        tool_response = _read_message(proc, timeout=timeout)

        if "error" in tool_response:
            logger.error("MCP tool call failed: %s", tool_response["error"])
            raise RuntimeError(
                f"MCP tool call failed: {tool_response['error']}"
            )
        logger.info("MCP tool call successful")

        # --- Step 4: Parse the result ---
        logger.info("Step 4: Parsing tool response...")
        result = tool_response.get("result", {})
        content_list = result.get("content", [])

        tool_text_content: Any = None

        for content_item in content_list:
            if isinstance(content_item, dict):
                text = content_item.get("text", "")
                if text:
                    try:
                        parsed = json.loads(text)
                        tool_text_content = parsed
                    except json.JSONDecodeError:
                        tool_text_content = text

        if tool_text_content:
            if isinstance(tool_text_content, dict):
                logger.info("Parsed result keys: %s", list(tool_text_content.keys()))
                return tool_text_content
            else:
                logger.info("Returning raw text result")
                return {"raw": tool_text_content}

        logger.warning("No text content found in tool response — returning raw content")
        return {"raw_content": content_list}

    finally:
        # --- Cleanup ---
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except Exception:
            pass

        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception:
            pass

        try:
            if proc.stderr:
                stderr_output = proc.stderr.read()
                if stderr_output and stderr_output.strip():
                    logger.debug("MCP server stderr:\n%s", stderr_output[:1000])
        except Exception:
            pass

        logger.info("MCP subprocess cleaned up")


async def invoke_meeting_assistant(
    query: str,
    audio_file_path: str = "",
    timeout: float = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Invoke the ``process_meeting_query`` MCP tool via stdio subprocess.

    Runs the synchronous subprocess logic in a background thread via
    ``asyncio.to_thread()`` for compatibility with async frameworks.

    Args:
        query:           The user's query — either a meeting transcript to
                         process or a general meeting-related question.
        audio_file_path: Optional path to an audio file to transcribe.
        timeout:         Maximum seconds to wait for each MCP server response.

    Returns:
        A dict with keys like ``summary``, ``action_items``, or ``answer``
        depending on the type of query.

    Raises:
        RuntimeError: On MCP server startup failure or tool-call error.
        TimeoutError: If the server does not respond within *timeout*.
    """
    return await asyncio.to_thread(_invoke_mcp_sync, query, audio_file_path, timeout)


def invoke_meeting_assistant_sync(
    query: str,
    audio_file_path: str = "",
    timeout: float = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Synchronous wrapper around the MCP tool invocation.

    Convenient for use in Streamlit or other sync contexts.

    Args:
        query:           The user's query.
        audio_file_path: Optional path to an audio file to transcribe.
        timeout:         Maximum seconds to wait for each MCP server response.

    Returns:
        A dict with the tool result.
    """
    return _invoke_mcp_sync(query, audio_file_path, timeout)
