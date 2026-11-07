# Triple Spark — AI Academic Advising Assistant

Triple Spark helps An-Najah National University students find information across study plans and academic regulations. Students can ask questions in Arabic or English and receive Arabic answers with citations to the university materials used.

## What it does

- Looks up course names, codes, and prerequisites directly in the catalog. Comparisons read each course's prerequisites from its own record.
- Retrieves evidence for general academic questions, including regulations, and asks Gemini to answer using the retrieved excerpts.
- Handles recent follow-up questions, including shared prerequisites. It asks for clarification when a course reference is ambiguous.
- Shows source links or document names and available page references. Unsupported questions return a refusal.

## Architecture

The React and TanStack Start frontend sends questions to FastAPI. The backend first checks whether it can resolve a course directly from catalog metadata. For other questions, multilingual Sentence Transformers embeddings and ChromaDB retrieve relevant excerpts. A lexical reranker helps surface regulations. Gemini returns a structured answer with evidence quotes, and the backend checks those quotes against the cited excerpts before returning source metadata.

| Path | Purpose |
| --- | --- |
| [`backend/`](backend/) | FastAPI, retrieval, course lookup, conversation handling, and evidence verification |
| [`backend/data/`](backend/data/) | University chunks and example evaluation questions |
| [`backend/tests/`](backend/tests/) | Dataset, retrieval, API, and grounding regression tests |
| [`frontend/`](frontend/) | React interface, Vite development proxy, and Bun lockfile |
| [`frontend/src/test/`](frontend/src/test/) | Chat, routing, and citation display tests |

## Local setup on Windows

You’ll need Python 3.12, Node.js 24 LTS, Bun, and a Gemini API key. The first use of the embedding model needs access to its weights unless they are already cached.

### Backend

Run from the project root in PowerShell.

```powershell
Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
```

Set `GEMINI_API_KEY` in the local `backend/.env` file, or provide it through the server process environment. Keep it out of Git and frontend variables. See [`backend/.env.example`](backend/.env.example) for the available settings.

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The backend uses `backend/data/chunks.json` by default. `GET /` checks liveness. The first nonblank question builds the in-memory index. See the [backend guide](backend/README.md) for the dataset contract, API behavior, and retrieval evaluation.

### Frontend

In a second PowerShell window, run from the project root.

```powershell
Set-Location frontend
bun install --frozen-lockfile
node .\node_modules\vite\bin\vite.js dev --host 127.0.0.1 --port 5173 --strictPort
```

Open [Triple Spark](http://127.0.0.1:5173). The Vite proxy sends `/api/ask` to FastAPI on port 8000. If the backend uses another address, set `RAG_BACKEND_URL` before starting Vite.

Try asking **ما المتطلب السابق لمساق مشروع تخرج 1 في هندسة الحاسوب؟**, then **شو اسم هاد المتطلب؟**. Open the citation to check the course record. When a source has no reliable page reference, the interface shows the source without a page label.

## Testing

From `backend`, run the offline test suite. It uses controlled embeddings and mocked Gemini calls.

```powershell
$env:PYTHON_DOTENV_DISABLED = '1'
try { .\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider }
finally { $env:PYTHON_DOTENV_DISABLED = $null }
```

From `frontend`, run the tests and type check after installing dependencies.

```powershell
node .\node_modules\vitest\vitest.mjs run
node .\node_modules\typescript\bin\tsc --noEmit
```

## Grounding and limitations

- Catalog answers use the matching university records. For generated answers, citations identify excerpts containing the quoted evidence. Quote matching verifies the source of the quote. Whether it supports every claim still requires review.
- Academic rules can vary by program, plan version, or cohort. Confirm consequential decisions with the current university guide or an academic advisor.
- The first request can be slower because the backend builds the index in memory. Gemini-dependent requests can fail during provider outages, timeouts, or quota limits. The backend retries an upstream 503 once and returns an error if the service remains unavailable.
- The frontend sends a short recent conversation history. Ambiguous references may require the student to restate a course name or code.

## Team

| Teammate | Role |
| --- | --- |
| Mira | Academic Data |
| Raneem | RAG/Backend |
| Lana | Frontend |
