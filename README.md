# Agentic RAG Assistant — Medical Education & Clinical Reference

A production-grade **agentic Retrieval-Augmented Generation (RAG)** system I built for the
medical-education domain. It combines a multimodal ingestion pipeline (text, tables,
diagrams/images), hybrid retrieval (BM25 + vector fusion with neural re-ranking), an
agent that routes across a vector store, a structured clinical SQL database and live
PubMed literature, and a fully observable, guard-railed, streaming query pipeline.

I designed and implemented the entire stack myself — the FastAPI backend, the
ingestion and retrieval pipelines, the React/TypeScript frontend, and the evaluation,
observability and human-handoff layers.

---

## Table of Contents

1. [What I built](#what-i-built)
2. [Architecture at a glance](#architecture-at-a-glance)
3. [Project structure](#project-structure)
4. [Ingestion pipeline](#ingestion-pipeline)
5. [Retrieval & query pipeline](#retrieval--query-pipeline)
6. [Production ingestion principles I implemented](#production-ingestion-principles-i-implemented)
7. [Frontend](#frontend)
8. [Tech stack](#tech-stack)
9. [Running the project](#running-the-project)
10. [Configuration](#configuration)

---

## What I built

I wanted an assistant that never hallucinates on medical content: every sentence it
returns is traceable to something it retrieved. To get there I implemented:

- **Multimodal ingestion** — I route documents through LlamaParse when they contain
  tables or diagrams, extract each modality separately (semantic text chunks, LLM table
  summaries, vision-model image captions), and inject rich structural + medical metadata
  onto every node.
- **Hybrid retrieval** — I fuse a dense vector retriever with a BM25 sparse retriever via
  Reciprocal Rank Fusion (`QueryFusionRetriever`), pull the top 15 candidates, then narrow
  to the best results with a local FlashRank cross-encoder re-ranker (no extra LLM call).
- **An agent with three tool families** — a vector `policy_documents` tool, a read-only
  clinical SQL tool over six fixed tables, and PubMed/NCBI MCP literature tools. The agent
  decides which to call, and I force a "retrieve-before-answer" grounding rule.
- **Safety & evaluation** — Guardrails PII redaction, SQL write-intent blocking, RAGAS
  faithfulness + answer-relevance scoring on every answer, Langfuse tracing, and an
  automatic human-handoff path (email escalation) when quality drops.
- **A streaming UI** — a React frontend that consumes Server-Sent Events (SSE) to render
  the pipeline live, stream tokens, and display retrieved tables and images inline.

---

## Architecture at a glance

```
                          ┌─────────────────────────────────────────────┐
   React + TS + Vite      │                 FastAPI backend               │
   (SSE client)  ────────▶│  /api/upload   ───▶  Ingestion pipeline       │
        ▲                 │  /api/query    ───▶  Agentic query pipeline    │
        │  SSE events     │  /api/login    ───▶  JWT auth                  │
        └─────────────────│                                               │
                          └───────┬───────────────┬───────────────┬───────┘
                                  │               │               │
                          ┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼───────┐
                          │  PGVector    │ │ Clinical    │ │  PubMed MCP  │
                          │ (documents)  │ │ SQL (6 tbls)│ │ (literature) │
                          └──────────────┘ └─────────────┘ └──────────────┘

     Cross-cutting: Guardrails (PII / SQL-intent) · RAGAS eval · Langfuse tracing · Handoff
```

---

## Project structure

```
agentic_rag_assistant/
├── backend/
│   ├── main.py                         # Uvicorn entrypoint → app.app:app
│   ├── medical_database_schema.sql     # Clinical reference schema (6 tables)
│   ├── models/flashrank/…              # Bundled ms-marco-MiniLM-L-12-v2 ONNX re-ranker
│   ├── stored_images/                  # Persisted extracted figures (served via /api/images)
│   └── app/
│       ├── app.py                      # FastAPI app, lifespan, CORS, health, startup init
│       ├── core/limiter.py             # SlowAPI rate limiting
│       ├── config/config.py            # Central env-driven configuration
│       ├── auth/security.py            # JWT verification (claims carry per-request keys)
│       ├── langfuse/langfuse_client.py # Langfuse + OpenInference instrumentation
│       ├── routes/
│       │   ├── auth_routes.py          # /login, /me
│       │   ├── ingestion_routes.py     # /upload  (ingestion pipeline entry)
│       │   └── query_routes.py         # /query   (SSE agentic pipeline)
│       └── service/
│           ├── documents.py            # Load + clean raw text, binary guard
│           ├── multimodal.py           # Orchestrates LlamaParse multimodal parsing
│           ├── metadata.py             # Structural + content + medical metadata extractor
│           ├── chunking.py             # SemanticSplitter (+ sentence fallback)
│           ├── indexing.py             # PGVectorStore load/create, dedup, embed-model guard
│           ├── vectordb.py             # Node insertion into the index
│           ├── tools.py                # Retrievers, BM25 fusion, re-rankers, agent tools
│           ├── agent.py                # FunctionAgent / ReActAgent + lenient parser
│           ├── llms.py                 # Azure OpenAI / Gemini LLM + embeddings + evaluators
│           ├── structured_data_db.py   # SQLDatabase over the six clinical tables
│           ├── sql_bootstrap.py        # One-time schema bootstrap
│           ├── rate_limit.py           # Gemini RPM-aware HTTP clients
│           ├── llamparse/
│           │   ├── textprocessing.py       # Semantic text nodes
│           │   ├── table_extraction.py     # Markdown table detection/normalisation
│           │   ├── tableprocessing.py      # LLM table summaries (keeps original markdown)
│           │   ├── image_extraction.py     # PyMuPDF image extraction
│           │   ├── imageprocessing.py      # Persist image + build caption node
│           │   └── image_captioning.py     # Vision-model caption generation
│           ├── mcp/mcp_tools.py            # PubMed MCP client
│           ├── guard/validatior_guard.py   # Guardrails PII + SQL-intent validation
│           └── handoff/handoff_service.py  # Human-handoff trigger + email escalation
└── frontend/
    └── src/
        ├── config/urls.ts              # API base + endpoints
        ├── utils/network.ts            # streamSSE() + uploadFile() + ApiError
        ├── hooks/useChat.ts            # SSE consumer → message state machine
        ├── hooks/useUpload.ts          # Upload hook
        ├── components/                 # ChatArea, RightPanel, Markdown, EvalScorePanel, …
        ├── pages/                      # ChatPage, LoginPage, VectorToolPage, SQLToolPage
        ├── store/                      # Redux Toolkit + redux-persist (documents)
        └── auth/                       # AuthContext, ProtectedRoute, token, RateLimitContext
```

---

## Ingestion pipeline

When a user uploads a file to `POST /api/upload`, I run it through this sequence:

1. **Validate & deduplicate.** I sanitise the filename, enforce the allowed extensions
   (`.txt`, `.pdf`, `.md`, `.docx`) and a 10 MB cap, then compute a **SHA-256 hash** of the
   bytes. If that hash already exists in the vector table I reject with `409 Conflict` — this
   makes ingestion **idempotent** and **incremental** (identical re-uploads never create
   duplicate chunks).
2. **Load & clean text.** `Document_Process` writes the bytes to a temp file, loads them with
   LlamaIndex's `SimpleDirectoryReader`, and I normalise the text (Unicode NFC, strip control
   characters) and assert the loader did not return raw binary.
3. **Detect modality.** `MultiModal.requires_multimodal_parsing()` uses `pdfplumber`/`python-docx`
   to check for tables or images. If present, I route through **LlamaParse**; otherwise I take
   the lightweight text path.
4. **Extract per modality (LlamaParse path).** `process_docs_find` produces three kinds of nodes:
   - **Text** → `TextProcessor` semantic chunks (`modality=text`).
   - **Tables** → I detect markdown tables, drop header-only mis-parses, normalise them, then
     `TableProcessor` writes an LLM summary as the searchable text while preserving the original
     markdown in metadata (`content_type=table_summary`).
   - **Images/diagrams** → I extract them with PyMuPDF, generate an exhaustive caption with a
     vision model (chart type, axis labels, every data point, diagram connections), persist the
     image to `stored_images/`, and store the caption as the node text (`content_type=image_caption`,
     `image_path` in metadata).
5. **Inject metadata.** `DocumentMetadataExtractor` attaches structural metadata (file name, type,
   size, upload date, uploader, source-type inference) plus LLM-derived content metadata (category,
   topic, keywords, summary) and medical metadata (specialty, anatomical system, content domain,
   intended route). I stamp every node with `file_hash` and `embed_model`, and add those keys to
   the embed/LLM exclusion lists so they never pollute the embedding text.
6. **Chunk.** `Chunking_Strategy` uses a `SemanticSplitterNodeParser` (embedding-similarity
   breakpoints) with a `SentenceSplitter` fallback for oversized chunks (> 512×4 chars).
7. **Index.** `VectorDB.insert_nodes_index()` inserts the nodes into a **PGVector** table
   (`DOCS_MIND`, 3072-dim). I also guard against **embedding-model mismatch** — mixing vectors from
   different embedding models would silently break retrieval, so I refuse it explicitly.

---

## Retrieval & query pipeline

`POST /api/query` returns a **Server-Sent Events** stream so the UI can show each stage live.
The pipeline:

1. **Input guard.** I block write/mutation intent at the door (regex + patterns) so the SQL tool
   can only ever read.
2. **Embed-model check + index load.** I verify the active embedding model matches the stored
   vectors, then load the PGVector index.
3. **Agent instantiation.** I build a `FunctionAgent` (native tool-calling models) or a
   `ReActAgent` with a **lenient output parser** that forces a tool call before any answer and
   rewrites invented tool names back to `policy_documents`.
4. **Hybrid retrieval inside `policy_documents`:**
   - Dense **vector retriever** (`similarity_top_k = 15`).
   - Sparse **BM25 retriever** over the docstore nodes.
   - **`QueryFusionRetriever`** fuses both with **Reciprocal Rank Fusion** and returns 15 candidates.
   - A **FlashRank cross-encoder** (`ms-marco-MiniLM-L-12-v2`, bundled ONNX, no LLM call) re-ranks
     those 15 down to the top-N most relevant passages, which become the numbered `[n]` context blocks.
     (Re-rank width, cutoffs and auto-retriever are all env-configurable; deterministic `KeepTopN`
     is the safe default.)
5. **Tool routing.** The agent chooses among `policy_documents`, the read-only `clinical_reference_db`
   SQL tool (guarded by a regex **and** an LLM SQL-intent classifier), and the PubMed MCP tools.
6. **Grounding gate.** If no tool ran or nothing was retrieved, I refuse to answer rather than
   hallucinate.
7. **PII redaction.** Guardrails' local Presidio-backed `DetectPII` sanitises the answer (and live
   stream segments), failing closed if the check errors.
8. **Evaluation.** I score every answer with **RAGAS Faithfulness** (grounding) and
   **AnswerRelevancy**, and surface both to the UI.
9. **Observability.** Langfuse (via OpenInference LlamaIndex instrumentation) traces the whole run
   and returns a trace ID.
10. **Human handoff.** If the user explicitly asks for a human, nothing was retrieved, or
    faithfulness/relevance fall below thresholds, I generate a reference ID and email the full
    context (query, tools, scores, chunks, trace) to a support inbox.
11. **Attachments & citations.** I extract the tables and images that back the answer from the
    source nodes, dedupe them, and stream them plus the `[n]` citation map to the client.

---

## Production ingestion principles I implemented

I designed the ingestion layer against a checklist of production RAG principles:

| Principle          | How I implemented it |
|--------------------|----------------------|
| **Idempotency**    | SHA-256 content hashing; duplicate uploads return `409` instead of re-indexing. |
| **Incrementality** | Only new/changed files are processed; the hash makes re-ingestion a no-op. |
| **Determinism**    | Deterministic `KeepTopN` default, reproducible semantic chunking, embed-model stamping for reproducible retrieval. |
| **Structure-Aware**| LlamaParse markdown + separate table/image extraction; modality metadata preserves layout meaning. |
| **Noise Reduction**| Text cleaning, header-only-table dropping, similarity cutoff, oversized-chunk splitting, min-length checks. |
| **Metadata-First** | Structural + content + medical metadata on every node; `file_hash`/`embed_model` stamps excluded from embeddings. |
| **Access Control** | JWT auth, per-user document scope, read-only SQL guard, PII redaction, path-traversal-safe image serving. |
| **Observability**  | Langfuse tracing, structured logging, RAGAS scores, live SSE pipeline steps, handoff audit trail. |

---

## Frontend

I built the frontend in **React + TypeScript + Vite + Tailwind**, with **Redux Toolkit** (and
`redux-persist`) for the document store and a small set of custom hooks:

- **`useChat` (SSE state machine).** I consume the SSE stream through `streamSSE`, then reduce the
  events into message state: `step` events drive the live pipeline timeline, `token` events append
  to the streaming answer, `meta` carries the final answer plus sources, tools, tables, images and
  eval scores, `handoff` shows the escalation banner, and `error` surfaces failures.
- **`streamSSE` (network layer).** I read the `fetch` `ReadableStream` with a `TextDecoder`, split on
  `\n\n` frame boundaries, parse the `event:`/`data:` lines and dispatch typed events — with auth
  headers, 401/429 handling and abort support.
- **Text & image propagation.** The backend sends relative image URLs; `resolveImages` prefixes them
  with the API base so `ChatArea` can render retrieved **figures** (with captions) and **tables**
  (as rendered markdown) inline beneath the answer, alongside citation chips and source chips.
- **Rendering.** I render answers with `react-markdown` + `remark-gfm` through a themed component map,
  and keep presentational logic in functional components (`ChatArea`, `RightPanel`, `Markdown`,
  `EvalScorePanel`, `Sidebar`, `TopBar`, `Modal`), with auth handled by `AuthContext` +
  `ProtectedRoute`.

---

## Tech stack

**Backend:** Python, FastAPI, LlamaIndex, LlamaParse, PostgreSQL + pgvector, BM25, FlashRank
(ONNX), Guardrails (Presidio), RAGAS, Langfuse, Azure OpenAI / Google Gemini, SlowAPI, JWT.

**Frontend:** React, TypeScript, Vite, Tailwind CSS, Redux Toolkit, redux-persist, React Router,
react-markdown, lucide-react.

---

## Running the project

### Backend

```bash
cd backend
uv sync                       # or: pip install -r requirements.txt
cp .env.example .env          # then fill in your keys (see Configuration)
uv run uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                   # Vite dev server (defaults to the backend at :8000)
```

---

## Configuration

Key environment variables (backend `.env`):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` / `DB_*` | PostgreSQL + pgvector connection |
| `USE_GEMINI` | Switch between Azure OpenAI and Gemini providers |
| `AZURE_*` / `GEMINI_*` | Provider credentials & deployment names |
| `RETRIEVAL_TOP_K` | Candidate pool size before re-rank (default 15) |
| `RERANK_TOP_N` | Passages kept after re-rank |
| `ENABLE_FLASHRANK_RERANK` | Toggle the FlashRank cross-encoder re-ranker |
| `USE_AUTO_RETRIEVER` | Toggle metadata-inference auto-retriever |
| `HANDOFF_FAITHFULNESS_THRESHOLD` / `HANDOFF_RELEVANCE_THRESHOLD` | Handoff trigger thresholds |
| `SMTP_*` / `SUPPORT_EMAIL` | Human-handoff email escalation |
| `LANGFUSE_*` | Observability keys |
| `PUB_MED_MCP_URL` | PubMed MCP service endpoint the agent connects to |
