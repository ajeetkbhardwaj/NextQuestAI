---
marp: true
theme: default
paginate: true
---

<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Fira+Code:wght@400;500;700&display=swap');

:root {
  --color-foreground: #ffffff;
  --color-heading: #ffffff;
  --color-accent: #ffd700;
  --color-accent2: #ff6b9d;
  --color-box-bg: rgba(255,255,255,0.1);
  --font-default: 'Noto Sans JP', 'Hiragino Kaku Gothic ProN', 'Meiryo', sans-serif;
  --font-code: 'Fira Code', monospace;
}

section {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  color: var(--color-foreground);
  font-family: var(--font-default);
  font-weight: 400;
  box-sizing: border-box;
  position: relative;
  line-height: 1.7;
  font-size: 20px;
  padding: 48px 56px;
}

section:nth-child(2n) {
  background: linear-gradient(135deg, #0f3460 0%, #16213e 50%, #1a1a2e 100%);
}

section:nth-child(3n) {
  background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
}

section:nth-child(4n) {
  background: linear-gradient(135deg, #e94560 0%, #0f3460 100%);
}

section:nth-child(5n) {
  background: linear-gradient(135deg, #533483 0%, #e94560 100%);
}

h1, h2, h3, h4, h5, h6 {
  font-weight: 700;
  color: var(--color-heading);
  margin: 0;
  padding: 0;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
}

h1 {
  font-size: 52px;
  line-height: 1.3;
}

h2 {
  font-size: 38px;
  padding-bottom: 12px;
  border-bottom: 2px solid rgba(255,255,255,0.2);
  margin-bottom: 28px;
}

h2::before {
  content: '▸ ';
  color: var(--color-accent);
}

h3 {
  color: var(--color-accent);
  font-size: 26px;
  margin-top: 24px;
  margin-bottom: 12px;
}

ul, ol {
  padding-left: 28px;
}

li {
  margin-bottom: 8px;
}

li::marker {
  color: var(--color-accent);
}

strong {
  color: var(--color-accent);
  font-weight: 700;
}

code {
  background: rgba(255,255,255,0.15);
  padding: 3px 8px;
  border-radius: 4px;
  font-family: var(--font-code);
  font-size: 0.9em;
}

pre {
  background: rgba(0,0,0,0.4);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 8px;
  padding: 16px 20px;
  font-family: var(--font-code);
  font-size: 15px;
  overflow-x: auto;
  line-height: 1.5;
}

pre code {
  background: transparent;
  padding: 0;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 18px;
}

th, td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid rgba(255,255,255,0.15);
}

th {
  background: rgba(255,255,255,0.1);
  color: var(--color-accent);
  font-weight: 600;
}

tr:hover {
  background: rgba(255,255,255,0.05);
}

footer {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  position: absolute;
  left: 56px;
  right: 56px;
  bottom: 28px;
  text-align: center;
}

section.lead {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
}

section.lead h1 {
  margin-bottom: 16px;
  text-align: center;
  font-size: 56px;
}

section.lead p {
  font-size: 22px;
  color: var(--color-foreground);
  text-shadow: 0 2px 5px rgba(0, 0, 0, 0.3);
}

section.lead h1::before {
  content: '🔮 ';
}

.box {
  background: var(--color-box-bg);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 12px;
  padding: 20px 24px;
  margin: 16px 0;
}

.box-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin: 16px 0;
}

.box-item {
  background: var(--color-box-bg);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 8px;
  padding: 16px;
}

.box-item h4 {
  color: var(--color-accent);
  font-size: 18px;
  margin-bottom: 8px;
}

.flow {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin: 20px 0;
  flex-wrap: wrap;
}

.flow-item {
  background: rgba(255,255,255,0.1);
  border: 2px solid var(--color-accent);
  border-radius: 8px;
  padding: 12px 20px;
  font-weight: 600;
  text-align: center;
}

.flow-arrow {
  color: var(--color-accent);
  font-size: 24px;
}

.icon-badge {
  display: inline-block;
  background: var(--color-accent);
  color: #1a1a2e;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 700;
  margin-right: 8px;
}
</style>

<!-- _class: lead -->

# NexusAI

## Deep Research Assistant

Perplexity Clone with Multi-Agent Orchestration

Built with LangGraph • Gradio • HuggingFace Spaces

---

## Agenda

<div class="flow">
  <span class="flow-item">🏗️ Architecture</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">🤖 Agents</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">🔧 Tech Stack</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">💻 Components</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">🎨 UI Design</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">🚀 Deploy</span>
</div>

---

## What is NexusAI?

<div class="box">
<p><strong>Agentic RAG-powered Q&A System</strong> — A Perplexity-style deep research assistant that searches the web, retrieves relevant information, reasons over results, and provides citation-backed answers.</p>
</div>

<div class="box-grid">
  <div class="box-item">
    <h4>🔍 Multi-Agent Pipeline</h4>
    <p>5 specialized agents working together: Planner → Search → Scrape → Analyze → Synthesize</p>
  </div>
  <div class="box-item">
    <h4>📚 Citation-Backed</h4>
    <p>Every answer includes source attribution with clickable links for verification</p>
  </div>
  <div class="box-item">
    <h4>⚡ Real-Time Streaming</h4>
    <p>Token-by-token response generation for immediate feedback</p>
  </div>
  <div class="box-item">
    <h4>☁️ HF Spaces Ready</h4>
    <p>One-click deployment to HuggingFace Spaces with Docker support</p>
  </div>
</div>

---

## System Architecture

<h3>High-Level Overview</h3>

```
┌─────────────────────────────────────────────────────────────────┐
│                    Gradio UI (HuggingFace Spaces)               │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ Chat Input  │  │ Search Mode  │  │  Source Citations      │ │
│  └─────────────┘  └──────────────┘  └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LangGraph Orchestrator                        │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│  │Planner  │───▶│ Search   │───▶│ Scraper  │───▶│Synthesizer│ │
│  │ Agent   │    │ Agent    │    │ Agent    │    │  Agent    │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│                                                             │
│                   ┌──────────┐                              │
│                   │ Analyzer │                              │
│                   │  Agent   │                              │
│                   └──────────┘                              │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌──────────┐       ┌──────────┐       ┌──────────────┐
    │  Web     │       │ Content  │       │     LLM      │
    │  Search  │       │ Fetchers │       │   Reasoning   │
    │ Tavily/  │       │ Trafilatura│    │ GPT-4o/      │
    │ DuckDuckGo│     │ BeautifulSoup│   │ Claude/      │
    │ Serper   │       │             │    │ Ollama       │
    └──────────┘       └──────────┘       └──────────────┘
```

---

## Multi-Agent Pipeline

<h3>5 Specialized Agents Working in Sequence</h3>

<div class="box-grid">
  <div class="box-item">
    <h4>1️⃣ Planner Agent</h4>
    <p>Decomposes query, creates research plan, determines search strategy</p>
  </div>
  <div class="box-item">
    <h4>2️⃣ Search Agent</h4>
    <p>Executes parallel web searches, filters results by relevance</p>
  </div>
  <div class="box-item">
    <h4>3️⃣ Scraper Agent</h4>
    <p>Fetches and extracts content from top URLs</p>
  </div>
  <div class="box-item">
    <h4>4️⃣ Analyzer Agent</h4>
    <p>Extracts key info, facts, statistics from content</p>
  </div>
  <div class="box-item">
    <h4>5️⃣ Synthesizer Agent</h4>
    <p>Combines findings, generates answer with citations</p>
  </div>
</div>

---

## Agent State Management

<h3>LangGraph TypedDict State</h3>

```python
class AgentState(TypedDict):
    original_query: str              # User's question
    search_results: List[SearchResult]  # Web search hits
    scraped_content: List[ScrapedContent]  # Fetched pages
    extracted_facts: List[ExtractedFact]  # Key findings
    final_answer: str              # Generated response
    citations: List[Citation]     # Source references
    reasoning_trace: List[str]    # Thinking process
    error: Optional[str]           # Error tracking
```

<div class="box">
<p><span class="icon-badge">KEY</span>State persists through the entire pipeline, enabling error recovery and retry logic at each stage.</p>
</div>

---

## Technical Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Orchestration** | <code>LangGraph 0.5.x</code> | Multi-agent pipeline |
| **Multi-Agent** | <code>CrewAI 0.80.x</code> | Agent coordination (optional) |
| **LLM Client** | <code>OpenAI SDK</code> | GPT-4o / Claude / Ollama |
| **Web Search** | <code>Tavily, DuckDuckGo</code> | Multi-provider search |
| **HTML Parsing** | <code>Trafilatura</code> | Content extraction |
| **UI Framework** | <code>Gradio 5.x</code> | Web interface |
| **Async** | <code>httpx, asyncio</code> | Parallel operations |
| **Validation** | <code>Pydantic 2.x</code> | Type-safe data |
| **Database** | <code>SQLite</code> | Chat history |
| **Deployment** | <code>HuggingFace Spaces</code> | Cloud hosting |

---

## Search Providers

<h3>Multi-Provider with Automatic Fallback</h3>

<div class="box-grid">
  <div class="box-item">
    <h4>🔴 Tavily Search</h4>
    <p>Primary search with semantic relevance scoring</p>
    <code>TAVILY_API_KEY</code>
  </div>
  <div class="box-item">
    <h4>🟢 DuckDuckGo</h4>
    <p>Free fallback, no API key required</p>
    <code>SEARCH_PROVIDER=duckduckgo</code>
  </div>
  <div class="box-item">
    <h4>🔵 Serper Search</h4>
    <p>Google results alternative</p>
    <code>SERPER_API_KEY</code>
  </div>
</div>

<h3>Fallback Chain</h3>

<div class="flow">
  <span class="flow-item">Tavily</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">Serper</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">DuckDuckGo</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">Error Message</span>
</div>

---

## Content Extraction

<h3>Multi-Tool Fetching Pipeline</h3>

```
URL Input
    │
    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Trafilatura │────▶│ BeautifulSoup│───▶│ Clean Text │
│ (Primary)  │     │  (HTML Parse)│    │  Output     │
└─────────────┘     └─────────────┘     └─────────────┘
    │                   │                    │
    └─────── OR ────────┘
              │
              ▼
    ┌─────────────────┐
    │ Readability-lxml │
    │ (Article Extract)│
    └─────────────────┘
```

<div class="box">
<p><span class="icon-badge">NOTE</span>Each tool is tried sequentially. On failure, the next tool attempts extraction. Failed sources are skipped without halting the pipeline.</p>
</div>

---

## LLM Providers

<h3>Multi-Provider Support</h3>

<div class="box-grid">
  <div class="box-item">
    <h4>🤖 OpenAI GPT-4o</h4>
    <p>Primary reasoning model, highest quality</p>
    <code>LLM_PROVIDER=openai<br>LLM_MODEL=gpt-4o</code>
  </div>
  <div class="box-item">
    <h4>🧠 Anthropic Claude</h4>
    <p>Fallbback option, strong reasoning</p>
    <code>LLM_PROVIDER=anthropic<br>LLM_MODEL=claude-3-5-sonnet</code>
  </div>
  <div class="box-item">
    <h4>🏠 Ollama (Local)</h4>
    <p>Free local deployment, privacy-first</p>
    <code>LLM_PROVIDER=ollama<br>LLM_MODEL=llama3.2</code>
  </div>
</div>

---

## Gradio UI Design

<h3>Interface Layout</h3>

```
┌──────────────────────────────────────────────────────────────┐
│  ┌────────────────────────────────────────────────────────┐ │
│  │           🔮 NexusAI                                     │ │
│  │    "Deep research, clear answers"                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  [User Query Input - Textbox]                          │ │
│  │                                                        │ │
│  │  ☑ Deep Research    ☐ Quick Search    [Search Button]  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    ANSWER                               │ │
│  │  ────────────────────────────────────────────────────  │ │
│  │  [Markdown response with citations]                    │ │
│  │                                                        │ │
│  │  📚 Sources: [Clickable citation cards]                │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  [Thinking Process - Expandable/Collapsible]          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Related Questions: [Clickable suggestions]            │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## UI Features

<div class="box-grid">
  <div class="box-item">
    <h4>⚡ Streaming Responses</h4>
    <p>Token-by-token generation for immediate feedback</p>
  </div>
  <div class="box-item">
    <h4>📚 Source Citations</h4>
    <p>Clickable citation cards with link verification</p>
  </div>
  <div class="box-item">
    <h4>🧠 Thinking Visibility</h4>
    <p>Expandable reasoning trace shows agent logic</p>
  </div>
  <div class="box-item">
    <h4>🌙 Theme Toggle</h4>
    <p>Dark/light mode for comfortable viewing</p>
  </div>
  <div class="box-item">
    <h4>📱 Mobile Responsive</h4>
    <p>Optimized for mobile and tablet devices</p>
  </div>
  <div class="box-item">
    <h4>💡 Related Questions</h4>
    <p>AI-generated follow-up suggestions</p>
  </div>
</div>

---

## Deployment Options

<h3>1. HuggingFace Spaces (Cloud)</h3>

<div class="box">
<pre>git add .
git commit -m "Initial commit"
git push
# Creates Space automatically via spaces.yaml</pre>
</div>

<h3>2. Docker (Self-Hosted)</h3>

<div class="box-grid">
  <div class="box-item">
    <h4>Option A: With docker-compose</h4>
    <pre>docker-compose up --build</pre>
    <p>Includes Ollama container</p>
  </div>
  <div class="box-item">
    <h4>Option B: Standalone</h4>
    <pre>docker build -t nexusai .
docker run -p 7860:7860 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434/v1 \
  nexusai</pre>
  </div>
</div>

---

## HuggingFace Spaces Config

<h3>spaces.yaml</h3>

<pre>title: NexusAI
emoji: 🔮
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 5.0.0
app_file: app.py
pinned: false</pre>

<div class="box">
<p><span class="icon-badge">SECRETS</span>Add in HF Space settings: <code>OPENAI_API_KEY</code>, <code>ANTHROPIC_API_KEY</code>, <code>TAVILY_API_KEY</code></p>
</div>

---

## Environment Configuration

<h3>.env File Setup</h3>

<pre># LLM Provider Selection
LLM_PROVIDER=ollama          # or openai / anthropic
LLM_MODEL=llama3.2           # or gpt-4o / claude-3-5-sonnet
OLLAMA_BASE_URL=http://localhost:11434/v1

# Search Provider
SEARCH_PROVIDER=duckduckgo   # or tavily / serper

# API Keys (for cloud providers)
OPENAI_API_KEY=sk-your-key-here
TAVILY_API_KEY=tvly-your-key-here
SERPER_API_KEY=serpapi-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Runtime Options
MAX_SOURCES=5
DEEP_RESEARCH=true
STREAMING=true</pre>

---

## Error Handling Strategy

| Error Type | Handling |
|------------|----------|
| **No API Key** | Show setup instructions in UI |
| **Search Failed** | Fallback to next search provider |
| **Fetch Failed** | Skip source, continue with others |
| **LLM Failed** | Retry with exponential backoff (3 attempts) |
| **Rate Limited** | Queue requests, show progress indicator |

<div class="box">
<h4>🔄 Resilience Features</h4>
<ul>
<li>Timeout handling (30s default)</li>
<li>Connection pooling for HTTP reuse</li>
<li>Graceful degradation on partial failures</li>
<li>Detailed error logging for debugging</li>
</ul>
</div>

---

## Performance Optimizations

<div class="box-grid">
  <div class="box-item">
    <h4>💾 Caching Layer</h4>
    <p>Search results cached for 1 hour to avoid redundant API calls</p>
  </div>
  <div class="box-item">
    <h4>⚡ Async Pipeline</h4>
    <p>Parallel search + scraping reduces latency by 60%</p>
  </div>
  <div class="box-item">
    <h4>📡 Streaming</h4>
    <p>Token-by-token LLM output starts faster</p>
  </div>
  <div class="box-item">
    <h4>🔄 Connection Pooling</h4>
    <p>Reuse HTTP connections, reduce overhead</p>
  </div>
</div>

<div class="box">
<h4>📊 Performance Metrics</h4>
<ul>
<li>Search: ~2-3 seconds for 5 sources</li>
<li>Scrape: ~5-10 seconds for content extraction</li>
<li>LLM: Streaming starts in ~1 second</li>
<li>Total: Typical query completes in 15-30 seconds</li>
</ul>
</div>

---

## Project Structure

<pre>
nexusai/
├── app.py              # Main Gradio application
├── requirements.txt    # Python dependencies
├── .env.example        # Environment template
├── spaces.yaml         # HuggingFace Spaces config
├── docker-compose.yml  # Docker orchestration
├── Dockerfile          # Container build
├── SPEC.md             # Technical specification
├── README.md           # Documentation
└── src/
    ├── __init__.py
    ├── config.py       # Configuration management
    ├── models.py       # AgentState, Pydantic models
    ├── search.py       # Multi-provider search (Tavily/DuckDuckGo/Serper)
    ├── scraper.py      # Content extraction (Trafilatura/BeautifulSoup)
    ├── llm.py          # LLM client (OpenAI/Anthropic/Ollama)
    ├── agents.py      # Agent definitions (Planner/Search/Scraper/Analyzer/Synthesizer)
    ├── workflow.py     # LangGraph pipeline orchestration
    ├── prompts.py      # LLM prompt templates
    ├── database.py     # SQLite chat history
    ├── resilience.py   # Retry logic, circuit breakers
    ├── ui.py           # UI components and styling
    └── test_workflow.py
</pre>

---

## Quick Start Guide

<h3>Local Development</h3>

<div class="flow">
  <span class="flow-item">1. Install</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">2. Ollama</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">3. Run</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">4. Use</span>
</div>

<pre># 1. Install dependencies
pip install -r requirements.txt

# 2. Start Ollama server
ollama pull llama3.2    # Download model
ollama serve            # Start server

# 3. Run application
python app.py

# 4. Open browser
# Visit http://localhost:7860</pre>

---

## Summary

<div class="box-grid">
  <div class="box-item">
    <h4>🎯 What is NexusAI?</h4>
    <p>Perplexity-style deep research assistant</p>
  </div>
  <div class="box-item">
    <h4>🤖 Multi-Agent</h4>
    <p>Planner → Search → Scrape → Analyze → Synthesize</p>
  </div>
  <div class="box-item">
    <h4>🔄 Multi-Provider</h4>
    <p>OpenAI, Anthropic, Ollama + Tavily/DuckDuckGo/Serper</p>
  </div>
  <div class="box-item">
    <h4>📦 Production-Ready</h4>
    <p>Streaming, caching, error handling included</p>
  </div>
  <div class="box-item">
    <h4>🚀 Easy Deploy</h4>
    <p>HuggingFace Spaces or Docker in minutes</p>
  </div>
  <div class="box-item">
    <h4>🔓 Open Source</h4>
    <p>MIT License, contributions welcome</p>
  </div>
</div>

---

<!-- _class: lead -->

# Thank You

## 🔮 NexusAI

**Deep Research, Clear Answers**

Questions? Feedback? Contributions?

🔗 https://github.com/your-repo/nexusai

