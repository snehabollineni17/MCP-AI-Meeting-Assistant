# AI Meeting Assistant — MCP Server + Client + Streamlit UI

An MCP (Model Context Protocol) based AI Meeting Assistant that processes meeting transcripts to generate summaries and action items using Google Gemini.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set environment variables

```bash
set GOOGLE_API_KEY=your_google_api_key_here
```

### 3. Run the Streamlit app

```bash
streamlit run streamlit_app.py
```

### 4. (Optional) Test the MCP server directly

```bash
python mcp_server.py
```

This starts the server in stdio mode — useful for testing with MCP-compatible clients or VS Code.

## Usage

1. **Paste a meeting transcript** (longer than 200 characters) to get:
   - A concise **summary** of the meeting
   - Extracted **action items** with owners and deadlines

2. **Ask a question** (shorter text) to get an AI-generated answer about meetings, agendas, or best practices.

## Tool: `process_meeting_query`

The single MCP tool exposed by the server. It accepts a `query` string and returns a JSON object:

- For transcripts: `{ "summary": "...", "action_items": "..." }`
- For questions: `{ "answer": "..." }`
- On error: `{ "error": "..." }`
