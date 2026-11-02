import json
import os

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
MAX_QUESTION_CHARS = 1500
SYSTEM_PROMPT = (
    "You are a helpful assistant listening to a conversation. "
    "The user will give you a transcript. Find the most recent question in it "
    "and answer it clearly and briefly in a few sentences. "
    "If the transcript has no question, reply with a short, helpful response to what was said."
)


class LLMError(Exception):
    pass


def stream_answer(transcript):
    text = transcript.strip()[-MAX_QUESTION_CHARS:]
    payload = {
        "model": OLLAMA_MODEL,
        "stream": True,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    }
    try:
        with requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            stream=True,
            timeout=(5, 300),
        ) as response:
            if response.status_code != 200:
                raise LLMError(_error_message(response))
            for line in response.iter_lines(chunk_size=1):
                if not line:
                    continue
                data = json.loads(line)
                if "error" in data:
                    raise LLMError(data["error"])
                piece = data.get("message", {}).get("content", "")
                if piece:
                    yield piece
                if data.get("done"):
                    break
    except requests.exceptions.ConnectionError:
        raise LLMError(f"Cannot reach Ollama at {OLLAMA_URL}. Start Ollama and try again.")
    except requests.exceptions.Timeout:
        raise LLMError("Ollama took too long to respond.")


def _error_message(response):
    try:
        detail = response.json().get("error", "")
    except ValueError:
        detail = response.text.strip()
    if response.status_code == 404:
        return f"{detail or 'Model not found'}. Run: ollama pull {OLLAMA_MODEL}"
    return detail or f"Ollama returned status {response.status_code}"
