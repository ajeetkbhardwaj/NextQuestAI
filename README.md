# NextQuestAI - Deep Research Assistant

A Perplexity-like AI system with multi-agent orchestration, web search, and LLM reasoning. Built with LangGraph and Gradio.

## 🌟 Features

- **Multi-Agent Pipeline**: Planner → Search → Scrape → Analyze → Synthesize
- **Deep Research Mode**: Multi-round analysis with self-correction
- **Web Search**: DuckDuckGo, Tavily with automatic fallback
- **LLM Providers**: Ollama, OpenAI, Anthropic, Gemini, HuggingFace, Nvidia (with reasoning extraction)
- **Streaming Responses**: Real-time answer generation
- **Source Citations**: Proper attribution with clickable links
- **Research Trace**: Visible thinking process
- **Observability**: Structured logging, progress tracking, token monitoring
- **Performance**: Circuit breakers, adaptive concurrency, persistent cache
- **Health Checks**: Component-level health monitoring

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Ollama (optional, for local inference)

```bash
ollama pull gemma4:e2b
ollama serve
```

### 3. Run the Application

```bash
python src/ui.py
```

Visit `http://localhost:7860`

---

## Using LLM Providers

### Nvidia (Recommended for Reasoning)

```bash
NVIDIA_API_KEY=your-key
LLM_PROVIDER=nvidia
LLM_MODEL=deepseek-ai/deepseek-v4-pro
```

### OpenAI

```bash
OPENAI_API_KEY=sk-your-key
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
```

### Anthropic

```bash
ANTHROPIC_API_KEY=sk-ant-your-key
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
```

### Ollama (Local)

```bash
LLM_PROVIDER=ollama
LLM_MODEL=gemma4:e2b
OLLAMA_BASE_URL=http://localhost:11434/v1
```

### Gemini

```bash
GEMINI_API_KEY=your-key
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.0-flash
```

---

## Project Structure

```
nexusai/
├── src/
│   ├── __init__.py
│   ├── agents.py          # Agent nodes (planner, search, scrape, analyzer, synthesizer)
│   ├── config.py          # Configuration management with Pydantic
│   ├── database.py       # SQLite history storage
│   ├── llm.py            # LLM client wrapper (6 providers)
│   ├── models.py         # AgentState, data models, agent settings
│   ├── observability.py  # StructuredLogger, ProgressTracker, TokenMonitor
│   ├── performance.py     # CircuitBreaker, FallbackChain, PersistentCache, HealthMonitor
│   ├── prompts.py        # System prompts for agents
│   ├── resilience.py      # Retry logic, search cache
│   ├── scraper.py        # Content extraction with trafilatura
│   ├── search.py         # Multi-provider search (DuckDuckGo, Tavily)
│   ├── ui.py            # Gradio UI with health checks
│   └── workflow.py       # LangGraph pipeline orchestration
├── tests/
│   ├── conftest.py       # Pytest fixtures
│   ├── test_agents.py   # Agent and workflow tests
│   ├── test_scraper.py  # Scraper tests
│   └── test_search.py   # Search and performance tests
├── app.py               # Legacy Streamlit entry point
├── requirements.txt     # Python dependencies
├── Quick-Start.md       # Quick start guide
└── README.md
```

---

## Configuration

| Variable              | Default                       | Description       |
| --------------------- | ----------------------------- | ----------------- |
| `LLM_PROVIDER`      | `ollama`                    | LLM backend       |
| `LLM_MODEL`         | `gemma4:e2b`                | Model name        |
| `OLLAMA_BASE_URL`   | `http://localhost:11434/v1` | Ollama server URL |
| `SEARCH_PROVIDER`   | `duckduckgo`                | Search engine     |
| `NVIDIA_API_KEY`    | -                             | Nvidia API key    |
| `OPENAI_API_KEY`    | -                             | OpenAI API key    |
| `ANTHROPIC_API_KEY` | -                             | Anthropic API key |

---

## Docker Deployment

```bash
# With docker-compose
docker-compose up --build

# Standalone
docker build -t nexusai .
docker run -p 7860:7860 \
  -e LLM_PROVIDER=openai \
  -e OPENAI_API_KEY=your-key \
  nexusai
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

---

## Architecture

```
┌─────────────┐
│   Planner   │ → Refines query with strategy
└──────┬──────┘
       ↓
┌─────────────┐
│   Search    │ → Multi-provider search with caching
└──────┬──────┘
       ↓
┌─────────────┐
│   Scrape    │ → Content extraction (trafilatura)
└──────┬──────┘
       ↓
┌─────────────┐
│  Analyzer   │ → Fact extraction with citations
└──────┬──────┘
       ↓ (self-correction loop)
┌─────────────┐
│   Search    │ → Retry with expanded query
└──────┬──────┘
       ↓
┌─────────────┐
│ Synthesizer │ → Final answer with references
└─────────────┘
```

### Deep Research vs Quick Mode

| Setting             | Quick | Deep |
| ------------------- | ----- | ---- |
| Max Sources         | 5     | 15   |
| Max Search Results  | 10    | 20   |
| Analysis Rounds     | 1     | 3    |
| Min Facts Threshold | 3     | 5    |

---

## 📜 License

MIT License
