import os

import requests


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash-lite"

def generate_summary(transcript: str) -> str:
    if not transcript or not transcript.strip():
        raise ValueError("Transcript is empty, cannot generate summary")

    api_key = os.environ.get("GOOGLE_API_KEY")
    model_name = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured")

    prompt = f"""
    Summarize the following meeting transcript

    Transcript:
    {transcript}
    """

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
    except requests.HTTPError as exc:
        body = response.text[:500]
        raise RuntimeError(
            f"Gemini request failed with status {response.status_code}: {body}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Gemini returned a non-JSON response") from exc

    try:
        return payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Gemini response format: {payload}") from exc
