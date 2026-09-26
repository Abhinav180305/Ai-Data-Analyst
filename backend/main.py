"""
AI Data Analyst — Backend
--------------------------
FastAPI service with:
  0. Real accounts: signup/login with bcrypt-hashed passwords, JWT bearer
     tokens, and every session tied to the user who created it — no one can
     read or query another user's uploaded data.
  1. CSV upload, persisted to disk + SQLite (survives restarts), loaded into
     DuckDB per-session.
  2. Groq-powered SQL/Python code generation for natural-language questions,
     executed in a sandboxed subprocess, self-correcting on error.
  3. An auto-suggested dashboard (chart set) from the data profile.
  4. On-demand distribution charts (KDE/hist/box/violin) for numeric columns
     and count-based charts (bar/pie/pareto/donut) for categorical ones.
  5. Five baseline ML models against a chosen target column, with metrics
     and feature importance.
  6. Plain-English insights for query results.

Run:
    pip install -r requirements.txt
    Create backend/.env with:
        GROQ_API_KEY=gsk_...
        JWT_SECRET=<a long random string — see note below>
    uvicorn main:app --reload --port 8000

JWT_SECRET note: this signs every login token. Generate one with:
    python -c "import secrets; print(secrets.token_hex(32))"
Never commit .env or reuse a secret across environments.
"""

import os
import io
import sys
import json
import uuid
import sqlite3
import traceback
import threading
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi.responses import StreamingResponse, FileResponse

import duckdb
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, field_validator
from passlib.context import CryptContext
from jose import jwt, JWTError
from groq import Groq
from dotenv import load_dotenv

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingRegressor
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    r2_score, mean_squared_error, mean_absolute_error,
)

load_dotenv()

MODEL = "openai/gpt-oss-120b"
client = Groq()  # reads GROQ_API_KEY from env (loaded via .env above)

def to_native(obj):
    """Recursively convert numpy scalars/arrays to native Python types so
    FastAPI's jsonable_encoder never chokes on them."""
    if isinstance(obj, np.generic):       # covers np.bool_, np.int64, np.float64, etc.
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_native(v) for v in obj]
    return obj

# ---------------------------------------------------------------------------
# Auth config
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is not set. Add it to backend/.env — generate one with:\n"
        "  python -c \"import secrets; print(secrets.token_hex(32))\""
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

app = FastAPI(title="AI Data Analyst")

# Lock this down to your real frontend origin(s) before deploying anywhere
# public. "*" with credentialed requests is a security hole in production.
FRONTEND_ORIGINS = os.environ.get("FRONTEND_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Storage: in-memory session cache (fast path) backed by SQLite metadata +
# on-disk CSVs, so sessions survive an uvicorn --reload restart. Every
# session row and every cached session dict carries the owning user_id, and
# get_session() refuses to hand back a session to anyone else.
# For real production use: Postgres instead of SQLite, S3 instead of local
# disk, and a proper migrations tool instead of CREATE TABLE IF NOT EXISTS.
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "session_data")
DB_PATH = os.path.join(BASE_DIR, "sessions.db")
os.makedirs(SESSIONS_DIR, exist_ok=True)

SESSIONS: dict[str, dict] = {}


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            csv_path TEXT NOT NULL,
            table_name TEXT NOT NULL,
            profile_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        email = payload.get("email")
        if not user_id:
            raise JWTError("missing subject")
    except JWTError:
        raise HTTPException(401, "Invalid or expired token — please log in again")
    return {"id": user_id, "email": email}


# ---------------------------------------------------------------------------
# Session storage helpers (all ownership-checked)
# ---------------------------------------------------------------------------
def persist_session_metadata(session_id: str, user_id: str, csv_path: str, table_name: str, profile: dict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO sessions (session_id, user_id, csv_path, table_name, profile_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, user_id, csv_path, table_name, json.dumps(profile, default=str),
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def get_session(session_id: str, user_id: str) -> Optional[dict]:
    """Returns the session only if it exists AND belongs to user_id.
    Fast path checks the in-memory cache; otherwise rebuilds from SQLite
    metadata + the persisted CSV on disk (survives backend restarts)."""
    cached = SESSIONS.get(session_id)
    if cached:
        return cached if cached.get("user_id") == user_id else None

    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT user_id, csv_path, table_name, profile_json FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None

    owner_id, csv_path, table_name, profile_json = row
    if owner_id != user_id:
        return None
    if not os.path.exists(csv_path):
        return None

    try:
        df = pd.read_csv(csv_path)
        profile = json.loads(profile_json)
        workdir = os.path.join(SESSIONS_DIR, session_id)
        os.makedirs(workdir, exist_ok=True)

        con = duckdb.connect(database=":memory:")
        con.register("data", df)
        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM data")

        session = {
            "df": df, "con": con, "table_name": table_name,
            "profile": profile, "workdir": workdir, "user_id": owner_id,
        }
        SESSIONS[session_id] = session
        return session
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class SignupRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


class QueryRequest(BaseModel):
    session_id: str
    question: str
    engine: Optional[str] = "auto"  # "sql" | "python" | "auto"
    history: Optional[list[dict]] = None  # [{"question": "...", "code": "...", "explanation": "..."}]


class DashboardRequest(BaseModel):
    session_id: str


class MLRequest(BaseModel):
    session_id: str
    target: str


class PredictRequest(BaseModel):
    session_id: str
    inputs: dict

# ---------------------------------------------------------------------------
# Data / LLM helpers (unchanged from the non-auth version)
# ---------------------------------------------------------------------------

def select_important_columns(df: pd.DataFrame, top_n: int = 10) -> list[str]:
    """
    For wide datasets, rank columns by how much information they carry and
    return the top_n most important. Numeric columns are ranked by their
    contribution to the leading PCA components (weighted by explained
    variance) — a column that barely moves independently of the others
    contributes little to the components and ranks low. Categorical columns
    are ranked by the entropy of their value distribution (a column that's
    95% one value carries less information than one split evenly).
    This only controls what gets FULL detail in the LLM's schema profile —
    it never restricts the actual table, so a question that names an
    excluded column by name can still be answered.
    """
    if len(df.columns) <= top_n:
        return list(df.columns)

    scores: dict[str, float] = {}
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    if len(numeric_cols) >= 2:
        try:
            numeric_df = df[numeric_cols].dropna()
            if len(numeric_df) >= 5:
                scaled = StandardScaler().fit_transform(numeric_df)
                n_components = min(5, len(numeric_cols), scaled.shape[0])
                pca = PCA(n_components=n_components)
                pca.fit(scaled)
                loadings = np.abs(pca.components_) * pca.explained_variance_ratio_[:, None]
                importance = loadings.sum(axis=0)
                for col, score in zip(numeric_cols, importance):
                    scores[col] = float(score)
        except Exception:
            pass
    for col in numeric_cols:
        scores.setdefault(col, 0.0)

    cat_cols = [c for c in df.columns if c not in numeric_cols]
    for col in cat_cols:
        try:
            counts = df[col].dropna().value_counts(normalize=True)
            if len(counts) > 1:
                entropy = -(counts * np.log2(counts)).sum()
                max_entropy = np.log2(len(counts))
                scores[col] = float(entropy / max_entropy) if max_entropy > 0 else 0.0
            else:
                scores[col] = 0.0
        except Exception:
            scores[col] = 0.0

    # Normalize numeric-PCA and categorical-entropy scores separately to
    # [0,1] first, so neither group dominates purely due to differing scales.
    def normalize(cols):
        vals = [scores[c] for c in cols]
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-9:
            return {c: 0.5 for c in cols}
        return {c: (scores[c] - lo) / (hi - lo) for c in cols}

    normalized = {}
    if numeric_cols:
        normalized.update(normalize(numeric_cols))
    if cat_cols:
        normalized.update(normalize(cat_cols))

    ranked = sorted(df.columns, key=lambda c: normalized.get(c, 0.0), reverse=True)
    return ranked[:top_n]

def compute_data_health(df: pd.DataFrame) -> dict:
    """
    A quick, upfront read on data quality — shown the moment a CSV loads,
    before the user asks anything. Combines four signals into a single
    score: completeness (missing values), duplicate rows, outlier-heavy
    numeric columns (IQR method), and near-unique "ID-like" categorical
    columns that usually aren't useful for analysis.
    """
    total_cells = df.shape[0] * df.shape[1]
    total_nulls = int(df.isna().sum().sum())
    completeness_pct = round(100 * (1 - total_nulls / total_cells), 1) if total_cells else 100.0

    duplicate_rows = int(df.duplicated().sum())
    duplicate_pct = round(100 * duplicate_rows / len(df), 1) if len(df) else 0.0

    outlier_columns = []
    for col in df.select_dtypes(include="number").columns:
        series = df[col].dropna()
        if len(series) < 10:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outlier_pct = 100 * ((series < lower) | (series > upper)).mean()
        if outlier_pct > 5:
            outlier_columns.append({"column": col, "outlier_pct": round(float(outlier_pct), 1)})

    high_cardinality_columns = []
    for col in df.select_dtypes(exclude="number").columns:
        if len(df) == 0:
            continue
        uniqueness = df[col].nunique() / len(df)
        if uniqueness > 0.9:
            high_cardinality_columns.append(col)

    # Weighted score: completeness matters most, then duplicates, then the two warning types
    score = 100.0
    score -= (100 - completeness_pct) * 0.5
    score -= min(duplicate_pct, 20) * 1.0
    score -= min(len(outlier_columns) * 4, 20)
    score -= min(len(high_cardinality_columns) * 3, 15)
    score = max(0, min(100, round(score)))

    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B+"
    elif score >= 70:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 45:
        grade = "D"
    else:
        grade = "F"

    return {
        "score": score,
        "grade": grade,
        "completeness_pct": completeness_pct,
        "duplicate_rows": duplicate_rows,
        "duplicate_pct": duplicate_pct,
        "outlier_columns": outlier_columns[:5],
        "high_cardinality_columns": high_cardinality_columns[:5],
    }

def profile_dataframe(df: pd.DataFrame, table_name: str) -> dict:
    """
    Build a compact schema/profile description to feed the LLM. For wide
    tables (>10 columns), only the top 10 most informative columns (see
    select_important_columns) get full stats; the rest are listed by
    name + dtype only, so the model still knows they exist.
    """
    important_cols = set(select_important_columns(df, top_n=10))

    profile = {
        "table_name": table_name,
        "n_rows": len(df),
        "n_cols": len(df.columns),
        "columns": [],
    }
    if len(df.columns) > 10:
        profile["_note"] = (
            f"This table has {len(df.columns)} columns. Full stats are shown only for the "
            f"{len(important_cols)} most informative ones (ranked by PCA contribution for numeric "
            f"columns, distribution entropy for categorical ones). Other columns are listed by name "
            f"only but can still be used in SQL/Python if the question names them directly."
        )

    for col in df.columns:
        series = df[col]
        if col not in important_cols:
            profile["columns"].append({"name": col, "dtype": str(series.dtype)})
            continue

        col_info = {
            "name": col,
            "dtype": str(series.dtype),
            "n_nulls": int(series.isna().sum()),
            "n_unique": int(series.nunique()),
        }
        if pd.api.types.is_numeric_dtype(series):
            col_info["min"] = float(series.min()) if series.notna().any() else None
            col_info["max"] = float(series.max()) if series.notna().any() else None
            col_info["mean"] = float(series.mean()) if series.notna().any() else None
        else:
            top_vals = series.dropna().astype(str).value_counts().head(5)
            col_info["sample_values"] = top_vals.index.tolist()
        profile["columns"].append(col_info)

    profile["sample_rows"] = json.loads(df.head(5).to_json(orient="records"))
    return profile

def trim_profile_for_prompt(profile: dict, max_chars: int = 4000) -> dict:
    """
    Groq's free tier caps requests at 8000 tokens/minute. A wide CSV's full
    profile (every column's stats + 5 sample rows) can blow past that on its
    own before the model even responds. This shrinks the profile — dropping
    sample rows first, then trimming per-column sample values — until the
    JSON representation fits comfortably under the limit, regardless of how
    many columns or rows the source CSV has.
    """
    trimmed = json.loads(json.dumps(profile, default=str))  # deep copy

    def size():
        return len(json.dumps(trimmed, default=str))

    # Step 1: cut sample_rows down, then drop entirely if still too big
    if "sample_rows" in trimmed and size() > max_chars:
        trimmed["sample_rows"] = trimmed["sample_rows"][:2]
    if "sample_rows" in trimmed and size() > max_chars:
        del trimmed["sample_rows"]

    # Step 2: trim each column's sample_values list
    if size() > max_chars:
        for col in trimmed.get("columns", []):
            if "sample_values" in col:
                col["sample_values"] = [str(v)[:30] for v in col["sample_values"][:3]]

    # Step 3: last resort — cap the number of columns described in detail
    if size() > max_chars:
        cols = trimmed.get("columns", [])
        if len(cols) > 25:
            trimmed["columns"] = cols[:25]
            trimmed["_note"] = f"{len(cols) - 25} additional columns omitted from this profile to fit the prompt size limit."

    return trimmed


def build_system_prompt(profile: dict, engine: str) -> str:
    schema_txt = json.dumps(trim_profile_for_prompt(profile), indent=2, default=str)
    if engine == "sql":
        return f"""You are a data analyst. You write DuckDB SQL only.

Table available: {profile['table_name']}

Full data profile (schema, stats, sample rows):
{schema_txt}

Rules:
- Return ONLY a JSON object: {{"sql": "<query>", "explanation": "<1 sentence>"}}
- No markdown fences, no prose outside the JSON.
- Query must run in DuckDB against the table `{profile['table_name']}`.
- Never use DROP/DELETE/UPDATE/INSERT/ALTER — read-only analysis only.
- Prefer SQL for filtering, aggregation, joins, ranking, grouping.
"""
    else:
        return f"""You are a data analyst. You write Python (pandas + matplotlib) only.

A pandas DataFrame named `df` is already loaded with this data:
{schema_txt}

Rules:
- Return ONLY a JSON object: {{"code": "<python code>", "explanation": "<1 sentence>"}}
- No markdown fences, no prose outside the JSON.
- The code must assign its final tabular result to a variable `result` (a DataFrame,
  Series, or dict), and if a chart is produced, save it to `chart.png` using matplotlib
  (do not call plt.show()).
- Do not read/write any files other than `chart.png`. No network calls. No `os.system`.
- Use only pandas, numpy, matplotlib — assume they're already imported.
"""


def ask_claude_for_code(question: str, profile: dict, engine: str) -> dict:
    system = build_system_prompt(profile, engine)
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=600,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
    )
    text = resp.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def run_sql(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    lowered = sql.lower()
    for banned in ["drop ", "delete ", "update ", "insert ", "alter ", "attach "]:
        if banned in lowered:
            raise ValueError(f"Query contains disallowed keyword: {banned.strip()}")
    return con.execute(sql).df()


def run_python_sandboxed(code: str, df: pd.DataFrame, workdir: str) -> dict:
    data_path = os.path.join(workdir, "data.pkl")
    df.to_pickle(data_path)

    runner = f"""
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, os

df = pd.read_pickle(r"{data_path}")
os.chdir(r"{workdir}")

{code}

out = result
if isinstance(out, pd.DataFrame):
    print("__RESULT_JSON__" + out.head(200).to_json(orient="records"))
elif isinstance(out, pd.Series):
    print("__RESULT_JSON__" + out.to_frame().reset_index().to_json(orient="records"))
else:
    print("__RESULT_JSON__" + json.dumps(out, default=str))
"""
    script_path = os.path.join(workdir, "script.py")
    with open(script_path, "w") as f:
        f.write(runner)

    proc = subprocess.run(
        [sys.executable, script_path],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=workdir,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-4000:])

    out_line = [l for l in proc.stdout.splitlines() if l.startswith("__RESULT_JSON__")]
    result_json = json.loads(out_line[-1].replace("__RESULT_JSON__", "")) if out_line else None
    chart_path = os.path.join(workdir, "chart.png")
    chart_exists = os.path.exists(chart_path)
    return {"result": result_json, "chart_path": chart_path if chart_exists else None}


def generate_insight(question: str, result_preview: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=400,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a data analyst explaining results to a non-technical stakeholder. "
                    "Given a question and the computed result, write 2-4 sentences: lead with "
                    "the key takeaway (the 'so what'), note anything surprising, and suggest one "
                    "follow-up angle worth exploring. Plain language, no jargon."
                ),
            },
            {"role": "user", "content": f"Question: {question}\n\nResult:\n{result_preview}"},
        ],
    )
    return resp.choices[0].message.content.strip()


def suggest_dashboard(profile: dict) -> list[dict]:
    """Ask the model to propose a handful of chart specs based on the schema alone."""
    system = f"""Given this dataset profile, propose 4-6 dashboard chart specs.

{json.dumps(trim_profile_for_prompt(profile), indent=2, default=str)}

Return ONLY a JSON object of this exact shape, nothing else:
{{"charts": [
  {{"title": "...", "chart_type": "bar|line|pie|scatter", "sql": "<DuckDB SQL against table {profile['table_name']}>"}}
]}}

CRITICAL rule for every "sql" query: the SELECT must alias its two output
columns as exactly "x" and "y" — nothing else. For example:
  SELECT neighborhood AS x, AVG(saleprice) AS y FROM {profile['table_name']} GROUP BY x ORDER BY y DESC
This is mandatory even if it feels redundant — charts are rendered by reading
columns literally named x and y, so any other alias will show an empty chart.
No markdown fences, no prose, no explanation — just the JSON object."""
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=1200,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": "Propose the dashboard."},
        ],
    )
    text = resp.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model did not return valid JSON for dashboard: {e}\nRaw output: {text[:500]}")
    charts = parsed.get("charts", parsed if isinstance(parsed, list) else [])
    if not isinstance(charts, list):
        raise ValueError(f"Expected a list of chart specs, got: {type(charts)}")
    return charts


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@app.post("/auth/signup", response_model=TokenResponse)
def signup(req: SignupRequest):
    email = req.email.lower()
    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "An account with this email already exists")

    user_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO users (id, email, hashed_password, created_at) VALUES (?, ?, ?, ?)",
        (user_id, email, hash_password(req.password), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()

    token = create_access_token(user_id, email)
    return {"access_token": token, "token_type": "bearer", "email": email}


@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    email = req.email.lower()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT id, hashed_password FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if not row or not verify_password(req.password, row[1]):
        raise HTTPException(401, "Incorrect email or password")

    token = create_access_token(row[0], email)
    return {"access_token": token, "token_type": "bearer", "email": email}


@app.get("/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# Data routes — every one requires a valid token and checks session ownership
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload_csv(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    session_id = str(uuid.uuid4())
    workdir = os.path.join(SESSIONS_DIR, session_id)
    os.makedirs(workdir, exist_ok=True)
    csv_path = os.path.join(workdir, "data.csv")
    with open(csv_path, "wb") as f:
        f.write(raw)

    table_name = "data"
    con = duckdb.connect(database=":memory:")
    con.register(table_name, df)
    con.execute(f"CREATE TABLE {table_name}_t AS SELECT * FROM {table_name}")
    table_name = f"{table_name}_t"

    profile = profile_dataframe(df, table_name)

    SESSIONS[session_id] = {
        "df": df, "con": con, "table_name": table_name,
        "profile": profile, "workdir": workdir, "user_id": current_user["id"],
    }
    persist_session_metadata(session_id, current_user["id"], csv_path, table_name, profile)

    health = compute_data_health(df)
    return {"session_id": session_id, "profile": profile, "health": health}


@app.post("/query")
def query(req: QueryRequest, current_user: dict = Depends(get_current_user)):
    session = get_session(req.session_id, current_user["id"])
    if not session:
        raise HTTPException(404, "Session not found — upload a CSV first")

    engine = req.engine
    if engine == "auto":
        # Explicit language always wins: if the user names a language, use it.
        q_lower = req.question.lower()
        if "python" in q_lower:
            engine = "python"
        elif "sql" in q_lower:
            engine = "sql"
        else:
            # Otherwise infer from intent: stats/ML/chart-heavy language -> python, else SQL
            py_signals = [
                "correlat", "predict", "forecast", "regression", "distribution", "outlier", "model",
                "plot", "chart", "graph", "pie", "histogram", "boxplot", "scatter", "visuali",
            ]
            engine = "python" if any(s in q_lower for s in py_signals) else "sql"

    last_error = None
    for attempt in range(3):
        try:
            spec = ask_claude_for_code(
                req.question if not last_error else
                f"{req.question}\n\nPrevious attempt failed with error:\n{last_error}\nFix it.",
                session["profile"],
                engine,
            )
            if engine == "sql":
                df_result = run_sql(session["con"], spec["sql"])
                return {
                    "engine": "sql",
                    "code": spec["sql"],
                    "explanation": spec.get("explanation", ""),
                    "columns": list(df_result.columns),
                    "rows": json.loads(df_result.head(200).to_json(orient="records")),
                    "insight_context": df_result.head(50).to_string(),
                }
            else:
                out = run_python_sandboxed(spec["code"], session["df"], session["workdir"])
                chart_url = None
                if out["chart_path"]:
                    chart_url = f"/chart/{req.session_id}"
                return {
                    "engine": "python",
                    "code": spec["code"],
                    "explanation": spec.get("explanation", ""),
                    "result": out["result"],
                    "chart_url": chart_url,
                    "insight_context": json.dumps(out["result"])[:3000],
                }
        except Exception as e:
            last_error = f"{e}\n{traceback.format_exc()[-1500:]}"
            continue

    raise HTTPException(500, f"Failed after 3 attempts. Last error: {last_error}")

@app.post("/query/stream")
def query_stream(req: QueryRequest, current_user: dict = Depends(get_current_user)):
    """
    Same job as /query, but streams the raw model output live as it's
    generated (true token-by-token, not a simulated typing effect), then
    executes the code and appends the final structured result behind a
    __FINAL__ marker once the model finishes. No retry-on-error here (retries
    don't make sense mid-stream) — a failed attempt surfaces as __ERROR__ and
    the frontend shows it directly.
    """
    session = get_session(req.session_id, current_user["id"])
    if not session:
        raise HTTPException(404, "Session not found — upload a CSV first")

    engine = req.engine
    if engine == "auto":
        q_lower = req.question.lower()
        if "python" in q_lower:
            engine = "python"
        elif "sql" in q_lower:
            engine = "sql"
        else:
            py_signals = [
                "correlat", "predict", "forecast", "regression", "distribution", "outlier", "model",
                "plot", "chart", "graph", "pie", "histogram", "boxplot", "scatter", "visuali",
            ]
            engine = "python" if any(s in q_lower for s in py_signals) else "sql"

    system = build_system_prompt(session["profile"], engine)

    # Recent Q&A turns give the model short-term memory, so a follow-up like
    # "now break that down by region" resolves against what was just asked —
    # capped at the last 3 turns to keep the prompt small.
    history_messages = []
    for turn in (req.history or [])[-3:]:
        history_messages.append({"role": "user", "content": turn.get("question", "")})
        history_messages.append({
            "role": "assistant",
            "content": json.dumps({"code": turn.get("code", ""), "explanation": turn.get("explanation", "")}),
        })

    def gen():
        # Moderation runs on a background thread starting immediately, in
        # parallel with code generation — instead of waiting for it to finish
        # before even starting to generate. Tokens are buffered until the
        # moderation result is known, then flushed all at once (fast, since
        # moderation is typically much quicker than full code generation);
        # after that, remaining tokens stream live as normal.
        mod_result = {}

        def run_moderation():
            mod_result.update(moderate(req.question))

        mod_thread = threading.Thread(target=run_moderation)
        mod_thread.start()

        full_text = ""
        buffer = []
        moderation_cleared = False
        try:
            stream = client.chat.completions.create(
                model=MODEL,
                max_tokens=600,
                stream=True,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": req.question},
                ],
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if not delta:
                    continue
                full_text += delta

                if moderation_cleared:
                    yield delta
                    continue

                if mod_thread.is_alive():
                    buffer.append(delta)
                    continue

                mod_thread.join()
                if mod_result.get("flagged"):
                    yield "__ERROR__This question can't be processed — please ask something about analyzing your uploaded data."
                    return
                moderation_cleared = True
                for b in buffer:
                    yield b
                buffer = []
                yield delta

            if not moderation_cleared:
                mod_thread.join()
                if mod_result.get("flagged"):
                    yield "__ERROR__This question can't be processed — please ask something about analyzing your uploaded data."
                    return
                for b in buffer:
                    yield b
        except Exception as e:
            yield f"__ERROR__{e}"
            return

        text = full_text.strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            spec = json.loads(text)
            if engine == "sql":
                df_result = run_sql(session["con"], spec["sql"])
                payload = {
                    "engine": "sql",
                    "code": spec["sql"],
                    "explanation": spec.get("explanation", ""),
                    "columns": list(df_result.columns),
                    "rows": json.loads(df_result.head(200).to_json(orient="records")),
                    "insight_context": df_result.head(50).to_string(),
                }
            else:
                out = run_python_sandboxed(spec["code"], session["df"], session["workdir"])
                chart_url = f"/chart/{req.session_id}" if out["chart_path"] else None
                payload = {
                    "engine": "python",
                    "code": spec["code"],
                    "explanation": spec.get("explanation", ""),
                    "result": out["result"],
                    "chart_url": chart_url,
                    "insight_context": json.dumps(out["result"])[:3000],
                }
            yield "__FINAL__" + json.dumps(payload)
        except Exception as e:
            yield f"__ERROR__{e}"

    return StreamingResponse(gen(), media_type="text/plain")


@app.get("/chart/{session_id}")
def get_chart(session_id: str, current_user: dict = Depends(get_current_user)):
    session = get_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(404, "Session not found")
    path = os.path.join(session["workdir"], "chart.png")
    if not os.path.exists(path):
        raise HTTPException(404, "No chart generated for this session yet")
    return FileResponse(path, media_type="image/png")


@app.post("/dashboard")
def dashboard(req: DashboardRequest, current_user: dict = Depends(get_current_user)):
    session = get_session(req.session_id, current_user["id"])
    if not session:
        raise HTTPException(404, "Session not found — upload a CSV first")

    try:
        specs = suggest_dashboard(session["profile"])
    except Exception as e:
        raise HTTPException(500, f"Could not generate dashboard: {e}")

    charts = []
    for spec in specs:
        try:
            df_result = run_sql(session["con"], spec["sql"])
            if "x" not in df_result.columns or "y" not in df_result.columns:
                continue  # model didn't follow the x/y aliasing rule — skip rather than show a broken chart
            charts.append({
                "title": spec["title"],
                "chart_type": spec["chart_type"],
                "x": "x",
                "y": "y",
                "data": json.loads(df_result.to_json(orient="records")),
            })
        except Exception:
            continue
    return {"charts": charts}


@app.get("/distribution/{session_id}/{column}/{chart_type}")
def distribution_chart(session_id: str, column: str, chart_type: str, current_user: dict = Depends(get_current_user)):
    session = get_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(404, "Session not found — upload a CSV first")

    df = session["df"]
    if column not in df.columns:
        raise HTTPException(400, f"Unknown column: {column}")

    series = df[column].dropna()
    if not pd.api.types.is_numeric_dtype(series):
        raise HTTPException(400, f"'{column}' is not numeric — this chart needs a numeric column")
    if series.empty:
        raise HTTPException(400, f"'{column}' has no non-null values to plot")

    fig, ax = plt.subplots(figsize=(6, 3.6))
    fig.patch.set_facecolor("#161B26")
    ax.set_facecolor("#161B26")

    if chart_type == "kde":
        series.plot.kde(ax=ax, color="#E8A33D", linewidth=2)
        ax.fill_between(ax.lines[0].get_xdata(), ax.lines[0].get_ydata(), color="#E8A33D", alpha=0.15)
        ax.set_title(f"Distribution (KDE) — {column}", color="#E7E9EE", fontsize=12)
        ax.set_xlabel(column, color="#8B93A7")
        ax.set_ylabel("Density", color="#8B93A7")
    elif chart_type == "box":
        bp = ax.boxplot(series, vert=False, patch_artist=True, widths=0.5)
        for box in bp["boxes"]:
            box.set(facecolor="#4FD1C5", edgecolor="#2A3140")
        for median in bp["medians"]:
            median.set(color="#E8697D", linewidth=2)
        for whisker in bp["whiskers"] + bp["caps"]:
            whisker.set(color="#8B93A7")
        ax.set_yticks([])
        ax.set_title(f"Boxplot — {column}", color="#E7E9EE", fontsize=12)
        ax.set_xlabel(column, color="#8B93A7")
    elif chart_type == "hist":
        bins = min(30, max(5, series.nunique()))
        ax.hist(series, bins=bins, color="#7C9EFF", edgecolor="#161B26")
        ax.set_title(f"Histogram — {column}", color="#E7E9EE", fontsize=12)
        ax.set_xlabel(column, color="#8B93A7")
        ax.set_ylabel("Count", color="#8B93A7")
    elif chart_type == "violin":
        if series.nunique() < 3:
            plt.close(fig)
            raise HTTPException(400, f"'{column}' has too few distinct values for a violin plot")
        vp = ax.violinplot(series, vert=False, showmedians=True)
        for body in vp["bodies"]:
            body.set_facecolor("#C792EA")
            body.set_edgecolor("#2A3140")
            body.set_alpha(0.7)
        ax.set_yticks([])
        ax.set_title(f"Violin — {column}", color="#E7E9EE", fontsize=12)
        ax.set_xlabel(column, color="#8B93A7")
    else:
        plt.close(fig)
        raise HTTPException(400, "chart_type must be one of: kde, box, hist, violin")

    ax.tick_params(colors="#8B93A7")
    for spine in ax.spines.values():
        spine.set_color("#2A3140")

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@app.get("/category-counts/{session_id}/{column}")
def category_counts(session_id: str, column: str, current_user: dict = Depends(get_current_user)):
    session = get_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(404, "Session not found — upload a CSV first")

    valid_columns = {c["name"] for c in session["profile"]["columns"]}
    if column not in valid_columns:
        raise HTTPException(400, f"Unknown column: {column}")

    table = session["table_name"]
    sql = f'SELECT "{column}" AS value, COUNT(*) AS count FROM {table} GROUP BY "{column}" ORDER BY count DESC LIMIT 20'
    df_result = session["con"].execute(sql).df()
    return {"column": column, "data": json.loads(df_result.to_json(orient="records"))}


@app.post("/ml/train")
def ml_train(req: MLRequest, current_user: dict = Depends(get_current_user)):
    session = get_session(req.session_id, current_user["id"])
    if not session:
        raise HTTPException(404, "Session not found — upload a CSV first")

    df = session["df"].copy()
    if req.target not in df.columns:
        raise HTTPException(400, f"Unknown column: {req.target}")
    if len(df) < 20:
        raise HTTPException(400, "Need at least 20 rows to train models reliably")

    df = df.dropna(subset=[req.target])
    y_raw = df[req.target]
    X = df.drop(columns=[req.target])

    keep_cols = []
    for col in X.columns:
        if X[col].isna().mean() > 0.5:
            continue
        if X[col].dtype == "object" and X[col].nunique() > 50:
            continue
        keep_cols.append(col)
    X = X[keep_cols]
    if X.shape[1] == 0:
        raise HTTPException(400, "No usable feature columns remain after filtering")

    numeric_cols = X.select_dtypes(include="number").columns.tolist()
    cat_cols = [c for c in X.columns if c not in numeric_cols]

    is_classification = (not pd.api.types.is_numeric_dtype(y_raw)) or y_raw.nunique() <= 10
    task = "classification" if is_classification else "regression"

    if is_classification:
        le = LabelEncoder()
        y = le.fit_transform(y_raw.astype(str))
    else:
        y = y_raw.values

    preprocessor = ColumnTransformer([
        ("num", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), numeric_cols),
        ("cat", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), cat_cols),
    ])

    try:
        stratify = y if is_classification and pd.Series(y).value_counts().min() >= 2 else None
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=stratify
        )
    except Exception as e:
        raise HTTPException(400, f"Could not split data: {e}")

    if is_classification:
        models = {
            "Logistic Regression": LogisticRegression(max_iter=1000),
            "Random Forest": RandomForestClassifier(n_estimators=200, random_state=42),
            "Decision Tree": DecisionTreeClassifier(random_state=42),
            "K-Nearest Neighbors": KNeighborsClassifier(),
            "Naive Bayes": GaussianNB(),
        }
    else:
        models = {
            "Linear Regression": LinearRegression(),
            "Random Forest": RandomForestRegressor(n_estimators=200, random_state=42),
            "Decision Tree": DecisionTreeRegressor(random_state=42),
            "K-Nearest Neighbors": KNeighborsRegressor(),
            "Gradient Boosting": GradientBoostingRegressor(random_state=42),
        }

    results = []
    best_importance = None
    best_importance_score = -1
    best_overall_pipeline = None
    best_overall_score = -1

    for name, model in models.items():
        try:
            pipe = Pipeline([("prep", preprocessor), ("model", model)])
            pipe.fit(X_train, y_train)
            preds = pipe.predict(X_test)

            if is_classification:
                metrics = {
                    "accuracy": round(float(accuracy_score(y_test, preds)), 4),
                    "precision": round(float(precision_score(y_test, preds, average="weighted", zero_division=0)), 4),
                    "recall": round(float(recall_score(y_test, preds, average="weighted", zero_division=0)), 4),
                    "f1": round(float(f1_score(y_test, preds, average="weighted", zero_division=0)), 4),
                }
                primary_score = metrics["accuracy"]
            else:
                rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
                metrics = {
                    "r2": round(float(r2_score(y_test, preds)), 4),
                    "rmse": round(rmse, 4),
                    "mae": round(float(mean_absolute_error(y_test, preds)), 4),
                }
                primary_score = metrics["r2"]

            results.append({"model": name, "metrics": metrics})

            if primary_score > best_overall_score:
                best_overall_score = primary_score
                best_overall_pipeline = pipe

            # Surface feature importance from whichever tree-based model

            fitted_model = pipe.named_steps["model"]
            if hasattr(fitted_model, "feature_importances_") and primary_score > best_importance_score:
                try:
                    feature_names = pipe.named_steps["prep"].get_feature_names_out()
                    importances = fitted_model.feature_importances_
                    pairs = sorted(zip(feature_names, importances), key=lambda p: p[1], reverse=True)[:10]
                    best_importance = {
                        "model": name,
                        "features": [{"feature": str(f), "importance": round(float(v), 4)} for f, v in pairs],
                    }
                    best_importance_score = primary_score
                except Exception:
                    pass
        except Exception as e:
            results.append({"model": name, "error": str(e)})

    whatif_columns = []
    defaults = {}
    for col in X.columns:
        if col in numeric_cols:
            series = X[col].dropna()
            defaults[col] = float(series.median()) if not series.empty else 0.0
        else:
            series = X[col].dropna()
            defaults[col] = series.mode().iloc[0] if not series.empty else ""

    if best_overall_pipeline is not None:
        whatif_raw_cols = select_important_columns(X, top_n=8)
        for col in whatif_raw_cols:
            if col in numeric_cols:
                series = X[col].dropna()
                if series.empty:
                    continue
                whatif_columns.append({
                    "name": col, "type": "numeric",
                    "min": float(series.min()), "max": float(series.max()),
                    "default": defaults[col],
                })
            else:
                series = X[col].dropna()
                if series.empty:
                    continue
                top_options = series.astype(str).value_counts().head(8).index.tolist()
                whatif_columns.append({
                    "name": col, "type": "categorical",
                    "options": top_options, "default": defaults[col],
                })

        session["ml_model"] = {
            "target": req.target,
            "task": task,
            "pipeline": best_overall_pipeline,
            "label_encoder": le if is_classification else None,
            "defaults": defaults,
        }

    return to_native({
        "task": task,
        "target": req.target,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "n_features": len(numeric_cols) + len(cat_cols),
        "results": results,
        "feature_importance": best_importance,
        "whatif_columns": whatif_columns,
    })

@app.post("/ml/predict")
def ml_predict(req: PredictRequest, current_user: dict = Depends(get_current_user)):
    session = get_session(req.session_id, current_user["id"])
    if not session:
        raise HTTPException(404, "Session not found — upload a CSV first")

    model_info = session.get("ml_model")
    if not model_info:
        raise HTTPException(400, "Train a model first (ML Insights tab) before using What-If predictions")

    row = dict(model_info["defaults"])
    row.update(req.inputs)
    row_df = pd.DataFrame([row])

    try:
        pred = model_info["pipeline"].predict(row_df)[0]
    except Exception as e:
        raise HTTPException(400, f"Prediction failed: {e}")

    if model_info["task"] == "classification" and model_info["label_encoder"] is not None:
        pred = model_info["label_encoder"].inverse_transform([int(pred)])[0]
        return {"prediction": str(pred)}
    return {"prediction": float(pred)}

class InsightRequest(BaseModel):
    question: str
    context: str


@app.post("/insight/stream")
def insight_stream(req: InsightRequest, current_user: dict = Depends(get_current_user)):
    """Streams the plain-English explanation token-by-token instead of
    waiting for the full response — this is what makes the UI feel fast."""
    def token_generator():
        stream = client.chat.completions.create(
            model=MODEL,
            max_tokens=400,
            stream=True,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a data analyst explaining results to a non-technical stakeholder. "
                        "Given a question and the computed result, write 2-4 sentences: lead with "
                        "the key takeaway (the 'so what'), note anything surprising, and suggest one "
                        "follow-up angle worth exploring. Plain language, no jargon."
                    ),
                },
                {"role": "user", "content": f"Question: {req.question}\n\nResult:\n{req.context}"},
            ],
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    return StreamingResponse(token_generator(), media_type="text/plain")

@app.get("/correlation/{session_id}")
def correlation_heatmap(session_id: str, current_user: dict = Depends(get_current_user)):
    """Renders a correlation heatmap across the most important numeric
    columns (reusing the same PCA-based ranking used for the schema profile,
    capped at 15 columns so it stays readable on wide datasets)."""
    session = get_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(404, "Session not found — upload a CSV first")

    df = session["df"]
    numeric_df = df.select_dtypes(include="number").dropna(axis=1, how="all")
    if numeric_df.shape[1] < 2:
        raise HTTPException(400, "Need at least 2 numeric columns for a correlation heatmap")

    cols = select_important_columns(numeric_df, top_n=15)
    corr = numeric_df[cols].corr()
    n = len(cols)

    fig, ax = plt.subplots(figsize=(max(6, n * 0.6), max(5, n * 0.55)))
    fig.patch.set_facecolor("#161B26")
    ax.set_facecolor("#161B26")
    im = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)

    ax.set_xticks(range(n))
    ax.set_xticklabels(cols, rotation=45, ha="right", color="#8B93A7", fontsize=9)
    ax.set_yticks(range(n))
    ax.set_yticklabels(cols, color="#8B93A7", fontsize=9)

    for i in range(n):
        for j in range(n):
            val = corr.values[i, j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                     color="white" if abs(val) > 0.4 else "#B8BFCC", fontsize=7)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.yaxis.set_tick_params(color="#8B93A7")
    for label in cbar.ax.get_yticklabels():
        label.set_color("#8B93A7")

    ax.set_title("Correlation Heatmap", color="#E7E9EE", fontsize=12)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    ) 

