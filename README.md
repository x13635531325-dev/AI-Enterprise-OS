# AI Enterprise OS

Enterprise-grade AI application platform built with React, FastAPI, Scrapling, Alibaba Cloud OSS, MySQL, SQLite, model routing, observability, RAG, citation guardrails, and offline evaluation.

## What This Project Demonstrates

AI Enterprise OS is a run-first LLM application. Every user request becomes a persisted Run with steps, trace spans, model calls, metrics, retries, tool calls, citations, and quality metadata.

Core capabilities:

- React chat console with workflow selection, run history, model health, traces, retrieval details, prompt metadata, and citation guardrail status.
- FastAPI backend with workflow execution APIs.
- Model Gateway with mock, DeepSeek, and OpenAI provider support.
- Circuit breaker and fallback model routing for unreliable model calls.
- SQLite persistence for runs, traces, model calls, tool calls, knowledge documents, chunks, FTS index, and embeddings.
- Hybrid RAG retrieval with lexical search, vector search, RRF fusion, optional reranker, grounded prompts, and citations.
- Prompt versioning and prompt template hashing.
- Citation guardrail for numbered source references.
- Offline RAG answer evaluation with golden sets and CI quality gate.
- Scrapling 0.4.11 crawl control plane with HTTP, dynamic-browser, and stealth sessions.
- Editable CSS/XPath extraction rules, adaptive selectors, URL following, concurrency, throttling, robots.txt compliance, and checkpoints.
- No-code presets for article text, downloadable files, and images, with selectors isolated in an advanced custom mode.
- Same-domain asset downloads with extension allowlists, count limits, size limits, and original filename preservation.
- Selectable, idempotent delivery to local storage, Alibaba Cloud OSS, and MySQL.
- Persisted crawl jobs, pages, per-destination delivery attempts, retries, and interrupted-job recovery.
- GitHub Actions workflow for backend tests, RAG eval, frontend lint, and frontend build.

## Repository Layout

```text
backend/
  app/
    api/routes/              FastAPI route handlers
    core/                    environment-driven configuration
    evals/                   RAG evaluation harness, golden sets, report tools
    gateways/                model gateway, model router, providers, circuit breaker
    schemas/                 API and persistence DTOs
    services/                run, knowledge, embedding, reranking, prompts, guardrails
    storage/                 SQLite repositories
    tools/                   tool registry and tool implementations
    workflows/               workflow implementations
    crawling/                Scrapling runner, extraction, local/OSS/MySQL pipeline
frontend/
  react-chat/                React + Vite chat console
scripts/                     local developer scripts
tests/                       backend unit and integration tests
.github/workflows/           CI quality gate
```

## Requirements

- Python 3.12
- Node.js 22
- npm
- Optional: local embedding/reranker model cache if `*_LOCAL_FILES_ONLY=true`

## Backend Setup

Create your backend environment file:

```powershell
Copy-Item backend\.env.example backend\.env
```

Then edit `backend/.env`.

For local mock-only development:

```env
MODEL_PROVIDER=mock
```

For DeepSeek:

```env
MODEL_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_MODEL=deepseek-v4-flash
```

Local crawl delivery works without external credentials:

```env
CRAWL_LOCAL_STORAGE_DIR=./data/crawl_exports
```

For optional cloud and database delivery, add rotated RAM credentials and the MySQL server connection:

```env
OSS_ACCESS_KEY_ID=
OSS_ACCESS_KEY_SECRET=
OSS_SECURITY_TOKEN=
OSS_REGION=cn-beijing
OSS_ENDPOINT=https://oss-cn-beijing.aliyuncs.com
OSS_DEFAULT_BUCKET=xuefangedufile
OSS_CONTENT_BUCKET=xuefangedu
OSS_REVIEW_BUCKET=xuefang-jiaoyan

MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DATABASE=
```

Use a least-privilege RAM user or STS credentials. Never use the STS service endpoint as the OSS upload endpoint. For Beijing OSS, the public upload endpoint is `https://oss-cn-beijing.aliyuncs.com`.

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

HTTP crawl mode works after dependency installation. Install browser binaries before using `dynamic` or `stealth` mode:

```powershell
.\scripts\install-scrapling-browsers.ps1
```

Start backend:

```powershell
.\scripts\dev-backend.ps1
```

Backend URL:

```text
http://127.0.0.1:8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

API docs:

```text
http://127.0.0.1:8000/docs
```

## Frontend Setup

Install dependencies:

```powershell
Set-Location frontend\react-chat
npm install
```

Start frontend:

```powershell
.\scripts\dev-frontend.ps1
```

Frontend URL:

```text
http://localhost:5173
```

The Vite dev server proxies `/api/*` requests to `http://127.0.0.1:8000`.

## Main API Endpoints

```text
GET  /health
POST /api/runs
GET  /api/runs
GET  /api/runs/{run_id}
GET  /api/model-health
GET  /api/crawls/capabilities
POST /api/crawls
GET  /api/crawls
GET  /api/crawls/{job_id}
POST /api/crawls/{job_id}/retry
POST /api/knowledge/documents
GET  /api/knowledge/documents
POST /api/knowledge/search
POST /api/knowledge/reindex
```

## Site Crawler Control Plane

The default ingestion experience manages mature website-specific crawlers instead
of trying to infer authenticated download flows from CSS selectors. The initial
adapters reuse the existing `zxxk-scrapling` and `youtike-scrapling` projects,
including their login sessions, source-id/file-hash deduplication, archive
extraction, OSS upload, and business database import.

Configure their project roots in `backend/.env`:

```env
ZXXK_CRAWLER_ROOT=D:/crawlers/zxxk-scrapling
YOUTIKE_CRAWLER_ROOT=D:/crawlers/youtike-scrapling
```

Control-plane APIs:

```text
GET  /api/site-crawlers
POST /api/site-crawler-tasks
GET  /api/site-crawler-tasks
GET  /api/site-crawler-tasks/{task_id}
GET  /api/site-crawler-tasks/{task_id}/logs
POST /api/site-crawler-tasks/{task_id}/retry
POST /api/site-crawler-tasks/{task_id}/cancel
```

Tasks and UTF-8 logs are persisted in SQLite. Transient network failures use
bounded exponential-backoff retries. Authentication, verification/WAF, and quota
conditions pause instead of repeatedly hitting the website. Backend restarts
convert active tasks to paused tasks so an operator can recover them explicitly.

New website-specific crawlers implement the command contract documented in
`backend/site_crawler_manifests/README.md`, then register through a trusted JSON
manifest. Manifests are administrator-controlled because they authorize a local
executable; they are not accepted from the public web UI.

## Generic Crawl Ingestion

Open the frontend and select `Data ingestion`. The control plane can edit:

- Start URLs and allowed domains.
- No-code collection type: page content, files, images, or custom structured data.
- File categories: documents, spreadsheets, presentations, and archives.
- Optional file/image description matched against link text, filenames, metadata, and URLs.
- Automatic pagination for common next-page and pagination links.
- HTTP, dynamic-browser, or stealth fetch mode.
- Page/item CSS or XPath selectors.
- Adaptive extraction fields and multi-value fields.
- Link-following selector, page limit, concurrency, delay, and robots.txt behavior.
- Local output directory below the configured storage root.
- OSS bucket alias and object prefix.
- MySQL destination table.

Local, OSS, and MySQL are independent switches and can be combined. Example API request using only local storage:

```powershell
$body = @{
  name = "documentation-crawl"
  start_urls = @("https://example.com/docs")
  item_selector = "article"
  follow_selector = "a.next::attr(href)"
  fields = @(
    @{ name = "title"; selector = "h1::text"; required = $true }
    @{ name = "content"; selector = "p::text"; multiple = $true }
  )
  asset_downloads = @{
    enabled = $false
    selector = "a[href]"
    url_attributes = @("href")
    description = "只爬安徽省的试卷"
    extensions = @("pdf", "docx", "xlsx", "zip")
    max_assets = 200
  }
  fetch_mode = "http"
  max_pages = 100
  robots_txt_obey = $true
  destinations = @{
    local = @{
      enabled = $true
      directory = "documentation"
      save_html = $true
      save_json = $true
    }
    oss = @{ enabled = $false }
    mysql = @{ enabled = $false }
  }
} | ConvertTo-Json -Depth 8

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/crawls `
  -ContentType "application/json" `
  -Body $body
```

Local paths are relative to `CRAWL_LOCAL_STORAGE_DIR`; absolute paths and parent-directory traversal are rejected. Local artifacts use a Windows-safe, content-addressed layout:

```text
{local_root}/{directory}/{YYYYMMDD}/{crawl_job_id}/{content_hash_32}/raw.html
{local_root}/{directory}/{YYYYMMDD}/{crawl_job_id}/{content_hash_32}/data.json
```

The MySQL sink creates its destination table if it does not exist. The configured database user therefore needs `CREATE`, `INSERT`, and `UPDATE` permissions for that table. Records are upserted by crawl-job and record hash.

OSS object keys are content-addressed:

```text
{prefix}/{YYYY}/{MM}/{DD}/{crawl_job_id}/{hash_prefix}/{content_hash}/raw.html
{prefix}/{YYYY}/{MM}/{DD}/{crawl_job_id}/{hash_prefix}/{content_hash}/data.json
```

Each page and destination attempt is also recorded in local SQLite. Retrying a failed or interrupted job skips successful deliveries and resumes from the Scrapling checkpoint.

File and image presets schedule matching links as additional Scrapling requests. Only URLs on the crawl's allowed domains and with explicitly allowed extensions are downloaded. The default maximum is 200 assets per job and 100 MiB per asset. Downloaded binaries keep a sanitized original filename and use the same local/OSS/MySQL delivery audit as page artifacts.

## Workflows

Supported workflow names:

```text
default_chat_workflow
task_planning_workflow
rag_workflow
```

Example request:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/runs `
  -ContentType "application/json" `
  -Body '{"input":"What is our Project Atlas release policy?","workflow_name":"rag_workflow"}'
```

## Quality Gate

Run the local quality gate:

```powershell
.\scripts\run-quality-gate.ps1
```

This runs:

```text
pytest tests
python -m app.evals.run_rag_answer_eval --ci-mode --min-pass-rate 1.0 --no-save-report
npm run lint
npm run build
```

The GitHub Actions workflow runs the same checks on push to `main` or `master`, and on pull requests.

## RAG Evaluation

Golden set:

```text
backend/app/evals/golden_sets/rag_answer_golden_set.json
```

Eval corpus:

```text
backend/app/evals/golden_sets/rag_eval_corpus.json
```

Run offline deterministic eval:

```powershell
$env:PYTHONPATH = "$PWD\backend"
Set-Location backend
python -m app.evals.run_rag_answer_eval --ci-mode --min-pass-rate 1.0 --no-save-report
```

Run eval against current database and configured model:

```powershell
$env:PYTHONPATH = "$PWD\backend"
Set-Location backend
python -m app.evals.run_rag_answer_eval --use-current-db
```

## Data and Secrets

Ignored local runtime files:

```text
backend/.env
backend/data/*.sqlite3
backend/app/evals/reports/*.json
```

Never commit real API keys or local SQLite databases.

## Current Architecture

```text
React UI
  -> /api/runs
FastAPI routes
  -> RunService
Workflow registry
  -> default chat / task planning / RAG workflow
Model Gateway
  -> model router
  -> circuit breaker
  -> mock / DeepSeek / OpenAI provider
SQLite repositories
  -> runs, steps, traces, model calls, tool calls, documents, chunks, embeddings
Scrapling crawl control
  -> scheduler / sessions / robots.txt / checkpoint / adaptive selectors
  -> local delivery audit
  -> local HTML and JSON artifacts
  -> Alibaba Cloud OSS artifacts
  -> MySQL structured records
Evaluation harness
  -> golden set
  -> offline deterministic CI mode
  -> pass/fail quality gate
```

## Production Notes

This project is intentionally local-first. Before production deployment, add:

- Authentication and authorization.
- Tenant isolation.
- Request rate limits.
- A distributed background queue and worker pool for multi-instance crawl execution.
- Managed database instead of local SQLite.
- Secrets manager integration.
- Structured logging export.
- Deployment manifests for the chosen platform.
