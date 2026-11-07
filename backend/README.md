Triple Spark — Arabic Smart Academic Advisor

Project Overview

Triple Spark is an Arabic Smart Academic Advisor designed to help university students access accurate academic information through a conversational interface.

The system addresses the difficulty students face when searching through scattered university regulations, academic policies, student guides, and study plans.

It uses Retrieval-Augmented Generation (RAG) to retrieve relevant information from university documents and generate answers based exclusively on the retrieved context.

Each answer includes verifiable evidence, the original document name, and the relevant page number. When the available documents do not contain sufficient information, the system refuses to provide an unsupported answer.

System Architecture

Triple Spark follows a Retrieval-Augmented Generation (RAG) architecture consisting of two main stages.

1. Data Preparation

Provided Documents → Data Processing (Extraction, Cleaning, and Chunking) → Embeddings Generation → ChromaDB (Vector Storage)

2. Question Answering

Student Question → Vector Search → Retrieve Relevant Chunks → Gemini AI → Evidence Verification → Triple Spark Interface

The system returns the generated answer along with its source document and page number.

Technologies

* Backend: Python and FastAPI.
* Vector Database: ChromaDB.
* Language Model: Google Gemini.
* Frontend: Lovable.
* Data Processing: Python-based extraction, cleaning, and chunking.
* Retrieval: Vector similarity search.

Frontend Integration

The frontend is developed independently using Lovable and communicates with the FastAPI backend through API requests.

The interface provides an Arabic conversational experience and displays generated answers together with their supporting sources and page numbers.

The backend handles document retrieval, answer generation, and evidence verification.

⸻

Windows setup (PowerShell)

Install Python 3.12 and run these commands from the project root.

Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }

If py is unavailable, use the installed Python 3.12 executable to create .venv. Add your own GEMINI_API_KEY to the local .env for live answers. Keep that file private. Run the remaining commands from backend.

Run

.\.venv\Scripts\python.exe -m uvicorn main:app --reload

Open http://127.0.0.1:8000/docs and test POST /api/ask with {"question":"كيف أسجل موادي؟"}.

GET / is a liveness check. The first nonblank POST /api/ask initializes Gemini and builds the index. Operational failures return HTTP 500 with a safe detail message. Unsupported questions return HTTP 200 with the Arabic refusal and an empty sources array.

React development origins on localhost and 127.0.0.1 are allowed by default on ports 5173 and 3000. If React uses another host or port, include its exact origin in the comma-separated FRONTEND_ORIGINS setting.

Since the Lovable frontend is hosted independently, its deployed origin must be included in FRONTEND_ORIGINS when required for cross-origin API requests.

Dataset handoff

Provide a UTF-8 JSON file containing a nonempty array of chunk objects. Every chunk requires these five fields.

[
  {
    "id": "registration-1",
    "text": "يمكن للطلاب تسجيل المواد من خلال البوابة الإلكترونية للجامعة.",
    "source": "registration.pdf",
    "page": 3,
    "chunk_index": 0
  }
]

* id, text, and source must be strings with nonblank content. IDs must be unique across the entire dataset. Use source for the original document name.
* page must be a positive integer or a nonblank page label such as iv or A-12. Numeric page strings must be positive. Preserve the original page reference.
* chunk_index must be a nonnegative integer. Booleans are invalid for page and chunk_index.
* Extra fields are allowed. The loader preserves them, and the index uses source and page as citation metadata.
* Keep Arabic text legible and preserve course codes and column labels in short table excerpts.

Place the file at data/chunks.json or select another file with DATA_PATH. Relative paths resolve from backend. Restart after replacing the dataset. To validate and count chunks without loading embeddings or contacting Gemini, run this command with Python 3.12 and replace the path as needed.

python -c "from data_loader import load_chunks; print(len(load_chunks('data/chunks.json')))"

API contract

Send POST /api/ask with Content-Type: application/json.

{"question":"كيف أسجل موادي؟"}

A supported answer returns HTTP 200. sources[].page is always a string.

{"answer":"يمكنك تسجيل المواد عبر البوابة الإلكترونية للجامعة.","sources":[{"source":"registration.pdf","page":"3"}]}

Case	HTTP status	Response
Unsupported question	200	{"answer":"لا توجد معلومات كافية للإجابة عن هذا السؤال.","sources":[]}
Whitespace-only question	200	{"answer":"يرجى إدخال سؤال.","sources":[]}
Missing question, empty string, invalid type, or invalid JSON	422	FastAPI validation details in a detail array
Backend operational failure	500	A safe message such as {"detail":"Could not retrieve document chunks."}

Run tests

The suite uses synthetic data, controlled embeddings, and mocked Gemini responses. With the tested python-dotenv version, run this in the project virtual environment to disable loading local credentials during tests.

$env:PYTHON_DOTENV_DISABLED = '1'
try { ./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider }
finally { $env:PYTHON_DOTENV_DISABLED = $null }

Evaluate retrieval

Create a UTF-8 JSON file with manually labeled chunk IDs from the dataset being evaluated. Use an empty ID list for questions the documents cannot answer.

[
  {"question": "إمتى ببلّش تسجيل المواد؟", "expected_chunk_ids": ["registration-1"], "should_refuse": false},
  {"question": "كم قيمة منحة التفوق؟", "expected_chunk_ids": [], "should_refuse": true}
]
./.venv/Scripts/python.exe evaluate_retrieval.py path/to/cases.json --chunks path/to/chunks.json --k 3

The evaluator uses the configured embedding model and reports candidate IDs, document names, pages, and distances. Mean Recall@k averages the fraction of labeled relevant chunks retrieved per answerable question. Unsupported questions are counted separately, including how many received any candidates. Retrieval evaluation runs the embedding model without calling Gemini. Use evaluate.py separately for live answer and refusal review with data/eval_questions.json.

Start with MAX_DISTANCE disabled and compare several k values on a calibration set with formal Arabic, Palestinian colloquial paraphrases, multi-chunk questions, and plausible unsupported questions. Compare the distances for labeled relevant passages, manually judged distractors, and the nearest candidates for unsupported questions. Try candidate MAX_DISTANCE values in the process environment and measure both lost relevant chunks and unsupported questions still receiving candidates. Check the selected settings on a held-out set. Keep the cutoff disabled if the distances do not separate these cases reliably. Recalibrate after changing the corpus or embedding configuration.

Dependency reproducibility

requirements.txt lists direct dependencies. The Python 3.12 offline suite used FastAPI 0.162.0, Pydantic 2.14.3, python-dotenv 1.2.4, ChromaDB 1.5.9, google-genai 3.0.0, pytest 9.2.0, httpx 0.28.1, and NumPy 2.5.4. The local server smoke test used Uvicorn 0.54.0. The offline suite used controlled vectors in place of Sentence Transformers, so it does not establish a tested version for that package.

For the submission, reproduce these versions in a clean Python 3.12 environment, verify the actual Sentence Transformers and PyTorch versions on the demo machine, then capture the complete resolved environment with python -m pip freeze. Install that snapshot in a second clean environment and rerun the tests and demo smoke check before sharing it.

AI tools disclosure

OpenAI Codex assisted with backend implementation, automated tests, and documentation. Google Gemini generates Arabic answers and returns structured evidence from retrieved excerpts. The backend verifies the quotes against the source chunks before returning citations.

Important limits

* The backend verifies that evidence quotes appear in the cited chunks. Manually check whether those quotes support the answer’s claims.
* The first nonblank question builds the in-memory Chroma index for that server process.
* No automatic PDF extraction here: Mira supplies cleaned chunks.
* No automatic objective answer accuracy metric; evaluation script prints predictions for manual checking.
* If no distance threshold is configured, a related-looking chunk may still be irrelevant; use refusal testing and consider calibrated filtering.
* Test Gemini model availability/quota and network before demo.
* Keep API keys server-side; CORS is not authentication.
* localhost only reaches the same machine. For two laptops, use a trusted LAN or host both apps together.