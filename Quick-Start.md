# NexusAI Quick-Start Guide

A multi-agent research assistant powered by LangGraph, featuring deep research capabilities, adaptive concurrency, and observability.

## Prerequisites

- Python 3.10+
- pip or conda
- (Optional) Ollama for local LLM inference

## Installation

```bash
# Clone the repository
git clone https://github.com/your-repo/nexusai.git
cd nexusai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Environment Setup

Create a `.env` file based on `.env.example`:

```bash
# LLM Providers (at least one required)
OLLAMA_BASE_URL=http://localhost:11434/v1
LLM_MODEL=gemma4:e2b
LLM_PROVIDER=ollama

# Or use OpenAI
# OPENAI_API_KEY=sk-your-key-here

# Or use Anthropic
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# Or use Nvidia
# NVIDIA_API_KEY=your-nvidia-api-key

# Search Provider
SEARCH_PROVIDER=duckduckgo
```

## Running the Application

### Option 1: Gradio UI (Recommended)

```bash
python src/ui.py
```

Access at: http://localhost:7860

### Option 2: Direct Workflow

```bash
python test_workflow.py
```

## Usage

1. **Enter a Query**: Type your research question in the text box
2. **Select Provider**: Choose from ollama, openai, anthropic, gemini, huggingface, or nvidia
3. **Choose Model**: Specify the model name (e.g., `deepseek-ai/deepseek-v4-pro`)
4. **Deep Research**: Toggle for comprehensive multi-round analysis

### Example Queries

- "What are the latest breakthroughs in quantum computing 2026?"
- "Compare LangGraph vs CrewAI for multi-agent systems"
- "What is the current state of AI regulation?"

## Deep Research Mode

When enabled:
- **3x sources** analyzed vs quick mode
- **Multi-round analysis** with self-correction
- **Higher content limits** for thorough extraction
- **Retry logic** if insufficient facts found

## API Providers

| Provider | Model Example | Notes |
|----------|--------------|-------|
| Ollama | `gemma4:e2b` | Local, privacy-focused |
| OpenAI | `gpt-4o` | Requires API key |
| Anthropic | `claude-3-5-sonnet` | Requires API key |
| Gemini | `gemini-2.0-flash` | Requires API key |
| Nvidia | `deepseek-ai/deepseek-v4-pro` | Supports reasoning extraction |
| HuggingFace | `meta-llama/Llama-3.2-3B` | Requires API key |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_agents.py -v

# Run with coverage
pytest tests/ --cov=src
```

## Architecture

```
┌─────────────┐
│   Planner   │ → Refines query
└──────┬──────┘
       ↓
┌─────────────┐
│   Search    │ → Fetches results
└──────┬──────┘
       ↓
┌─────────────┐
│   Scrape    │ → Extracts content
└──────┬──────┘
       ↓
┌─────────────┐
│  Analyzer   │ → Extracts facts
└──────┬──────┘
       ↓ (if facts < threshold)
┌─────────────┐
│   Search    │ → Retry with expanded query
└──────┬──────┘
       ↓
┌─────────────┐
│ Synthesizer │ → Generates final answer
└─────────────┘
```

## Troubleshooting

**Ollama not connecting?**
```bash
ollama serve
```

**Search returning no results?**
- Check internet connection
- Try a different search provider

**Rate limiting?**
- Reduce concurrency settings
- Add API keys for premium providers

## License

MIT License
