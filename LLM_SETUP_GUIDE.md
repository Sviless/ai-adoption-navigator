# LLM Enhanced Mode - Setup Guide

The app works fully offline in **Template Engine Mode**. LLM Enhanced Mode adds AI judgment and tailored narratives on top. It never changes the calculated scores or ROI numbers.

## Option 1: Local model with Ollama (private, free, no API key)

Use case data never leaves your machine, which is a good fit for confidential proposals.

1. Install Ollama from https://ollama.com
2. Pull a model: `ollama pull llama3.1` (or `qwen2.5`, `mistral`)
3. Make sure it is running (`ollama serve`, or the Ollama desktop app)
4. In the app sidebar, choose **Mode: LLM Enhanced**, then **Provider: Ollama (local, no API key)**
5. Keep the default URL `http://localhost:11434` unless you changed it

Larger local models give noticeably better results. Small models may occasionally return invalid JSON; the app then falls back to template output.

## Option 2: Cloud provider with an API key

| Provider | Install | Environment variable | Suggested models |
|---|---|---|---|
| Anthropic Claude | `pip install anthropic` | `ANTHROPIC_API_KEY` | `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5` |
| OpenAI | `pip install openai` | `OPENAI_API_KEY` | `gpt-4o-mini`, `gpt-4o` |
| Google Gemini | Nothing (uses the REST API) | `GEMINI_API_KEY` | `gemini-2.5-flash`, `gemini-2.5-pro` |
| Groq | `pip install groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |

You can type any other model name your provider supports into the model box.

**Gemini and Ollama: load your real model list.** After pasting a Gemini key, click **Load my models** in the sidebar. The app asks Google which models your key can use, newest first, and shows only text models (no embedding, speech or image models). For Ollama, **Installed models** lists the models on your machine. New models appear in the list automatically, with no app update needed.

**Provide the key** in either of two ways:
- Paste it into the sidebar **API key** field. It is kept in memory for the current session only and never written to disk.
- Or set the environment variable before starting the app (PowerShell example):
  ```powershell
  $env:ANTHROPIC_API_KEY = "your-key"
  python -m streamlit run app.py
  ```

## What changes in LLM Enhanced Mode

| Feature | Where |
|---|---|
| Executive summary written for the specific context | Use case > Summary |
| "Skeptical CFO" assumption challenges (tagged **AI**) | Use case > Summary |
| Why this risk tier fits, and which controls matter most | Use case > Governance & risk |
| Tailored workforce and adoption recommendations | Use case > People & adoption |
| Pilot adjustments and extra risks (tagged **AI**) | Use case > Pilot plan |
| Smart intake that understands free text | Use case > Intake |
| Root-cause style value gap diagnosis with sponsor summary | Value tracker view |

The LLM runs only when you click **Save and assess**, **Re-assess**, **Extract fields** or **Diagnose**, so there are no surprise API costs.

## Troubleshooting
- **"No API key - using Template mode"**: paste a key or set the environment variable.
- **"LLM enhancement failed..." warning**: the app is showing template output. Check the key, model name, rate limits, or that Ollama is running.
- **Library not installed**: install the SDK for your provider (table above).
