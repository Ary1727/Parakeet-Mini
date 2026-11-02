# Parakeet Mini

A small Windows desktop app inspired by Parakeet AI. It listens to your microphone, shows a live transcript, and streams an AI-written answer to the question you just heard. Speech-to-text and the language model both run on your own computer.

## What it does

1. **Start** begins listening to the default microphone. Each time you stop talking, that phrase is transcribed and added to the transcript box.
2. **Stop** stops listening and transcribes any speech still in progress.
3. **Suggest Answer** sends the transcript to a local language model. The answer appears word by word as it is generated.

The transcript box is editable, so you can fix a misheard word before asking for an answer.

## How it works

| Part | Tool | File |
| --- | --- | --- |
| Window | Tkinter (ships with Python) | `app.py` |
| Microphone capture | sounddevice | `transcriber.py` |
| Speech-to-text | faster-whisper (Whisper `base.en`, runs on the CPU) | `transcriber.py` |
| Answer generation | Ollama running `llama3.2` | `llm.py` |

The microphone is read in 0.1 second blocks. A phrase ends after 0.8 seconds of silence, or after 20 seconds of continuous speech, and is then sent to Whisper. Very short noises are ignored.

## Setup (Windows)

You need Python 3.11 or 3.12 and Ollama.

**1. Install Ollama and download the model**

Install Ollama from https://ollama.com, then run:

```powershell
ollama pull llama3.2
```

Ollama runs in the background and listens on `http://localhost:11434`.

**2. Install the app**

```powershell
cd parakeet-mini
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activation script, run `Set-ExecutionPolicy -Scope Process Bypass` first.

**3. Run it**

```powershell
python app.py
```

The first time you press Start, the Whisper `base.en` model (about 150 MB) is downloaded once and cached. After that, nothing leaves your computer.

## Settings

Set these environment variables before running to change the defaults:

| Variable | Default | Purpose |
| --- | --- | --- |
| `WHISPER_MODEL` | `base.en` | Speech model. `tiny.en` is faster, `small.en` is more accurate. |
| `OLLAMA_MODEL` | `llama3.2` | Any model you have pulled with Ollama. |
| `OLLAMA_URL` | `http://localhost:11434` | Where Ollama is running. |

Example:

```powershell
$env:OLLAMA_MODEL = "llama3.2:1b"
python app.py
```

## Troubleshooting

- **No transcription appears:** Open Windows Settings, go to Privacy and security, then Microphone, and allow desktop apps to use the microphone. Also check the correct microphone is set as the default input device.
- **"Cannot reach Ollama":** Start Ollama, then press Suggest Answer again.
- **"model not found":** Run `ollama pull llama3.2`, or set `OLLAMA_MODEL` to a model you already have.
- **Transcription is slow:** Use `WHISPER_MODEL=tiny.en`.
- **Answers are slow:** Use a smaller model such as `llama3.2:1b`.

## Limits

- English only.
- Transcription happens after each pause, not word by word.
- It listens to the microphone only. It does not capture audio playing from the computer.

## License

MIT. See [LICENSE](LICENSE).
