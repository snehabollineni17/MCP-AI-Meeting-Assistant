"""
Streamlit UI for AI Meeting Assistant.

Provides a chat-based interface where users can:
  - Upload an audio file to transcribe and process.
  - Paste a meeting transcript to get a summary and action items.
  - Ask general meeting-related questions.

All queries are routed through the MCP client which spawns the MCP server
subprocess and communicates via the Model Context Protocol (JSON-RPC / stdio).
"""

import json
import logging
import os
import tempfile

import streamlit as st

from mcp_client import invoke_meeting_assistant_sync

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [streamlit_app] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("streamlit_app")

st.set_page_config(
    page_title="AI Meeting Assistant",
    page_icon="📋",
    layout="wide",
)

with st.sidebar:
    st.title("📋 AI Meeting Assistant")
    st.markdown("---")

    # Audio file uploader
    st.subheader("🎤 Upload Audio")
    uploaded_file = st.file_uploader(
        "Upload a meeting audio/video file",
        type=["mp3", "wav", "m4a", "ogg", "flac", "webm", "mp4"],
        help="Supported formats: MP3, WAV, M4A, OGG, FLAC, WEBM, MP4",
    )

    if uploaded_file is not None:
        st.audio(uploaded_file, format=f"audio/{uploaded_file.type.split('/')[-1]}")
        if st.button("🚀 Process Audio", use_container_width=True):
            logger.info("User clicked 'Process Audio' for file: %s", uploaded_file.name)
            st.session_state.process_audio = True

    st.markdown("---")
    st.markdown(
        """
**How to use:**

1. **Upload audio** using the file uploader above.
2. **Paste a transcript** (>200 chars) in the chat to get a summary and action items.
3. **Ask a question** about meetings, agendas, or best practices.
"""
    )
    st.markdown("---")

    if st.button("🗑️ Clear Chat", use_container_width=True):
        logger.info("User cleared chat history")
        st.session_state.messages = []
        st.session_state.pop("process_audio", None)
        st.rerun()

    st.markdown(
        """
**Example queries:**
- *How do I write an effective meeting agenda?*
- *Paste a transcript to get summary + action items*
"""
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("💬 Meeting Assistant Chat")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


if st.session_state.get("process_audio") and uploaded_file is not None:
    st.session_state.pop("process_audio", None)

    suffix = os.path.splitext(uploaded_file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name
    logger.info("Saved uploaded audio to temp file: %s", tmp_path)


    user_msg = f"🎤 Uploaded audio: **{uploaded_file.name}**"
    st.session_state.messages.append({"role": "user", "content": user_msg})
    with st.chat_message("user"):
        st.markdown(user_msg)

    with st.chat_message("assistant"):
        with st.spinner("Transcribing audio and processing via MCP pipeline..."):
            logger.info("Sending audio to MCP pipeline for processing...")
            try:
                result = invoke_meeting_assistant_sync(
                    query="",
                    audio_file_path=tmp_path,
                )

                response_parts = []

                if "transcript" in result:
                    response_parts.append("##  Transcript\n")
                    response_parts.append(result["transcript"])
                    response_parts.append("\n")

                if "summary" in result:
                    response_parts.append("##  Meeting Summary\n")
                    response_parts.append(result["summary"])
                    response_parts.append("\n")

                if "action_items" in result:
                    response_parts.append("##  Action Items\n")
                    response_parts.append(result["action_items"])
                    response_parts.append("\n")

                if "answer" in result:
                    response_parts.append(result["answer"])

                if "error" in result:
                    response_parts.append(f"**Error:** {result['error']}")

                if not response_parts:
                    response_parts.append(
                        f"```json\n{json.dumps(result, indent=2)}\n```"
                    )

                response_text = "\n".join(response_parts)
                st.markdown(response_text)

            except TimeoutError:
                logger.error("MCP server timed out during audio processing")
                response_text = (
                    "**Timeout:** The MCP server took too long to respond. "
                    "Please try again."
                )
                st.error(response_text)
            except ConnectionError as exc:
                logger.error("Connection error during audio processing: %s", exc)
                response_text = f"**Connection Error:** {exc}"
                st.error(response_text)
            except Exception as exc:
                logger.error("Unexpected error during audio processing: %s", exc)
                response_text = f"**Unexpected Error:** {exc}"
                st.error(response_text)
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    st.session_state.messages.append(
        {"role": "assistant", "content": response_text}
    )

user_input = st.chat_input("Paste a meeting transcript or ask a question...")

if user_input:
    logger.info("User submitted text query (length=%d)", len(user_input))
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Processing via MCP pipeline..."):
            logger.info("Sending text query to MCP pipeline...")
            try:
                result = invoke_meeting_assistant_sync(user_input)
                logger.info("MCP pipeline returned result with keys: %s", list(result.keys()))

                response_parts = []

                if "summary" in result:
                    response_parts.append("## 📝 Meeting Summary\n")
                    response_parts.append(result["summary"])
                    response_parts.append("\n")

                if "action_items" in result:
                    response_parts.append("## ✅ Action Items\n")
                    response_parts.append(result["action_items"])
                    response_parts.append("\n")

                if "answer" in result:
                    response_parts.append(result["answer"])

                if "error" in result:
                    response_parts.append(f"⚠️ **Error:** {result['error']}")

                if not response_parts:
                    # Fallback: show raw result
                    response_parts.append(
                        f"```json\n{json.dumps(result, indent=2)}\n```"
                    )

                response_text = "\n".join(response_parts)
                st.markdown(response_text)

            except TimeoutError:
                logger.error("MCP server timed out during text query processing")
                response_text = (
                    "⏱️ **Timeout:** The MCP server took too long to respond. "
                    "Please try again."
                )
                st.error(response_text)

            except ConnectionError as exc:
                logger.error("Connection error during text query: %s", exc)
                response_text = f"🔌 **Connection Error:** {exc}"
                st.error(response_text)

            except RuntimeError as exc:
                logger.error("Runtime error during text query: %s", exc)
                response_text = f"⚠️ **Error:** {exc}"
                st.error(response_text)
                
            except Exception as exc:
                logger.error("Unexpected error during text query: %s", exc)
                response_text = f"❌ **Unexpected Error:** {exc}"
                st.error(response_text)

    st.session_state.messages.append(
        {"role": "assistant", "content": response_text}
    )
