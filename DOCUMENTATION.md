# NedCard Intelligent Suite — Complete System Documentation

> **Written for:** Anyone — engineering team, business users, new joiners — who wants to understand what was built, why every piece exists, and how it all fits together.
> **Last updated:** 3 March 2026
> **Project location:** `/text_to_sql_demo/`

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [How a Query Flows Through the System](#2-how-a-query-flows-through-the-system)
3. [The Four Intelligence Domains](#3-the-four-intelligence-domains)
4. [Folder Structure — The Full Map](#4-folder-structure--the-full-map)
5. [Root-Level Files](#5-root-level-files)
6. [Backend — The Brain](#6-backend--the-brain)
7. [RAG & Document Intelligence](#7-rag--document-intelligence)
8. [Unified Router — The Intelligence Layer](#8-unified-router--the-intelligence-layer)
9. [Streamlit Frontend — Rapid Demo Interface](#9-streamlit-frontend--rapid-demo-interface)
10. [React Frontend — NedCard UI (Production-Grade)](#10-react-frontend--nedcard-ui-production-grade)
11. [Data — The Synthetic Database](#11-data--the-synthetic-database)
12. [Evals — Measuring Quality](#12-evals--measuring-quality)
13. [MLflow — Observability](#13-mlflow--observability)
14. [Architecture Documents](#14-architecture-documents)
15. [Infrastructure — Running in the Cloud](#15-infrastructure--running-in-the-cloud)
16. [How to Start Everything Locally](#16-how-to-start-everything-locally)
17. [Key Design Decisions Explained](#17-key-design-decisions-explained)
18. [Glossary — Plain English Definitions](#18-glossary--plain-english-definitions)

---

## 1. What This Project Is

**NedCard Intelligent Suite** is a production-ready AI assistant that lets Nedbank staff ask questions about sensitive business data — in plain English — and get intelligent answers back, instantly.

Instead of a data analyst writing SQL queries and waiting for a report, a user opens a **single unified chat interface** and types something like:

> *"Which branches have the highest credit decline rates this month, and is there a correlation with increased fraud activity?"*

The AI figures out which data to look at, queries the database itself, reasons about the results, and responds in natural language — in seconds. It can even fan out across multiple specialist agents simultaneously and synthesise their findings into one coherent answer.

**What makes it "agentic":** The AI doesn't answer from memory. It actively **uses tools** — querying databases, fetching social media posts, transcribing call recordings — then reasons about what it finds, and acts again if needed. This loop of *think → act → observe → think again* is called a **ReAct loop**. That loop is the foundation of the system.

**Two frontends serve the same backend:**
- **NedCard UI** (`nedcard-ui/`) — the production-grade React/TypeScript interface. Single unified chat page, voice recording, file attachment, live charts with fullscreen expand, animated thinking steps, domain-aware response badges.
- **Streamlit** (`frontend/`) — the rapid-prototype Python interface, built for speed of iteration and internal demos.

---

## 2. How a Query Flows Through the System

### Unified Chat Path (NedCard UI → Unified Router)

This is the primary production path. Every question from the chat interface goes to one endpoint:

```
User types a question in ChatPage.tsx
        │
        ▼
  submit(query) branches:

  ┌─ PATH A ─ file attached ─────────────────────────────────────────────────
  │  uploadDocument(file) → POST /api/documents/upload
  │    ├─ is_audio? → extract_audio() (Whisper-1) → transcript
  │    ├─ else      → extract_text() (PyMuPDF / UTF-8 decode)
  │    ├─ chunk_text() → embed_chunks() → save_chunks()
  │    └─ GPT-4o with _CALL_ANALYSIS_SYSTEM / _SUMMARY_SYSTEM
  │  if question typed → submitDocQuery() [RAG only, no duplicate summary]
  │  if no question    → display auto-summary
  │  → setActiveDocId + activeDocName banner
  │
  ├─ PATH B ─ activeDocId set ─────────────────────────────────────────
  │  queryDocument(activeDocId, question) → POST /api/documents/{id}/query
  │    ├─ embed question → cosine search top-k chunks
  │    └─ GPT-4o with _CALL_RAG_SYSTEM / _RAG_SYSTEM → grounded answer
  │
  └─ PATH C ─ no file, no active doc ────────────────────────────────
     POST /api/unified/query
        │
        ▼
  unified.py → _classify(query)
```
     ┌─────────────────────────────────────────────────┐
     │  Is this conversational? ("Hi", "Thanks", etc.) │
     │    YES → _conversational_reply()                │──► Direct OpenAI call
     │          (no LangGraph, no SQL tools, ~50ms)    │    "Hello! How can I help?"
     │    NO  → Which domain?                          │
     │           fraud keywords → fraud_sql_graph      │
     │           sentiment keywords → sentiment_graph  │
     │           speech keywords → speech_graph        │
     │           credit signals OR default → credit    │
     │           multiple domains → fan-out (parallel) │
     └─────────────────────────────────────────────────┘
        │
        ▼
  invoke_agent(graph, query, session_id)
     ┌─────────────────────────────────────────────────┐
     │  LangGraph ReAct loop                           │
     │  1. Think: what do I need?                      │
     │  2. Call a tool (SQL, schema, chart, etc.)      │◄──► Tools → SQLite DB
     │  3. Read tool result                             │
     │  4. Enough? → Answer    Not enough? → Loop      │
     └─────────────────────────────────────────────────┘
        │
        ├─► extract_chart_from_messages()  ← scans for __CHART__:{json}:__ENDCHART__ marker
        │
        ├─► compute_inline_scores()        ← sql_valid, sql_safe, answer_quality
        │
        ├─► mlflow.update_current_trace()  ← logs everything to MLflow
        │
        ▼
  AgentResponse {
    answer, sql_query, table_data, chart_data,
    latency_ms, eval_scores, agent_label
  }
        │
        ▼
  ChatPage.tsx renders:
    • Domain pill (only if agent_label is non-null)
    • DynamicChart (above message bubble, if chart_data exists)
    • MessageBubble (typewriter animation)
```

### Multiple Domains (Parallel Fan-out)

If the query spans multiple domains (e.g. "compare credit declines vs social sentiment"):

```
_classify() returns [credit_domain, sentiment_domain]
        │
        ▼
asyncio.gather(invoke_agent(credit_graph,...), invoke_agent(sentiment_graph,...))
        │
        ▼
_synthesise() → GPT-4o merges both answers into one coherent response
```

Every step — every tool call, every LLM reasoning step — is captured as a span in MLflow.

---

## 3. The Four Intelligence Domains

| Domain | Agent file | What it answers | Data source |
|---|---|---|---|
| **Credit Intelligence** | `credit_sql_agent.py` | Loan applications, approval rates, decline reasons, credit scores, branch performance | `credit_applications` (500 rows) |
| **Fraud Intelligence** | `fraud_sql_agent.py` | Fraud patterns, risk scores, merchant categories, case volumes, financial exposure | `fraud_transactions` (300 rows) |
| **Social Sentiment** | `sentiment_agent.py` | Customer opinion on X/LinkedIn, brand perception, complaint themes, topic trends | `social_posts` (400 rows) |
| **CX & Speech** | `speech_agent.py` | Call recordings, agent performance scores, customer experience, complaint analysis | `call_transcripts` (50 rows) + Whisper API |

All four share the same LangGraph architecture (see `base_graph.py`). Only the tools and system prompts differ.

**Default fallback:** If a query doesn't match any domain pattern, it routes to Credit Intelligence (the most common use case for this context).

---

## 4. Folder Structure — The Full Map

```
text_to_sql_demo/                  ← Project root
│
├── .env                           ← Secret keys and config (never committed to git)
├── .env.example                   ← Template showing what .env should contain
├── .gitignore                     ← Tells git what NOT to save (keys, databases, etc.)
├── Makefile                       ← Shortcut commands (make eval, make dev-frontend, etc.)
├── pyproject.toml                 ← Python project metadata
├── mlflow.db                      ← MLflow's SQLite database (stores all run/trace history)
│
├── backend/                       ← The AI brain — FastAPI + LangGraph
│   ├── Dockerfile                 ← How to package backend for Docker
│   ├── requirements.txt           ← Python libraries the backend needs
│   ├── app/
│   │   ├── main.py                ← App entry point — starts FastAPI, loads config
│   │   ├── config.py              ← Reads .env, makes settings available everywhere
│   │   ├── agents/                ← LangGraph agent definitions
│   │   ├── routers/               ← HTTP endpoints (/api/credit, /api/fraud, /api/documents, etc.)
│   │   │   ├── credit_sql.py      ← POST /api/credit/query
│   │   │   ├── fraud_sql.py       ← POST /api/fraud/query
│   │   │   ├── sentiment.py       ← POST /api/sentiment/query
│   │   │   ├── speech.py          ← POST /api/speech/query, /api/speech/tts
│   │   │   ├── unified.py         ← POST /api/unified/query ★ primary production endpoint
│   │   │   └── documents.py       ← POST /api/documents/upload + /query, RAG pipeline (NEW)
│   │   ├── tools/                 ← The actions agents can take
│   │   ├── schemas/               ← Data shapes (what requests/responses look like)
│   │   ├── db/                    ← Database connection and models
│   │   ├── rag/                   ← RAG pipeline (NEW)
│   │   │   ├── parser.py          ← Text extraction (PDF/CSV/MD) + Whisper audio transcription
│   │   │   ├── embedder.py        ← OpenAI ada-002 embeddings per chunk
│   │   │   └── store.py           ← SQLite vector store: save + cosine-similarity search
│   │   └── evals/                 ← Evaluation framework (metrics, golden dataset, harness)
│   └── tests/                     ← Automated test suite (38 tests)
│
├── frontend/                      ← The user interface — Streamlit
│   ├── Dockerfile                 ← How to package frontend for Docker
│   ├── requirements.txt           ← Python libraries the frontend needs
│   ├── app.py                     ← Main app file — sets up navigation between pages
│   ├── api_client.py              ← All calls to the backend go through here
│   ├── components/
│   │   └── eval_badge.py          ← Shared UI component — shows eval scores per response
│   └── pages/
│       ├── 1_Credit_SQL.py        ← Credit Application page
│       ├── 2_Fraud_SQL.py         ← Fraud Intelligence page
│       ├── 3_Sentiment_Analysis.py← Social Sentiment page
│       └── 4_Speech_Insights.py   ← Speech & CX page
│
├── data/                          ← Synthetic data generation and seeding
│   ├── seed_db.py                 ← Master script — runs all generators, populates the database
│   ├── seeds/
│   │   └── dev.db                 ← The SQLite database file (1,250 rows total)
│   └── synthetic/
│       ├── generate_credit_data.py
│       ├── generate_fraud_data.py
│       ├── generate_social_data.py
│       └── generate_speech_transcripts.py
│
├── nedcard-ui/                    ← React/TypeScript production-grade frontend (port 3002)
│   ├── package.json               ← Node dependencies (React 18, Vite 5, Tailwind 3, Framer Motion)
│   ├── vite.config.ts             ← Vite dev server + proxy config (/api/* → localhost:8000)
│   ├── tailwind.config.js         ← Custom design tokens (ned-green, ned-dark, ned-slate, etc.)
│   ├── index.html                 ← HTML entry point
│   └── src/
│       ├── main.tsx               ← React entry point (renders <App />)
│       ├── App.tsx                ← BrowserRouter + AuthProvider + ChatHistoryProvider + routes
│       ├── index.css              ← Global styles, chat-scroll utility
│       ├── lib/
│       │   └── api.ts             ← Axios wrapper: queryAgent, transcribeToText, getSentimentChartData
│       ├── types/
│       │   └── index.ts           ← All TypeScript interfaces: AgentResponse, ChatMessage, etc.
│       ├── context/
│       │   ├── AuthContext.tsx    ← Login/logout state, sessionStorage persistence
│       │   └── ChatHistoryContext.tsx ← In-memory chat history keyed by API endpoint
│       ├── components/
│       │   ├── ChatWindow.tsx     ← Reusable chat UI for legacy domain pages
│       │   ├── DynamicChart.tsx   ← Bar/line/pie charts + fullscreen modal (createPortal)
│       │   ├── MessageBubble.tsx  ← Single message: avatar, content, SQL, table
│       │   ├── SentimentInlineChart.tsx ← Donut+bar chart for sentiment-specific data
│       │   ├── DataTable.tsx      ← Tabular data display component
│       │   ├── Layout.tsx         ← Sidebar + Outlet wrapper for legacy pages
│       │   ├── Sidebar.tsx        ← Navigation sidebar
│       │   └── TypingIndicator.tsx← Three-dot loading animation
│       └── pages/
│           ├── LoginPage.tsx      ← Auth gate with mock login
│           ├── ChatPage.tsx       ← PRIMARY unified chat (voice, file attach, all domains)
│           ├── WelcomePage.tsx    ← Domain selection landing page
│           ├── DashboardPage.tsx  ← Executive overview page
│           ├── CreditPage.tsx     ← Dedicated credit chat (legacy page)
│           ├── FraudPage.tsx      ← Dedicated fraud chat (legacy page)
│           ├── SentimentPage.tsx  ← Sentiment + live charts (legacy page)
│           └── SpeechPage.tsx     ← Speech CX chat (legacy page)
│
├── docs/                          ← Architecture and reference documents
│   ├── routing-vs-isolated.html   ← 9-section teardown: isolated vs routing architectures
│   ├── architecture-visual.html   ← Animated SVG comparison diagram
│   ├── production-vision.html     ← High-fidelity UI prototype
│   ├── power-prompts.html         ← 5 business + 5 engineering diagnostic prompts
│   └── system-blueprint.html      ← This documentation rendered as visual HTML
│
├── infra/                         ← Infrastructure as code
│   ├── docker/
│   │   └── docker-compose.yml     ← Runs all services together with one command
│   └── k8s/                       ← Kubernetes manifests (for Azure AKS deployment)
│       ├── deployments.yaml
│       ├── backend-deployment.yaml
│       └── secrets.yaml
│
└── secrets/                       ← Docker secret files (empty placeholder, gitignored)
    └── .gitkeep
```

---

## 5. Root-Level Files

### `.env` — The Secret Vault
**What it is:** A plain text file containing all sensitive configuration — API keys, database URLs, environment settings.

**Why it matters:** Without this file, nothing works. It tells the app which OpenAI account to bill, which MLflow server to talk to, and what kind of environment it's running in (development vs production).

**What's inside:**
```
OPENAI_API_KEY=sk-proj-...        ← Your OpenAI billing key
MLFLOW_TRACKING_URI=http://localhost:5000  ← Where MLflow is running
MLFLOW_EXPERIMENT_NAME=text-to-sql-demo   ← What experiment bucket to log to
DB_URL=sqlite+aiosqlite:///./data/seeds/dev.db  ← Where the database is
ENVIRONMENT=development
BACKEND_URL=http://localhost:8000
LANGSMITH_TRACING=false           ← We use MLflow instead
```

**Critical rule:** This file is in `.gitignore` — it will never be accidentally uploaded to GitHub. `.env.example` is the safe, shareable version with placeholders instead of real values.

---

### `Makefile` — The Shortcut Menu
**What it is:** A file of named commands. Instead of typing long terminal commands, you type `make <name>`.

**Key commands:**
```
make seed          ← Generate all synthetic data and populate the database
make dev-frontend  ← Start the Streamlit web app
make dev-mlflow    ← Start the MLflow server
make eval          ← Run batch evaluations against the live backend
make eval-judge    ← Run evals + LLM-as-judge scoring
make eval-credit   ← Run credit use case evals only
make test          ← Run the full test suite
make lint          ← Check code quality
make clean         ← Remove generated files and caches
```

---

### `pyproject.toml` — Project Identity Card
**What it is:** A standard Python file that describes the project — its name, Python version requirements, and code quality tool settings (like ruff for linting).

**Who uses it:** Developers and CI/CD pipelines. Not touched during normal use.

---

## 6. Backend — The Brain

The backend is a **FastAPI application** that receives questions from the frontend and returns answers. It lives entirely in `backend/`.

---

### `backend/app/main.py` — The Front Door

**What it does:** This is the entry point. When you run `uvicorn app.main:app`, Python starts here. It:
1. Loads all configuration settings from `.env`
2. Pushes the OpenAI API key into the system environment (so OpenAI calls work)
3. Registers all four routers (credit, fraud, sentiment, speech)
4. Adds health check endpoint at `/health`
5. Sets up CORS (so the frontend can talk to it across browser security rules)

**Touches:** Everything. It's the wiring harness of the entire backend.

---

### `backend/app/config.py` — The Settings Manager

**What it does:** Uses a library called `pydantic-settings` to read the `.env` file and make every setting available as a typed Python object. Any file in the backend can import `settings` and access `settings.openai_api_key`, `settings.mlflow_experiment_name`, etc.

**Why this pattern matters:** Instead of looking up environment variables scattered across dozens of files, there's one single source of truth. If a setting name changes, you change it in one place.

**Key settings it manages:**
- `openai_api_key` — for all LLM calls
- `openai_model` — which GPT model to use (default: `gpt-4o`)
- `openai_whisper_model` — for speech transcription (default: `whisper-1`)
- `mlflow_tracking_uri` — where to send traces and metrics
- `mlflow_experiment_name` — which experiment bucket in MLflow
- `db_url` — the database connection string

---

### `backend/app/agents/` — The AI Agents

This folder contains the LangGraph agent definitions. Think of an agent as an AI that has been given a job description and a toolbox.

#### `base_graph.py` — The Agent Blueprint

**What it does:** Defines the shared infrastructure all four agents use:
- `BaseAgentState` — the memory structure every agent carries (current messages, session ID, original query)
- `build_react_graph()` — a factory function that builds a LangGraph ReAct agent from a list of tools and a system prompt. All four agents call this function.
- `call_model()` — the function that calls GPT-4o and wraps it in an MLflow trace span
- `log_agent_run()` — logs latency and model info to MLflow as a formal run

**The ReAct loop (what build_react_graph creates):**
```
Start
  │
  ▼
[agent node] ← GPT-4o decides what to do
  │
  ├─ "I need more info" → [tools node] → tool runs → back to [agent node]
  │
  └─ "I have enough" → END → return answer
```

**MLflow configuration at module level:**
When this file is imported, it immediately:
1. Sets the MLflow tracking URI
2. Sets the experiment name (`text-to-sql-demo`)
3. Enables `mlflow.openai.autolog()` — this automatically captures every OpenAI API call as a trace span without any extra code

#### `credit_sql_agent.py`, `fraud_sql_agent.py`, `sentiment_agent.py`, `speech_agent.py`

**What they are:** Each one is a thin file that:
1. Defines the system prompt for that use case (the AI's job description)
2. Lists which tools the agent has access to
3. Calls `build_react_graph()` to get a compiled agent

**Example — credit_sql_agent.py in plain English:**
> "You are a banking data analyst. You have two tools: one that tells you the database schema, and one that executes SQL. Use them to answer questions about credit applications. Always show the SQL you used. Never make up data."

---

### `backend/app/routers/` — The HTTP Endpoints

Routers are the API surface — the URLs the frontend calls.

#### `_agent_utils.py` — The Shared Invocation Logic

**What it does:** Every router uses this single function to run an agent. It handles:
1. Creating a session ID if one isn't provided
2. Opening an MLflow root trace span (the parent that all child spans attach to)
3. Calling `graph.ainvoke()` — running the agent asynchronously
4. Measuring latency
5. Extracting the final answer and any SQL from the agent's message history
6. Computing inline eval scores (`sql_valid`, `sql_safe`, `answer_quality`)
7. Attaching all of that to the MLflow trace
8. Calling `log_agent_run()` to log metrics to the MLflow experiment
9. Returning the result as a structured dictionary

**The MLflow tracing pattern:**
```python
with mlflow.start_span(name="agent:credit-sql", span_type=SpanType.AGENT) as span:
    span.set_inputs({"query": query, ...})
    result = await graph.ainvoke(initial_state)  # ← async agent runs here
    span.set_outputs({"answer": answer[:500], ...})
```
When this `with` block exits, the entire trace (including all child spans from tool calls and LLM calls) is flushed to MLflow.

#### `credit_sql.py`, `fraud_sql.py`, `sentiment.py`, `speech.py`

**What they are:** Each file registers two HTTP routes:
- `POST /api/<use-case>/query` — accepts a question, returns an answer
- `GET /api/<use-case>/examples` — returns example questions for the UI

They are thin wrappers — they receive the HTTP request, call `invoke_agent()`, and return the result. All the real logic is in `_agent_utils.py` and the agent itself.

---

### `backend/app/tools/` — The Agent's Hands

Tools are functions the agent can call. They are decorated with `@tool` (LangChain) and `@mlflow.trace` (MLflow).

#### `sql_tools.py` — Database Tools

Four tools, each decorated with `@mlflow.trace(span_type=SpanType.TOOL)`:

| Tool | What it does |
|---|---|
| `get_credit_schema()` | Returns the column names and types of the `credit_applications` table so the agent knows what it can query |
| `execute_credit_sql(sql)` | Executes a SQL query against the credit table and returns results as JSON |
| `get_fraud_schema()` | Returns the schema of `fraud_transactions` |
| `execute_fraud_sql(sql)` | Executes SQL against the fraud table |

**Why schema tools exist:** The agent doesn't have the database schema memorised. On first call, it asks for the schema, then uses that knowledge to write correct SQL. This is a common pattern in text-to-SQL agentic systems — it makes the agent self-sufficient even if the schema changes.

**Safety architecture:**
```
LLM generates SQL
        │
        ▼
_validate_sql() — regex rejects INSERT/UPDATE/DELETE/DROP/ALTER
        │
        ▼
_run_sql() — executes against readonly_engine (no write permission at DB level)
        │
        ▼
Row limit wrapper — LIMIT 200 enforced via sub-query wrapping
```

Two independent safety layers: code-level rejection + DB-level permission restriction.

#### `chart_tools.py` — Visualisation Tools

Contains `execute_credit_sql_chart` and `execute_fraud_sql_chart` — enhanced variants of the SQL tools that embed structured chart data in their return string.

**The string marker pattern — how chart data travels from tool to frontend:**

1. Agent calls `execute_credit_sql_chart(sql, title, chart_type, x_key, y_key)`
2. Tool runs the SQL (same safety checks as sql_tools)
3. Tool builds a return string: `narrative text\n\n__CHART__:{json_payload}:__ENDCHART__`
4. LangGraph stores this as a `ToolMessage` in the agent's state
5. After `graph.ainvoke()` finishes, `extract_chart_from_messages()` scans all ToolMessages for the marker
6. Returns the parsed JSON as `chart_data` → travels in `AgentResponse.chart_data` → rendered by `DynamicChart.tsx`

**Why a string marker instead of a ContextVar?** LangGraph's `ToolNode` uses `asyncio.gather()` internally, creating new async Tasks. Each Task gets a **copy** of ContextVar context at creation — mutations inside those Tasks vanish when they finish. The string in the ToolMessage travels inside LangGraph's own state (the messages list), which survives `ainvoke()` intact.

**`_build_tool_response(title, chart_type, x_key, y_key, rows, color_key)`** — assembles the narrative + chart marker string returned by chart tools.

#### `sentiment_tools.py` — Social Media Tools

| Tool | What it does |
|---|---|
| `fetch_social_posts(limit, platform, topic)` | Queries the `social_posts` table — can filter by platform (X/LinkedIn) and topic |
| `get_sentiment_breakdown()` | Returns aggregated positive/neutral/negative counts and percentages |

#### `whisper_tools.py` — Speech Tools

| Tool | What it does |
|---|---|
| `transcribe_audio(audio_bytes_b64, filename)` | Sends a base64-encoded audio file to OpenAI Whisper API, returns transcribed text |
| `get_transcript_from_db(call_id)` | Fetches a stored transcript from the `call_transcripts` table |
| `list_available_transcripts(limit)` | Lists available call records (date, agent, reason, resolution status) |

---

### `backend/app/schemas/responses.py` — The Data Contracts

**What it does:** Defines the exact shape of every request and response using Pydantic models. Think of these as typed forms — the app will reject any data that doesn't match the expected shape.

**Key schemas:**

`AgentRequest` — what the frontend sends:
```
query:      "What are the top 5 decline reasons?"  (required, max 2000 chars)
session_id: "abc-123..."                            (optional, for trace grouping)
```

`AgentResponse` — what the backend returns:
```
answer:      "The top 5 decline reasons are..."    (the AI's response)
sql_query:   "SELECT decline_reason, COUNT(*)..."  (SQL used, if applicable)
table_data:  [{...}, {...}]                         (raw data rows, if any)
chart_data:  {chart_type, title, x_key, y_key, rows}  (chart payload, if any)
latency_ms:  2341.5                                 (how long the agent took)
eval_scores: {"eval/sql_valid": 1.0, ...}          (quality scores)
agent_label: "Credit Intelligence"                 (domain specialist used, or null)
trace_id:    null                                   (reserved for trace linking)
```

**`agent_label` is critical for the frontend domain badge.** When `null`, it means the query was handled conversationally (no specialist agent was invoked) and the domain badge is suppressed. When set, it names the specialist(s) that responded (e.g. `"Credit Intelligence + Social Sentiment"`).

---

### `backend/app/db/` — The Database Layer

#### `session.py` — Database Connections

Creates two SQLAlchemy engine objects:
- `engine` — read/write (used only for seeding data)
- `readonly_engine` — read-only (used by all agent tools — safety by design)

Both are **async** (non-blocking), which means the FastAPI server can handle many requests simultaneously without each database call blocking the others.

#### `models.py` — The Database Tables

Defines all four database tables in Python using SQLAlchemy ORM:
- `CreditApplication` — 500 synthetic credit applications
- `FraudTransaction` — 300 synthetic fraud cases
- `SocialPost` — 400 synthetic social media posts
- `CallTranscript` — 50 synthetic call centre recordings

#### `db/migrations/` — Schema Version Control

Managed by Alembic. If the database schema ever needs to change (new column, renamed table), migration scripts are created here so the change is tracked and reversible.

---

### `backend/tests/` — The Test Suite

**38 tests** across three files, all runnable with `make test`.

| File | What it tests |
|---|---|
| `test_api_endpoints.py` | Every HTTP endpoint responds correctly — status codes, response shapes |
| `test_sql_tools.py` | The SQL tools return valid data, handle bad input gracefully |
| `test_data_generators.py` | The synthetic data generators produce correct row counts and valid data |
| `conftest.py` | Shared test setup — creates a test database, test client, mock data |

---

## 7. RAG & Document Intelligence

The RAG (Retrieval-Augmented Generation) module lets users upload documents or audio recordings directly in the chat and ask questions grounded on the actual file content — not model memory. It lives in `backend/app/rag/` and is orchestrated by `backend/app/routers/documents.py`.

---

### `backend/app/rag/parser.py` — Text & Audio Extraction

Routes extraction by file type:

| Function / Symbol | What it does |
|---|---|
| `AUDIO_EXTENSIONS` | Frozenset: `{mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg, flac}`. Any extension in this set routes to Whisper |
| `extract_text(filename, content)` | Async dispatcher — PyMuPDF for PDFs, raw UTF-8 decode for text/CSV/Markdown |
| `extract_audio(filename, content)` | Async — wraps bytes in `io.BytesIO`, sets `.name` attribute (SDK uses this for MIME detection), calls OpenAI Whisper-1, returns full transcript string |
| `chunk_text(text, size, overlap)` | Splits full text into overlapping windows (default 800 chars, 80 char overlap). Returns `list[str]` |

> **Whisper file size limit:** OpenAI enforces a 25 MB hard cap. The `documents.py` router checks this before calling `extract_audio()`.

---

### `backend/app/rag/embedder.py` — Chunk Embeddings

Converts text chunks into 1536-dimensional float vectors using OpenAI `text-embedding-ada-002`. Vectors are serialised as JSON float lists and stored in the `document_chunks` SQLite column.

```python
embed_chunks(chunks: list[str]) -> list[list[float]]
```

---

### `backend/app/rag/store.py` — SQLite Vector Store

Persists chunk embeddings and retrieves semantically relevant chunks via cosine similarity.

| Function | What it does |
|---|---|
| `save_chunks(doc_id, chunks, embeddings)` | Inserts one `DocumentChunk` row per chunk into `document_chunks` |
| `search_chunks(doc_id, query_vec, top_k)` | Loads all embeddings for a doc, computes cosine similarity against query vector, returns top-k sorted by relevance |

---

### `backend/app/routers/documents.py` — RAG Pipeline Orchestrator ★

Four endpoints that wire together the entire ingestion → retrieval → answer pipeline.

**Endpoints:**

| Endpoint | What it does |
|---|---|
| `POST /api/documents/upload` | Accept file → detect type → extract text/audio → chunk → embed → save ORM rows → GPT-4o summary → return `{doc_id, filename, summary, latency_ms}` |
| `POST /api/documents/{doc_id}/query` | Embed question → cosine search top-k chunks → GPT-4o grounded answer. Uses `_CALL_RAG_SYSTEM` for audio docs, `_RAG_SYSTEM` for text docs |
| `GET /api/documents/list` | Returns all uploaded documents (id, filename, file_type, created_at) |
| `DELETE /api/documents/{doc_id}` | Removes document + all its chunks |

**Size limits:**
```
Audio files (.mp3/.wav/.webm etc.) → 25 MB (Whisper API hard cap)
Documents  (.pdf/.txt/.csv etc.)  → 50 MB
```

**System prompt personalities:**

| Prompt | Used when | Behaviour |
|---|---|---|
| `_SUMMARY_SYSTEM` | Auto-summary of a document | Concise document overview |
| `_RAG_SYSTEM` | Q&A against a document | Strictly grounded; no invention beyond the provided chunks |
| `_CALL_ANALYSIS_SYSTEM` | Auto-summary of an audio upload | 5-section call-centre assessor: **Call overview · Client sentiment (with quotes) · Agent performance · Compliance & risk flags · Client needs & recommended actions** |
| `_CALL_RAG_SYSTEM` | Q&A against a call transcript | Grounded on transcript context; refers to "the client" and "the agent"; supports sentiment/quality assessments with direct transcript quotes |

**Audio routing flag:**
```python
is_audio = file_type in AUDIO_EXTENSIONS
# When True: extract_audio() instead of extract_text()
#            _CALL_ANALYSIS_SYSTEM for summaries
#            _CALL_RAG_SYSTEM for follow-up queries
# All other steps (chunk → embed → store) are identical
```

---

## 8. Unified Router — The Intelligence Layer

`backend/app/routers/unified.py` is the central routing brain that makes the single chat interface work across all four domains. It exposes one endpoint: `POST /api/unified/query`.

### `_DOMAINS` — The Domain Registry

An ordered list of domain descriptors. Each entry has a `key`, a display `label`, a compiled `pattern` regex, and a reference to the compiled `graph`:

```python
[
  { "key": "fraud",     "label": "Fraud Intelligence",  "pattern": re.compile(r"fraud|transact|suspicious...") },
  { "key": "sentiment", "label": "Social Sentiment",    "pattern": re.compile(r"sentiment|social|twitter...") },
  { "key": "speech",    "label": "CX & Speech",         "pattern": re.compile(r"call.?cent|transcript|voice...") },
  { "key": "credit",    "label": "Credit Intelligence", "pattern": re.compile(r".*") },  ← default fallback
]
```

Order matters. Fraud is tested before the credit wildcard, so fraud-related queries don't fall through to the credit agent.

### `_CONVERSATIONAL` — The Bypass Pattern

```python
_CONVERSATIONAL = re.compile(
    r"^\s*(?:hi+|hello+|hey+|good\s+(?:morning|afternoon)|thank(?:s| you)|..."
    r"how\s+are\s+you|what\s+can\s+you\s+do|who\s+are\s+you|help(?:\s+me)?)\s*[?!.]*\s*$"
)
```

When matched (or when the query is ≤3 words with no domain keywords), `_classify()` returns `_GENERAL_DOMAIN = {"key": "general", "label": None}`. The endpoint then calls `_conversational_reply()` — a direct OpenAI Chat Completions call using `_GENERAL_SYSTEM` prompt. No LangGraph, no tools, no database. Response in ~50–200ms. `agent_label` returns as `null`.

### `_classify(query)` — The Routing Decision

```python
def _classify(query: str) -> list[dict]:
    # 1. Conversational? → general bypass
    if _CONVERSATIONAL.match(query) or (short query with no domain keywords):
        return [_GENERAL_DOMAIN]
    # 2. Chart follow-up + sentiment signals? → sentiment only
    if _CHART_FOLLOWUP.search(query) and _SENTIMENT_SIGNALS.search(query):
        return [sentiment_domain]
    # 3. Both credit AND sentiment signals? → multi-domain fan-out
    if _CREDIT_SIGNALS.search(query) and _SENTIMENT_SIGNALS.search(query):
        return [credit_domain, sentiment_domain]
    # 4. First domain pattern match wins
    for domain in _DOMAINS:
        if domain["pattern"].search(query):
            return [domain]
```

### `_synthesise()` — Multi-Domain Answer Merging

When multiple agents respond, GPT-4o is called once more via `_synthesise(query, answers)` to merge both answers into a single coherent narrative. The synthesis system prompt instructs:
- Match tone to complexity (no forced "Executive Summary" headers for simple questions)
- Integrate numbers naturally
- One "So what?" sentence only when it adds genuine value

### The Endpoint Flow

```
POST /api/unified/query
  1. _classify(query)
  2. If general → _conversational_reply() → return immediately
  3. If specialist(s) → asyncio.gather(*[invoke_agent(d["graph"], ...) for d in domains])
  4. Collect results, extract chart_data (chart tool output takes priority)
  5. If multiple agents → _synthesise()
  6. agent_label = " + ".join(d["label"] for d in domains) — or None for general
  7. Return AgentResponse
```

---

## 9. Streamlit Frontend — Rapid Demo Interface

The Streamlit frontend is a **Python-only web application** built for rapid prototyping and internal demos. It lives in `frontend/`. For the production-grade UX, see Section 9 (React Frontend).

---

### `frontend/app.py` — The Navigation Shell

**What it does:** The entry point for Streamlit. It:
1. Sets the page title, icon, and sidebar layout
2. Defines the navigation menu (4 use case pages + a health check)
3. Shows the backend connection status in the sidebar
4. Displays the tech stack credits at the bottom

**What it does NOT do:** Any AI logic. It's purely navigation and layout.

---

### `frontend/api_client.py` — The Messenger

**What it does:** Every single HTTP call from the frontend to the backend goes through this one file. It uses `httpx` (a Python HTTP library) configured with:
- Base URL: `http://localhost:8000` (or whatever `BACKEND_URL` is set to)
- Timeout: 120 seconds (LLM calls can take time)

**Key functions:**
- `query_agent(endpoint, query, session_id)` — sends a question, returns the full response dict
- `get_examples(endpoint)` — fetches example queries for the dropdown buttons
- `check_health()` — pings `/health` to show connection status in the sidebar
- `list_call_transcripts()` — used by the Speech page to show available recordings
- `upload_audio(audio_bytes, filename, prompt)` — uploads an audio file for Whisper transcription

**Design principle:** The frontend is a "dumb terminal" — it sends questions and displays answers. It has no knowledge of LangGraph, MLflow, or OpenAI. All intelligence lives in the backend. This separation makes the frontend easy to replace (e.g. swap Streamlit for a React app) without changing a single line of backend code.

---

### `frontend/pages/` — The Four Use Case Pages

Each page follows the same structure:

```
1. Set page title and description
2. Initialise session state (conversation history, session ID)
3. Show quick metrics or charts (where relevant)
4. Show example query buttons
5. Display conversation history (past questions and answers)
6. Text input box at the bottom
7. On submit:
   a. Record start time (for client-side latency)
   b. Call api_client.query_agent()
   c. Record end time
   d. Display the answer
   e. Show generated SQL in expandable panel
   f. Show data table if rows were returned
   g. Call render_response_footer() for latency + eval badges
   h. Save to session history
```

#### `1_Credit_SQL.py` — Credit Application Page
Shows 500 synthetic credit applications. Has example buttons for common analyst queries. Displays the generated SQL so users can see how the AI is querying the data.

#### `2_Fraud_SQL.py` — Fraud Intelligence Page
Shows 300 fraud cases. Includes a quick-metrics bar at the top (confirmed fraud %, suspected %, cleared %). Data tables with `risk_score` column get colour-coded gradients (red = high risk).

#### `3_Sentiment_Analysis.py` — Social Sentiment Page
Includes a static dashboard at the top with:
- A donut chart showing sentiment breakdown (positive/neutral/negative)
- A bar chart of post volume by topic (Credit, Service, Fraud, App, Fees)
- Platform split metrics (X vs LinkedIn)

Below the charts is a chat interface for natural language queries.

#### `4_Speech_Insights.py` — Speech & CX Page
Three tabs:
- **Upload Audio** — drag-and-drop or record via microphone, Whisper transcribes it, GPT-4o analyses it
- **Browse Stored Transcripts** — dropdown of 50 pre-generated call recordings from the database
- **Ask Questions** — free-form chat about call data

---

### `frontend/components/eval_badge.py` — The Quality Indicator (Streamlit)

**What it does:** A shared component called at the bottom of every agent response. It renders:

```
⏱ Backend 2,341ms  ·  Network +87ms  ·  🟢 SQL valid  ·  🟢 SQL safe  ·  🟢 Answer quality  ·  Session abc12345  ·  Trace in MLflow ↗
```

**The coloured dots:**
- 🟢 Score ≥ 0.9 — all good
- 🟡 Score ≥ 0.4 — borderline, check the answer
- 🔴 Score < 0.4 — something went wrong

If any score is below ideal, it shows an expandable warning with a plain-English explanation of what failed and why.

**The two latency numbers:**
- **Backend latency** — measured by the server's own timer from the moment the agent starts to when it finishes
- **Network overhead** — client-side round-trip minus backend latency — this is the network + serialisation cost

---

## 10. React Frontend — NedCard UI (Production-Grade)

The NedCard UI is a **React 18 + TypeScript application** built for production-quality UX. It lives in `nedcard-ui/` and runs on **port 3002** via Vite's dev server. It communicates with the same FastAPI backend on port 8000.

---

### Technology Stack

| Library | Version | Role |
|---|---|---|
| React | 18 | Component model and rendering |
| TypeScript | 5 | Type safety across the entire frontend |
| Vite | 5 | Dev server (port 3002), HMR, build tool, `/api/*` proxy |
| Tailwind CSS | 3.4 | Utility-first styling with custom `ned-*` design tokens |
| Framer Motion | 11 | Animations — messages, thinking steps, chart modal |
| React Router | 6 | Client-side routing (BrowserRouter, ProtectedRoute) |
| Recharts | 2 | SVG charts (bar, line, pie) |
| Axios | — | HTTP client (`lib/api.ts`), 120s timeout |
| lucide-react | — | Icons (Send, Mic, Paperclip, X, ChevronDown, etc.) |

**Custom Tailwind design tokens** (`tailwind.config.js`):
```
ned-green  #00C66A   ← Primary action colour (send button, active states)
ned-dark   #0D1117   ← Page background
ned-dark2  #161B22   ← Header, panel backgrounds
ned-slate  #1C2333   ← Input area, card backgrounds
ned-muted  #6B7A8E   ← Placeholder text, secondary labels
```

---

### `src/main.tsx` — React Entry Point

Renders `<App />` into `#root`. Starting point for the entire React application. **Critical — required.**

---

### `src/App.tsx` — The Router Shell

Sets up `<AuthProvider>`, `<ChatHistoryProvider>`, and `<BrowserRouter>`. Route `/` redirects to `/chat` — the unified chat page is the default entry point. `ProtectedRoute` checks `isAuthenticated` and redirects to `/login` when false. **Required.**

---

### `src/types/index.ts` — TypeScript Contracts

All shared TypeScript interfaces. Key types:
- **`AgentResponse`** — includes `agent_label?: string | null` — controls domain badge visibility
- **`ChatMessage`** — `id`, `role`, `content`, `timestamp`, `latency_ms`, optional `sql_query`, `table_data`, `chart_data`
- **`ChartData`** — sentiment-specific chart shape (breakdown, topic_distribution, platform_split, etc.)

**Required — TypeScript compilation fails without it.**

---

### `src/lib/api.ts` — The HTTP Client

Axios instance with 120-second timeout.

| Function | What it does |
|---|---|
| `queryAgent(endpoint, query, sessionId)` | POST to any unified/domain agent endpoint |
| `uploadDocument(file)` | Multipart POST to `/api/documents/upload` — ingest PDF/audio/text into RAG pipeline; returns `{doc_id, filename, summary}` |
| `queryDocument(docId, question, sessionId)` | POST to `/api/documents/{id}/query` — RAG Q&A against a previously uploaded document |
| `uploadAudio(blob, filename, prompt, sessionId)` | Multipart speech upload to `/api/speech/transcribe` (Streamlit path) |
| `getSentimentChartData(params)` | GET filtered sentiment chart data |
| `textToSpeech(text, voice, model)` | _Retained in api.ts but no longer used by `handleSpeak`._ POST `/api/speech/tts` → MP3 Blob. `handleSpeak` now uses raw `fetch` + `MediaSource` for streaming playback instead. |

**Required — no backend communication without it.**

---

### `src/context/AuthContext.tsx` — Login State

Stores the logged-in user in `sessionStorage` (survives page refresh, clears on browser close). Exports `useAuth()` hook: `{ user, login(user), logout(), isAuthenticated }`. **Required.**

---

### `src/context/ChatHistoryContext.tsx` — Persistent Conversation Memory

Stores conversation history in `useRef<Record<string, ChatMessage[]>>({})` — keyed by endpoint URL. Uses `useRef` (not `useState`) so history writes do not trigger re-renders. Exposes `getHistory(key)`, `setHistory(key, messages)`, `clearHistory(key?)`.

---

### `src/pages/ChatPage.tsx` — The Primary Interface

**Most important file in the frontend.** All domain questions flow through this unified chat page.

#### Three-Path Submit Logic

**PATH A — file attached:**
1. `uploadDocument(file)` → POST `/api/documents/upload`
2. If question typed alongside upload → skip auto-summary, call `submitDocQuery()` immediately (prevents two responses)
3. If no question → display auto-summary / call analysis report
4. Sets `activeDocId` + `activeDocName` amber banner for follow-up questions

**PATH B — `activeDocId` set:**
- `queryDocument(activeDocId, question)` → RAG Q&A against the active document. Banner stays until user clicks ×.

**PATH C — no file, no active doc:**
- `queryAgent('/api/unified/query', ...)` → normal multi-domain pipeline.

#### Voice Recording (MediaRecorder API) — Redesigned

The mic no longer transcribes to text client-side. The new flow:
1. `startRecording()` creates `MediaRecorder(stream, {mimeType:'audio/webm'})`
2. On stop: assembles Blob → wraps as `new File([blob], 'voice-recording-{ts}.webm')` → `setAttachedFile(file)`
3. Audio file then travels through PATH A (Whisper transcription + call analysis on server side)

Live `m:ss` timer (red pill, `setInterval 1000ms`) resets on stop. Textarea placeholder reads "Recording… click mic to stop & attach".

**File input `accept` attribute:**
```
".pdf,.txt,.csv,.md,.mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm,.ogg,.flac"
```

#### TTS — Listen / Stop Button

Every completed assistant message has a speaker button below the bubble. Audio begins playing within ~1 second of clicking, thanks to a fully streaming pipeline:

**Flow (streaming path — Chrome / Firefox / Edge):**
```
handleSpeak(msgId, text)
  → fetch POST /api/speech/tts             ← raw fetch, not axios
  → ReadableStream chunks arrive from server
  → MediaSource + SourceBuffer            ← appends 4 KB chunks as they arrive
  → audio.play() called immediately       ← playback starts on first chunk
```

**Fallback (full-buffer — Safari):**
```
handleSpeak(msgId, text)
  → fetch POST /api/speech/tts → arrayBuffer() → Blob
  → URL.createObjectURL → new Audio(url).play()
```

**Backend (`speech.py` `_stream_tts`):**  
Uses `openai.audio.speech.with_streaming_response.create()` + `iter_bytes(4096)`. FastAPI's `StreamingResponse` pipes chunks to the client as OpenAI synthesises them — no server-side buffering of the full MP3.

- Toggle stops playback. Only one message plays at a time (`activeSpeaker` ref)
- State: `speakingId: string | null` drives Listen/Stop label and disables other buttons while audio plays
- `X-Accel-Buffering: no` header disables nginx proxy buffering if deployed behind a reverse proxy

#### Domain Badge — Removed from Chat Thread

The domain pill ("Credit Intelligence", etc.) was removed from above message bubbles. `domainMeta` state is still maintained internally but no longer rendered in the chat thread.

#### Thinking Indicator — Chain-of-Thought Streaming UI (Restored)

The staged multi-step loading indicator is fully active. This is the **progressive disclosure of agent reasoning** pattern — instead of a generic spinner, the UI narrates what the agent is actually doing at each execution phase.

**Step sequence (1.4 s each, driven by `setInterval` cycling `thinkingStep`):**

| Step | Label | Agent phase |
|---|---|---|
| 0 | Routing your question… | Router node classifying domain |
| 1 | *(domain-specific)* e.g. "Scanning fraud records…" | SQL agent querying the DB |
| 2 | Interpreting results… | LLM interpreting query output |
| 3 | Composing your answer… | Final response generation |

**Visual anatomy of the indicator bubble:**
- **Progress bar** — 4 pill-shaped segments that fill with the domain accent colour as steps advance
- **Spinner** — `animate-spin` SVG beside the step label (no emoji)
- **Step label** — slides in/out with `AnimatePresence mode="wait"` on each transition; colour inherits `thinkingMeta.color` (green/red/blue/purple per domain)
- **Trailing pulse dots** — 3 staggered breathing dots in the domain colour

`thinkingMeta` is set by the submit PATH that fires (PATH A → amber "Document Analysis", PATH C → detected domain). Step 1 label is overridden with the domain's `thinkLabel` from the domain-map.

#### User Avatar in MessageBubble

Every user message now has a matching avatar on the right side — a `w-11 h-11` `from-blue-500 to-purple-600` gradient circle showing the user's initials (`userInitials` prop, computed from `user?.name`). Mirrors the top-bar avatar exactly. AI messages retain the logo avatar on the left.

#### Empty-State Hero Icon Glow

The logo above "What do you need to know?" has a pulsing green glow: a `motion.span` ring behind the circle animates opacity (0.15→0.45→0.15) and scale (1→1.18→1) on a 3 s infinite `easeInOut` loop. A `boxShadow` on the circle provides a constant halo. Circle and image sizes increased to `w-36 h-36` / `w-24 h-24`.

---

### `src/components/DynamicChart.tsx` — The Charting Engine

**Shape discrimination:**
- `isSentimentChartData(data)` → `SentimentInlineChart` (donut + bar)
- `isGenericChartData(data)` → `GenericChartCard` (Recharts bar/line/pie)
- else → null

**`fmtTick(v)`** — Y-axis abbreviation: `1,500,000` → `1.5M`, `75,000` → `75K`

**`prettyKey(k)`** — label formatting: `loan_amount_requested` → `Loan Amount Requested`

**`FullscreenModal`:**
- `createPortal(..., document.body)` — bypasses parent overflow/z-index
- ESC key or backdrop click closes
- 460px chart height, `AnimatePresence` for enter/exit animation

---

### `src/components/ChatWindow.tsx`

Shared chat component used by legacy domain pages. Includes history, autocomplete (Arrow/Tab/Enter/Escape), thinking steps, typewriter, eval badges. Not used by `ChatPage.tsx`.

---

### `src/components/SentimentInlineChart.tsx`

Donut chart (positive/neutral/negative %) + bar chart (topic volume). Only for the sentiment agent's chart output shape.

---

### API Proxy (`vite.config.ts`)

```ts
server: {
  port: 3002,
  proxy: { '/api': 'http://localhost:8000' }
}
```
Proxies all `/api/*` from port 3002 to FastAPI. No CORS issues in development.

---

## 11. Data — The Synthetic Database

All data is fake (synthetic) — generated programmatically to look realistic without exposing any real customer information.

### `data/synthetic/` — The Generators

Each script uses Python's `faker` library and domain-specific logic to generate realistic-looking data.

| Script | Rows | Key fields |
|---|---|---|
| `generate_credit_data.py` | 500 | application_id, applicant_name, credit_score, loan_amount, employment_status, province, status (approved/rejected), decline_reason, assessor_comments |
| `generate_fraud_data.py` | 300 | transaction_id, amount, merchant_category, is_fraud, model_flagged, risk_score, investigator_notes |
| `generate_social_data.py` | 400 | post_id, platform (X/LinkedIn), content, sentiment (positive/neutral/negative), topic, likes, shares |
| `generate_speech_transcripts.py` | 50 | call_id, call_date, agent_name, customer_name, call_reason, transcript_text, cx_score, resolution_status |

**Total: 1,250 synthetic records across 4 tables.**

### `data/seed_db.py` — The Planter

Runs all four generators in sequence and inserts the results into `data/seeds/dev.db`. Run once with `make seed`. The database file is gitignored (too large, regenerable).

### `data/seeds/dev.db` — The Database

A SQLite file — a single-file relational database. Chosen for development because it requires zero infrastructure. In production, this would be replaced with PostgreSQL on Azure.

---

## 12. Evals — Measuring Quality

The evaluation framework lives in `backend/app/evals/`. It ensures we know whether the AI is actually doing a good job, not just whether it runs without crashing.

### Why Evals Matter

A system can return an answer to every query (no errors) while still:
- Writing SQL that doesn't actually parse
- Making up data that isn't in the database
- Giving vague one-sentence answers that don't help the user

Evals catch these problems before they reach stakeholders.

---

### Three Tiers of Evaluation

#### Tier 1 — Inline Evals (Runs on Every Query)
**Cost:** Zero — no extra API calls, runs in milliseconds.
**When:** Automatically, on every single production query.

Three deterministic scorers run immediately after the agent responds:

| Metric | What it checks | Pass condition |
|---|---|---|
| `eval/sql_valid` | Does the generated SQL actually parse? Run through SQLite's `EXPLAIN` command | 1.0 if valid, 0.0 if syntax error |
| `eval/sql_safe` | Does the SQL contain any dangerous keywords (`DROP`, `DELETE`, `INSERT`, `ALTER`, `TRUNCATE`)? | 1.0 if safe, 0.0 if dangerous keyword found |
| `eval/answer_quality` | Is the answer substantive? Checks length, checks for error/refusal prefixes | 1.0 if ≥30 chars and not an error, 0.2 if refusal, 0.0 if empty |

Scores are logged to:
- The MLflow trace (visible in the Traces flamegraph as span attributes)
- The MLflow run (visible in the Experiments tab as metrics)
- The frontend (visible to the user as coloured dots)

#### Tier 2 — Batch Evals (`make eval`)
**Cost:** OpenAI tokens for each test query (14 queries total ≈ small cost).
**When:** On demand — run before demos, after model changes, before deployments.

**How it works:**
1. `harness.py` reads the golden dataset from `dataset.py`
2. Sends each question to the live backend via HTTP
3. Scores each response with deterministic metrics
4. Logs an eval run to MLflow with:
   - Per-case breakdown (question, answer, SQL, all scores)
   - Aggregate `pass_rate` metric
   - Mean latency across all cases
   - Downloadable CSV artifact
   - JSON table viewable in MLflow UI

**What "pass" means:** A case passes if `sql_valid=1.0`, `sql_safe=1.0`, `answer_quality≥0.8`, and `latency<15,000ms`.

#### Tier 3 — LLM Judge (`make eval-judge`)
**Cost:** More OpenAI tokens — each test case is judged by GPT-4o.
**When:** Occasionally — for deeper quality audits.

Uses MLflow's built-in `answer_relevance()` and `answer_similarity()` metrics:
- **`answer_relevance`**: Does the answer actually address the question asked?
- **`answer_similarity`**: How semantically close is the answer to the ground truth we wrote?

These two metrics catch cases that pass deterministic checks (valid SQL, non-empty answer) but still give the wrong information.

---

### `backend/app/evals/dataset.py` — The Golden Dataset

Contains 14 carefully written test cases:
- **6 credit cases** — approval/rejection counts, top decline reasons, average credit scores, provincial rejection rates, loan amounts by employment status, recent applications
- **5 fraud cases** — fraud volumes, average transaction amounts, merchant categories, model precision, highest-value cases
- **3 sentiment cases** — overall sentiment, negative themes, positive feedback

Each case has:
- `query` — the exact question to send
- `ground_truth` — what a correct answer should cover (used by LLM judge)
- `expected_sql_contains` — keywords the SQL should mention (e.g. `["credit_applications", "status"]`)
- `endpoint` — which FastAPI route to call

---

### `backend/app/evals/metrics.py` — The Scorers

Contains all scoring functions in one place:
- Deterministic scorers (`score_sql_valid`, `score_sql_safe`, `score_answer_quality`) used inline on every query
- `compute_inline_scores()` — the function called from `_agent_utils.py` after every agent run
- MLflow `make_metric` wrappers — the same logic packaged in the format `mlflow.evaluate()` expects for batch runs

---

### `backend/app/evals/harness.py` — The Test Runner

The script that runs when you type `make eval`. It:
1. Parses command-line args (`--backend`, `--use-case`, `--judge`)
2. Opens an MLflow run named `eval-all-YYYYMMDD-HHMM`
3. Loops through all test cases, calling the backend for each
4. Scores each response
5. Logs everything to MLflow
6. Prints a summary to the terminal
7. (Optionally) runs LLM judge as a nested run

---

## 13. MLflow — Observability

MLflow is the system's **data recorder and dashboard**. It runs as a separate server on port 5000.

### What MLflow records

**Experiments** (the `text-to-sql-demo` experiment):
- Every agent invocation creates a **run** with: use case, model, query preview, latency, eval scores
- Every batch eval creates a **run** with: pass rate, mean latency, per-case results table

**Traces** (the Traces tab):
- Every agent invocation creates a **trace** — a flamegraph showing:
  ```
  agent:credit-sql           (AGENT span — the full invocation)
    ├─ llm:agent_step        (CHAIN span — LLM reasoning step)
    │   └─ openai/chat       (auto-captured by mlflow.openai.autolog())
    ├─ get_credit_schema     (TOOL span — schema lookup)
    ├─ llm:agent_step        (CHAIN span — second reasoning step)
    │   └─ openai/chat
    └─ execute_credit_sql    (TOOL span — SQL execution)
  ```
- Each span shows: inputs, outputs, duration, status, any eval scores as attributes

### Starting MLflow

```bash
# Always use this command (SQLite backend = full Overview tab)
make dev-mlflow
```

Or manually:
```bash
.venv/bin/mlflow server \
  --backend-store-uri "sqlite:///$(PWD)/mlflow.db" \
  --default-artifact-root "$(PWD)/mlartifacts" \
  --port 5000 \
  --host 127.0.0.1
```

**Important — why `mlflow server` not `mlflow ui`:**
- `mlflow ui` uses a file-based store (`./mlruns/`) — the Overview tab shows a warning and is partially broken
- `mlflow server` with `--backend-store-uri sqlite:///...` uses a SQL database — the full UI works, including aggregate charts
- `mlflow.db` at the project root is this SQLite database

### Where to find things in the MLflow UI

| UI Location | What you see |
|---|---|
| `Experiments → text-to-sql-demo → Runs` | Every query ever made, with metrics |
| `Experiments → text-to-sql-demo → Traces` | Flamegraphs of every agent run |
| A trace → click on a span | Inputs, outputs, duration, eval scores |
| A run → Metrics tab | Latency, eval scores as time-series |
| A run → Artifacts tab | Eval result CSV files |

---

## 14. Architecture Documents

The `docs/` folder contains five standalone HTML documents supporting stakeholder discussions around architecture, capabilities, and builder onboarding.

| Document | Purpose | Open with |
|---|---|---|
| `docs/routing-vs-isolated.html` | 9-section printable document: isolated-module vs production routing-agent architecture. Covers memory, load balancing, auth/multi-tenancy, context window management, migration roadmap. | Open in browser; Print → PDF |
| `docs/architecture-visual.html` | Interactive animated SVG. Toggle between architectures; step-by-step query trace replay. | Open in browser |
| `docs/production-vision.html` | High-fidelity HTML prototype of the unified production UI. | Open in browser |
| `docs/power-prompts.html` | 5 business showcase prompts (cross-domain correlation, branch heatmap, fraud brief, CX coaching, revenue narrative) + 5 engineering diagnostic prompts (SQL injection, router boundary, hallucination probe, latency stress, context poisoning). | Open in browser |
| `docs/system-blueprint.html` | Component-level reference guide for builders — what each file does, whether the system breaks without it, dependencies. | Open in browser |

**Key architectural distinction:**

| Dimension | Current Demo (Isolated) | Production Target (Routing) |
|---|---|---|
| Entry point | 4 separate tabs/pages | 1 unified chat interface (ChatPage) |
| Agent selection | User manually navigates | Unified router classifies intent |
| Memory | Per-session, in-memory | Shared PostgreSQL checkpointer |
| Horizontal scale | Sticky sessions required | Redis-backed session store |
| Cross-domain queries | Not possible | Supported — fan-out + synthesise |
| Auth / multi-tenancy | Mock auth in frontend | JWT + Row-Level Security in DB |

---

## 15. Infrastructure — Running in the Cloud

### `infra/docker/docker-compose.yml` — Local Docker Mode

Starts all three services together with `make dev`:
- **backend** — FastAPI on port 8000
- **frontend** — Streamlit on port 8501
- **mlflow** — MLflow server on port 5000

Each service gets environment variables injected from `.env`.

### `infra/k8s/` — Azure Kubernetes Service (AKS) Deployment

Three Kubernetes YAML manifests for deploying to Azure:
- `deployments.yaml` — defines how many replicas of each service to run
- `backend-deployment.yaml` — specific backend configuration (resource limits, health checks)
- `secrets.yaml` — how to inject API keys as Kubernetes secrets (not hardcoded)

Deployed with `make k8s-deploy`.

### `backend/Dockerfile` and `frontend/Dockerfile`

Instructions for packaging each service into a Docker container:
- Install Python dependencies
- Copy source code
- Set the startup command
- Expose the correct port

---

## 16. How to Start Everything Locally

**Prerequisites:** `.env` file configured with your OpenAI API key.

> ⚠️ **Start order is critical — MLflow MUST start before the backend.**
> `base_graph.py` calls `mlflow.set_experiment()` at module import time. If MLflow is not running when uvicorn imports the agents, the backend crashes immediately.

**Step 1 — MLflow (must be first):**
```bash
cd text_to_sql_demo
source .venv/bin/activate
.venv/bin/mlflow server --host 127.0.0.1 --port 5000 \
  --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns &
# → http://localhost:5000
```

**Step 2 — Backend:**
```bash
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --reload --port 8000 --app-dir backend
```

**Step 3 — React Frontend / NedCard UI (production-grade interface):**
```bash
cd nedcard-ui
export PATH="/opt/homebrew/bin:$PATH"   # macOS: ensures Homebrew Node is used
npm run dev
# → http://localhost:3002
```

**Step 4 — Streamlit Frontend (demo interface):**
```bash
make dev-frontend
# → http://localhost:8501
```

**Open in browser:**
- React app (NedCard UI) → http://localhost:3002
- Streamlit demo app → http://localhost:8501
- MLflow → http://localhost:5000
- API docs (auto-generated) → http://localhost:8000/docs

**Run evals (while backend is running):**
```bash
make eval
```

**Important — always use the venv:**
The project venv (`.venv/`) has all required libraries installed. Always use `.venv/bin/python`, `.venv/bin/streamlit`, `.venv/bin/mlflow`, etc.

---

## 17. Key Design Decisions Explained

### Why LangGraph instead of a simple prompt?
A simple prompt would just ask GPT-4o to answer directly from its training data. LangGraph lets the AI **call tools** — actually query the database — which means answers are based on real data, not hallucinated patterns. The ReAct loop also lets the agent ask follow-up questions to itself: "The schema says there's a `province` column — let me use that in my WHERE clause."

### Why a string marker for chart data instead of a ContextVar?
`asyncio.gather()` in LangGraph's `ToolNode` creates new async Tasks. Each Task gets a **copy** of the ContextVar context at creation time — mutations inside those Tasks vanish when they finish. The string marker (`__CHART__:{json}:__ENDCHART__`) lives inside LangGraph's message list, which is always available after `ainvoke()` returns. Robust to async Task boundaries.

### Why a conversational bypass in the unified router?
Without it, "Hi" was routed to the Credit Intelligence agent (the `.*` wildcard fallback), which responded as a banking data analyst. The `_CONVERSATIONAL` regex intercepts greetings, thanks, and meta questions before they reach LangGraph. Direct OpenAI call takes ~50–200ms vs ~2–10s for a full agent. `agent_label: null` in the response tells the frontend not to show a domain badge.

### Why is `agent_label` null for conversational replies?
The domain badge ("Credit Intelligence") carries meaning — it tells the user which specialist looked at their question. Showing it for "Hello!" is misleading. Gating on `agent_label` keeps the badge truthful.

### Why does the chart render above the text bubble?
The AI often says "as shown in the chart above" in its response text. If the chart rendered below, that reference would be backwards. The order in JSX (`<DynamicChart>` first, then `<MessageBubble>`) is a deliberate spatial truth.

### Why `createPortal` for the fullscreen chart modal?
Without `createPortal`, the modal is mounted inside the chat message DOM tree, which has `overflow: hidden` and potentially low `z-index` ancestors. The modal would be clipped or appear behind other elements. `createPortal(element, document.body)` mounts the modal at the DOM root, bypassing all parent constraints.

### Why the MediaRecorder API for voice recording (not a library)?
The MediaRecorder API is browser-native — no dependencies, no bundle size cost. It produces `audio/webm` blobs that can be sent directly to Whisper. Every major modern browser supports it.

### Why does the mic now create a file attachment instead of transcribing to text?
The original flow sent audio to Whisper client-side → pasted text into the textarea — good for typed queries, but wasted the audio's richness. The new flow wraps the WebM blob as a `File` and routes it through PATH A (server-side Whisper + call analysis). This makes recordings first-class call intelligence inputs rather than lossy text summaries.

### Why upload + question → skip auto-summary?
When a user uploads a file and simultaneously types a question, showing the full auto-summary first and then the RAG answer produces two responses — visually confusing and slow. The PATH A fix: if `query.trim()` is non-empty, skip the summary entirely and call `submitDocQuery()` with the question directly. Auto-summary still shows when no question is typed.

### Why cosine similarity in SQLite instead of a dedicated vector database?
For the current scale (uploaded docs per session, not millions of vectors), SQLite is sufficient and zero-dependency. Cosine similarity over a few hundred chunks takes milliseconds in Python. When the system scales to a persistent multi-tenant document library, migrating to pgvector (PostgreSQL extension) changes only `store.py` — all upstream code is unchanged.

### Why two separate RAG system prompts (`_RAG_SYSTEM` vs `_CALL_RAG_SYSTEM`)?
Documents and call recordings have fundamentally different Q&A expectations. For documents, users want information retrieval ("what does the contract say about…"). For calls, users want sentiment, agent quality, and compliance assessment ("how satisfied was the client?", "did the agent follow the script?"). Separate prompts let each persona use appropriate language and reasoning patterns without compromising the other.

### Why TTS with Nova voice specifically?
Nova is OpenAI's most natural-sounding English voice for conversational content — clear cadence, appropriate for financial intelligence readbacks. The voice is a constant in `handleSpeak()`, but the `textToSpeech(text, voice)` function signature accepts any voice, making it a one-line change to switch to Alloy, Echo, Fable, Onyx, or Shimmer.

### Why streaming TTS instead of a full Blob download?
The previous implementation called `openai.audio.speech.create()` (blocking) → `response.content` (full buffer in RAM) → `StreamingResponse(iter([audio_bytes]))` — functionally a complete round-trip before any audio was sent. For a typical LLM response (~300 words), OpenAI takes 5–10 seconds to synthesise the full MP3. The user heard nothing until synthesis was complete.

The streaming fix uses `openai.audio.speech.with_streaming_response.create()` on the backend, piping 4 KB chunks via `StreamingResponse` to the browser as they arrive. The frontend uses the `MediaSource` API to begin playback immediately from the first chunk — reducing time-to-first-audio from ~8–10 s to ~0.5–1 s.

### Why a live `m:ss` timer during recording?
When you can't see or hear yourself recording, time perception breaks down. Without a timer, users can't judge whether they recorded 3 seconds or 30. The timer (incrementing every 1 second via `setInterval`) solves this without any UI complexity.

### Why FastAPI as the backend?
FastAPI is **async** — it can handle many requests at the same time without one blocking another. This matters because LLM calls take 2–10 seconds. With a synchronous server, request #2 would wait for request #1 to finish. With FastAPI, both run in parallel.

### Why Streamlit for the rapid-prototype frontend?
Streamlit lets you build an interactive data app in pure Python, without HTML, CSS, or JavaScript. For a demo or internal tool, this is a significant speed advantage. The tradeoff is less customisation than a full React app — which the NedCard UI delivers.

### Why SQLite for development, not PostgreSQL?
SQLite is a single file — no server to install, no network to configure. For development and demos, it's the fastest path to a working system. The database connection string is the only thing that changes when moving to PostgreSQL in production (the rest of the code is identical thanks to SQLAlchemy's abstraction layer).

### Why MLflow instead of LangSmith?
LangSmith requires account email verification and is a paid external service. MLflow is fully self-hosted — no external dependencies, no data leaving the network, no monthly subscription. MLflow 3 added first-class LLM tracing that is feature-equivalent for this use case.

### Why synthetic data instead of real data?
Three reasons: **Privacy** — no real customer data in development. **Control** — exact shape, volume, and edge cases we need. **Reproducibility** — anyone can regenerate the same dataset with `make seed`.

### Why a dual frontend (Streamlit + React)?
Streamlit enables a fully functional data app in pure Python in hours — ideal for prototyping. The React frontend (NedCard UI) removes Streamlit's hard limits on interactivity, streaming, and animations while consuming the same backend API unchanged. Prove the concept → harden the UX → migrate in phases.

### Why conversational system prompts instead of report-style?
Early agents defaulted to structured, report-style responses regardless of the question asked. All four agents were rewritten with an explicit rule: *"Answer exactly what was asked. A simple question gets a 1–2 sentence direct answer. Only add structure when the complexity warrants it."* This better matches chat UX and serves executives asking quick follow-up questions.

### Why ChatHistoryContext instead of URL state?
`ChatHistoryContext` (React Context + `useRef`) is in-memory, scoped to the browser session, requires no serialisation, and — crucially — does not trigger re-renders when history is written (uses `useRef`, not `useState`). URL params are ugly and size-limited; `localStorage` is synchronous and can conflict across tabs.

### Why typewriter streaming on the client side, and how is pacing controlled?
The FastAPI backend returns a complete response in one HTTP payload. Client-side typewriter streaming makes responses feel alive without requiring a streaming API. For production, server-sent events would stream tokens directly from the LLM, reducing time-to-first-token significantly.

**Pacing algorithm (punctuation-aware, recursive `setTimeout`):**

| Condition | Delay | Effect |
|---|---|---|
| Normal character | 18 ms | ~55 chars/sec — smooth reading pace |
| After `.` `!` `?` | 210 ms | Sentence breath — feels like a thought completing |
| After `,` `;` `:` | 90 ms | Clause beat — natural spoken rhythm |
| After `\n` | 130 ms | Line-break pause — lets the reader follow paragraph breaks |

The previous implementation used `setInterval(+6 chars, 16ms)` = 375 chars/sec, which appeared mechanical. Fixed-interval `setInterval` is replaced with recursive `setTimeout` so each character independently schedules its successor's delay based on what it is.

### Why separate `readonly_engine` for agent tools?
Defence in depth. Even if the AI generated a `DROP TABLE` statement (which `_validate_sql()` would catch), the database connection itself has no write permission. Two independent safety layers are better than one.

---

## 18. Glossary — Plain English Definitions

| Term | What it means |
|---|---|
| **Agent** | An AI that can take actions (call tools, query databases) on its own, not just generate text |
| **ReAct loop** | The agent's thinking pattern: Reason about what you need → Act (call a tool) → Observe the result → Repeat if needed |
| **LangGraph** | The library that defines and manages the agent's decision flow |
| **Tool** | A Python function the agent can call — like a database query or an API call |
| **ContextVar** | A Python mechanism for storing context per async Task. Breaks when LangGraph uses `asyncio.gather()` — each new Task gets a copy, not a reference |
| **String marker** | The chart data transport pattern: `__CHART__:{json}:__ENDCHART__` embedded in the tool's return string, extracted after `ainvoke()` completes. Bypasses the ContextVar copy problem |
| **unified router** | The `/api/unified/query` endpoint — classifies intent and fans out to the right specialist agent(s) |
| **Conversational bypass** | When `_CONVERSATIONAL` matches the query, skips LangGraph entirely and calls GPT-4o directly (~50ms response). `agent_label` returns as `null` |
| **agent_label** | Field in `AgentResponse` — names the domain specialist(s) that responded, or `null` for conversational replies. Controls whether the frontend badge is shown |
| **Domain badge** | The coloured pill shown above AI responses ("Credit Intelligence", "Fraud Intelligence", etc.). Only shown when a specialist agent was actually invoked (`agent_label` is non-null) |
| **FastAPI** | The Python web framework powering the backend API |
| **Streamlit** | The Python library powering the rapid-prototype frontend |
| **MLflow** | The observability platform — records every query, trace, and metric |
| **Trace** | A complete record of one agent run — like a detailed receipt showing every step and how long it took |
| **Span** | One step within a trace — e.g. "this tool call" or "this LLM call" |
| **Experiment** | A named bucket in MLflow that groups all runs for this project (`text-to-sql-demo`) |
| **Run** | One entry in an MLflow experiment — represents one query or one eval batch |
| **Eval** | Short for evaluation — the process of measuring whether the AI's answers are good |
| **Golden dataset** | A curated set of questions with known correct answers, used to test the system |
| **LLM judge** | Using GPT-4o to evaluate GPT-4o's answers — surprisingly effective |
| **Inline eval** | Scoring that runs on every query automatically, with no extra API cost |
| **SQLite** | A zero-configuration database stored as a single file — used in development |
| **PostgreSQL** | A full-featured database server — used in production |
| **SQLAlchemy** | A Python library that lets you talk to both SQLite and PostgreSQL with the same code |
| **readonly_engine** | A database connection with no write permission — every agent tool uses this, not the read-write engine |
| **Docker** | A tool that packages the app into a self-contained container that runs identically everywhere |
| **Kubernetes** | A system for running many Docker containers at scale in the cloud (Azure AKS) |
| **venv** | A self-contained Python environment with all required libraries — lives in `.venv/` |
| **pydantic** | A Python library that enforces data shapes — if a field is missing or the wrong type, it raises an error |
| **CORS** | Browser security rule that prevents a web page from calling APIs on a different domain — FastAPI is configured to allow calls from both frontends |
| **async** | Non-blocking code — while waiting for one database call, the server can handle other requests |
| **Vite** | A fast JavaScript build tool and dev server used by the React frontend — handles HMR and proxies `/api/*` requests to FastAPI |
| **Tailwind CSS** | A utility-first CSS framework — instead of writing `.card { padding: 16px; }` you write `className="p-4"` directly in the component |
| **Framer Motion** | A React animation library — handles smooth entry/exit animations, thinking step transitions, and chat message fades |
| **Typewriter streaming** | A client-side UX pattern where the AI's complete response is revealed character-by-character with punctuation-aware pacing: 18 ms/char normally; 210 ms after `.!?`; 90 ms after `,;:`; 130 ms after newlines. Implemented via recursive `setTimeout` so each character independently controls the next character's delay |
| **MediaRecorder** | Browser-native API for recording audio — produces `audio/webm` blobs sent to Whisper |
| **Whisper** | OpenAI's speech-to-text model — accepts audio blobs and returns transcript text |
| **DynamicChart** | The React component that renders any chart (bar/line/pie) from the backend's `chart_data` payload. Supports compact inline mode and fullscreen modal |
| **GenericChartCard** | The compact chart container with a "Full view" expand button |
| **FullscreenModal** | The expanded chart view, mounted via `createPortal` at `document.body`, closeable via ESC or backdrop click |
| **fmtTick** | Helper function abbreviating large numbers for Y-axis ticks (1.5M, 75K) |
| **prettyKey** | Helper converting snake_case/camelCase to Title Case for chart labels and tooltips |
| **Autocomplete** | As the user types, a dropdown appears showing relevant example queries filtered by `useMemo` — keyboard-navigable (Arrow keys, Tab, Enter) |
| **ChatHistoryContext** | A React Context that stores conversation history across page navigation, keyed by API endpoint — uses `useRef` to avoid unnecessary re-renders |
| **Thinking steps** | The staged chain-of-thought loading indicator. Four sequential labels (Routing → domain-specific query → Interpreting → Composing) cycle every 1.4 s via `setInterval`. Each step slides in/out via `AnimatePresence`. Driven by `thinkingStep` counter + `thinkingMeta` for domain accent colour |
| **Progressive disclosure of agent reasoning** | UX pattern where the loading state narrates each internal phase of agent execution rather than showing a single generic spinner. Reduces perceived wait time and builds user trust by revealing *what the system is actually doing* at each step — coined in agentic AI UX literature |
| **Chain-of-thought streaming UI** | The technical name for the staged thinking indicator pattern — mapping internal agent reasoning steps (route → query → interpret → compose) to sequential, animated UI states visible to the user in real time |
| **Staged loading indicator** | A loading UX where multiple named phases replace a single spinner. Each stage has a label, a slide transition, and a progress bar that fills as steps advance. Domain accent colour (green/red/blue/purple) threads through all elements |
| **Punctuation-aware typewriter** | The typewriter algorithm that varies character delay based on punctuation type: longer pauses after sentence-ending characters create natural reading rhythm that mimics how a person speaks or writes |
| **userInitials prop** | The `MessageBubble` prop carrying the user's 1–2 letter initials (derived from `user?.name`). Renders the blue-to-purple gradient avatar on the right side of every user message, mirroring the top-bar header avatar |
| **Hero icon glow** | The pulsing green ring and `boxShadow` on the empty-state logo above "What do you need to know?". A `motion.span` behind the circle breathes (opacity 0.15→0.45→0.15, scale 1→1.18→1) on a 3 s infinite `easeInOut` loop |
| **RAG** | Retrieval-Augmented Generation — questions are answered using retrieved chunks of an uploaded document, not model memory |
| **Chunk** | A fixed-size text window (800 chars, 80 overlap) from a document, stored as an embedding row in `document_chunks` |
| **Embedding** | A 1536-dim float vector (OpenAI `text-embedding-ada-002`) representing a chunk's semantic meaning. Used for cosine similarity search |
| **Cosine similarity** | Mathematical measure of angle between two vectors. 1.0 = identical meaning, 0 = unrelated. Used in `store.py` to rank chunks |
| **Call intelligence** | The `_CALL_ANALYSIS_SYSTEM` prompt persona — a call-centre assessor that generates a structured 5-section report from a Whisper transcript |
| **Active document** | The amber banner in ChatPage after a file upload. Follow-up questions route to RAG against that document until the user clicks × |
| **PATH A / B / C** | The three branches in `submit()`. A = file attached; B = active doc, no new file; C = no document context (normal agent query) |
| **TTS** | Text-to-Speech. `POST /api/speech/tts` streams MP3 chunks via OpenAI `with_streaming_response`. The browser uses `MediaSource` to begin playback as the first chunks arrive (~0.5–1 s latency). Voice: Nova (OpenAI). Falls back to full-Blob on Safari. |
| **speakingId** | React state tracking which message is currently being read aloud — drives Listen/Stop button label and disabled state for other buttons |
| **activeSpeaker ref** | `useRef<HTMLAudioElement>` holding the playing TTS element. Used to stop playback before starting a new one |
| **MediaSource streaming TTS** | Browser API (`MediaSource` + `SourceBuffer`) used in `handleSpeak` to append incoming audio chunks and begin playback before synthesis completes — eliminates the 8–10 s full-synthesis wait |
| **_stream_tts** | Private async generator in `speech.py` that wraps OpenAI's streaming TTS response and yields 4 KB chunks to FastAPI's `StreamingResponse` |
| **MLflow startup order** | `base_graph.py` calls `mlflow.set_experiment()` at import time. MLflow server must be running **before** the backend starts, or the backend crashes at launch |
| **Routing agent** | A proposed production pattern where a single AI classifier reads the user's query and decides which specialist agent to invoke |
| **Isolated modules** | The legacy demo architecture — each use case is a separate page/agent with no shared context between them |
| **PostgreSQL checkpointer** | A LangGraph feature that stores agent conversation state in PostgreSQL rather than RAM, enabling history to survive pod restarts and scale across instances |
