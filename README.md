# AI Data Analyst

Upload a CSV, ask questions in plain English, and get back generated SQL/Python,
the actual results, a chart when relevant, and a plain-language insight —
plus an auto-generated dashboard. Code generation and insights run on
**Groq** (Llama 3.3 70B) for fast, low-latency inference.

## Architecture

```
┌─────────────┐      CSV upload      ┌──────────────────────┐
│   React     │ ───────────────────► │   FastAPI backend     │
│  (frontend) │                      │                        │
│             │ ◄─────────────────── │  DuckDB (SQL engine)   │
│  Chat +     │   question / answer  │  pandas (Python engine)│
│  Dashboard  │                      │  Groq / Llama 3.3      │
└─────────────┘                      │    (code-gen + insights)│
                                      └──────────────────────┘
```

**Flow for a question:**
1. Frontend sends the question + session id to `/query`.
2. Backend picks SQL (DuckDB) or Python (pandas), based on the question — or
   whatever engine you request explicitly.
3. Groq (Llama 3.3 70B) receives the *data profile* (schema, dtypes, stats,
   sample rows — never the whole raw file) and returns generated code as JSON.
4. Code executes: SQL runs directly against DuckDB; Python runs in an isolated
   subprocess with a timeout, no network access, and a restricted set of
   allowed operations.
5. If it errors, the traceback is fed back to the model for up to 2 retries.
6. Results go back to the model one more time to produce a short,
   plain-English insight — kept separate from the code-generation step for
   reliability.

**Dashboard flow:** `/dashboard` asks the model to propose 4-6 chart specs
from the schema alone (no need for the user to ask), runs each as SQL, and
returns them for the frontend to render with Recharts.

## Why DuckDB + pandas together

- **DuckDB (SQL)** handles filtering, aggregation, grouping, joins, and
  ranking — the majority of "explore my data" questions. LLMs write correct
  SQL more reliably than pandas code for this class of task, and DuckDB
  queries a CSV-backed table with no separate database server.
- Using Groq means these round trips (code-gen → execute → insight, x2-3 per
  question) return much faster than with a typical hosted API, since Groq's
  inference is optimized for low latency — useful here since a single
  question can trigger 2-3 model calls.
- **pandas/matplotlib (Python)** is used when the question needs statistics,
  correlation, distributions, or a rendered chart image — things SQL can't
  express well.

The backend chooses automatically based on keywords in the question
(`correlate`, `predict`, `distribution`, etc. → Python; everything else →
SQL), or you can force it via the `engine` field in the `/query` request.

## Setup

### Backend
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api/*` to the
FastAPI backend on port 8000 (see `vite.config.js`).

## Security notes for production

This prototype is intentionally minimal. Before shipping it to real users:

- **Sandbox Python execution properly.** The current subprocess approach is a
  starting point, not a security boundary — move to a locked-down Docker
  container, gVisor, or a hosted sandbox (E2B, Modal) with no filesystem or
  network access beyond the working directory.
- **Persist sessions.** Sessions currently live in an in-memory dict and are
  lost on restart — move to Redis/Postgres + object storage (S3) for the
  uploaded files.
- **Add authentication and per-user rate limits** on `/query` and
  `/dashboard`, since each call makes at least one (and up to three) LLM
  requests.
- **Validate file size/type** on upload and cap DuckDB memory/row limits for
  very large CSVs.
- **Restrict CORS** (`allow_origins=["*"]` is fine for local dev only).

## Extending it

- **Follow-up questions with memory:** pass recent Q&A pairs into the system
  prompt so "now break that down by month" resolves against the prior query.
- **Multi-file / joins:** register multiple uploaded CSVs as separate DuckDB
  tables and let Claude join across them.
- **Export:** add a `/export` endpoint that reruns a saved query and returns
  a CSV or the dashboard as a PDF.
- **Clarifying questions:** for vague prompts ("analyze my data"), have
  Claude propose 2-3 specific angles instead of guessing.
