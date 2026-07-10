# BuildLens AI — Project Specification

## Overview

BuildLens AI is an internal developer platform that ingests CI/CD test run data, parses failure logs, performs AI-powered failure triage using embeddings and an LLM, finds similar historical failures, and generates actionable issue drafts.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+ / FastAPI |
| Database | PostgreSQL 16 with pgvector |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| Frontend | Next.js 14+ (App Router) / TypeScript / Tailwind CSS |
| AI | OpenAI API (GPT-4o-mini, text-embedding-3-small) |
| Containerization | Docker + Docker Compose |
| Testing | pytest |
| CI Demo | GitHub Actions |

## Functionality Specification

### Core Features

#### 1. CI Run Ingestion (POST /api/runs/ingest)
- Accept JSON payload: repo_name, branch, commit_sha, pipeline_id, environment, status, test_suite_name, failed_test_names (list), raw_log_text, timestamp
- Validate all fields with Pydantic
- Parse raw log text with LogParser service to extract structured failure data
- Generate embeddings for the cleaned log representation
- Store CIRun, FailureLog, and embedding vectors in DB
- Return created CI run with ID

#### 2. CI Run Listing (GET /api/runs)
- Return paginated list of CI runs (default 20 per page)
- Fields: id, repo_name, branch, commit_sha, environment, status, test_suite_name, timestamp, triage_status, failure_category
- Support query filters: status (passed/failed), repo_name, environment

#### 3. CI Run Detail (GET /api/runs/{id})
- Return full CI run with embedded FailureLog, TriageResult, and SimilarFailures
- Include parsed log data, triage classification, and AI summary

#### 4. AI Triage (POST /api/runs/{id}/triage)
- Run only on failed CI runs
- Use LogParser output + failure metadata as prompt context
- Call LLM to classify failure category (8 categories)
- Generate: summary, root_cause, suggested_steps, confidence_score, owner_guess, issue_title, issue_body
- Store result in TriageResult table
- Return triage result

#### 5. Similar Failure Search (GET /api/runs/{id}/similar)
- Generate embedding for current failure log
- Query pgvector for top-5 nearest neighbors (filtered to same repo, exclude current)
- Return: similar_run_id, similarity_score, old_root_cause, old_resolution, commit_metadata
- Requires run to have triage result or at least a failure log

#### 6. Issue Draft Generation (POST /api/runs/{id}/issue-draft)
- Use triage result + similar failures to construct full GitHub issue
- Format: title, body (markdown), labels, assignee guess
- Store in IssueDraft table
- Return draft (user can copy/paste to GitHub/Jira)

#### 7. Health Check (GET /api/health)
- Check DB connectivity
- Check LLM API connectivity
- Return: status, database, llm

### Database Models

#### CIRun
- id (UUID, PK)
- repo_name (VARCHAR 255)
- branch (VARCHAR 255)
- commit_sha (VARCHAR 64)
- pipeline_id (VARCHAR 255)
- environment (VARCHAR 100)
- status (ENUM: passed, failed, skipped)
- test_suite_name (VARCHAR 255)
- failed_test_names (JSONB array)
- timestamp (DATETIME)
- created_at (DATETIME)
- updated_at (DATETIME)
- Relationships: failure_log (1:1), triage_result (1:1), issue_draft (1:1)

#### FailureLog
- id (UUID, PK)
- ci_run_id (UUID, FK -> CIRun, unique)
- raw_log_text (TEXT)
- cleaned_log_text (TEXT)
- extracted_errors (JSONB)
- stack_traces (JSONB array)
- exception_names (JSONB array)
- failed_tests (JSONB array)
- timeout_indicators (BOOLEAN)
- dependency_errors (JSONB array)
- infrastructure_errors (JSONB array)
- embedding (VECTOR(1536))
- created_at (DATETIME)
- Relationships: ci_run (1:1 backref)

#### TriageResult
- id (UUID, PK)
- ci_run_id (UUID, FK -> CIRun, unique)
- failure_category (ENUM: test_assertion_failure, application_code_bug, flaky_test, dependency_configuration_issue, infrastructure_environment_failure, timeout_performance_issue, unknown)
- summary (TEXT)
- root_cause (TEXT)
- suggested_steps (JSONB array)
- confidence_score (FLOAT 0-1)
- owner_guess (VARCHAR 255)
- issue_title (VARCHAR 500)
- issue_body (TEXT)
- model_used (VARCHAR 100)
- created_at (DATETIME)
- Relationships: ci_run (1:1 backref)

#### IssueDraft
- id (UUID, PK)
- ci_run_id (UUID, FK -> CIRun, unique)
- title (VARCHAR 500)
- body (TEXT)
- labels (JSONB array)
- assignee_guess (VARCHAR 255)
- format (ENUM: github, jira)
- created_at (DATETIME)
- Relationships: ci_run (1:1 backref)

### Log Parser Specification

The LogParser service must extract:
1. **Stack traces** — lines following Python/Java/JS error patterns (look for `File`, `raise`, `Error:`, `Exception:`)
2. **Exception names** — class names in traceback (e.g., `AssertionError`, `ValueError`, `ConnectionRefusedError`)
3. **Failed tests** — lines matching pytest assertion patterns, JUnit failures, test framework output
4. **Timeout indicators** — keywords: "timeout", "timed out", "took too long", "deadline exceeded"
5. **Dependency errors** — keywords: "ImportError", "ModuleNotFoundError", "No module named", "dependency", "version mismatch"
6. **Infrastructure errors** — keywords: "connection refused", "out of memory", "disk full", "network error", "503", "502"

Output: structured JSON with extracted data + cleaned log text (noise removed, relevant lines kept)

### AI Triage Prompt Strategy

System prompt: Role = "Senior SRE / DevOps engineer with deep CI/CD debugging experience"

User prompt includes:
- Extracted error patterns from log parser
- Failed test names
- Exception names
- Stack trace excerpt (first 2000 chars)
- Previous triage context if available

Expected output: JSON with structured fields (validated via Pydantic)

### Failure Categories

1. `test_assertion_failure` — Test code bug or assertion mismatch
2. `application_code_bug` — Product code bug exposed by tests
3. `flaky_test` — Non-deterministic test behavior
4. `dependency_configuration_issue` — Library version mismatch, config error
5. `infrastructure_environment_failure` — Env issues (DB, cache, network)
6. `timeout_performance_issue` — Slow tests, resource exhaustion
7. `unknown` — Cannot determine from available data

## Acceptance Criteria

- [ ] `POST /api/runs/ingest` stores a CI run and returns it with ID
- [ ] `GET /api/runs` returns paginated list with correct filters
- [ ] `GET /api/runs/{id}` returns full run data with related records
- [ ] Log parser extracts at least: exception names, stack traces, failed tests, timeout indicators
- [ ] `POST /api/runs/{id}/triage` returns a classified failure with confidence score
- [ ] `GET /api/runs/{id}/similar` returns top-5 similar runs with scores
- [ ] `POST /api/runs/{id}/issue-draft` generates a valid GitHub-format markdown draft
- [ ] `GET /api/health` returns status of all dependencies
- [ ] Frontend dashboard displays runs list with status badges
- [ ] Frontend run detail page shows triage results and similar failures
- [ ] Docker Compose brings up full stack successfully
- [ ] Alembic migrations create all tables including pgvector extension
- [ ] pytest tests pass for log parser and triage helpers
- [ ] Seed data script populates DB with demo data
- [ ] Example project has a GitHub Actions workflow that calls ingestion API