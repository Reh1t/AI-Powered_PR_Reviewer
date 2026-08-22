# AI-Powered Pull Request Reviewer: Automated Event-Driven Code Governance Pipeline



# Introduction & Goals



This project delivers an event-driven code analysis and governance pipeline that automates pull request reviews for GitHub repositories. Operating on live webhook payloads and multi-file Git diffs, the system intercepts GitHub pull request events, extracts patch metadata, batches and parses token-bounded code chunks, and routes structured payloads to OpenAI/Anthropic LLMs for security, style, and architectural audit. Structured Markdown feedback containing line-level review comments is then posted back into the pull request discussion thread via authenticated GitHub App REST/GraphQL endpoints.

The pipeline eliminates manual review latency for boilerplate syntax and vulnerability scanning, enforcing continuous quality and security compliance before human review.

**Goal 1:** Validate, parse, and review pull requests upon code submission without manual developer invocation.

**How I know it worked:** GitHub webhook `pull_request.opened` and `pull_request.synchronize` events are processed with structured review comments posted back to the PR within **15 seconds** of event dispatch.

**Goal 2:** Prevent context window overflows and payload truncation across multi-file pull requests.

**How I know it worked:** 100% of pull requests containing diffs up to **4,000 lines of code** or **32,000 tokens** are deterministically chunked and reviewed without runtime payload errors.

**Goal 3:** Secure the ingestion interface against forged or malicious third-party events.

**How I know it worked:** 100% of incoming HTTP requests fail with an immediate **HTTP 401 Unauthorized** response if the `X-Hub-Signature-256` HMAC digest fails validation.

## Architecture



```
                       +-----------------------------+
                       |      GitHub Repository      |
                       |  (PR Open / Synchronize)    |
                       +--------------+--------------+
                                      |
                                      | Webhook Event (HTTPS POST + HMAC-SHA256)
                                      v
                       +-----------------------------+
                       |       FastAPI Gateway       |
                       | (Signature & Auth Validation)|
                       +--------------+--------------+
                                      |
                                      | Async Task Delegation
                                      v
                       +-----------------------------+
                       |     Diff Processing Unit    |
                       | (Diff Extraction & Chunking)|
                       +--------------+--------------+
                                      |
                                      | Clean Chunk / Unified Diff Buffer
                                      v
                       +-----------------------------+
                       |     AI Reviewer Engine      |
                       |  (Structured Prompt & LLM)  |
                       +--------------+--------------+
                                      |
                                      | Structured Review Payload (JSON / Markdown)
                                      v
                       +-----------------------------+
                       |     GitHub REST Service     |
                       |  (Installation Token Auth)  |
                       +--------------+--------------+
                                      |
                                      | POST /pulls/{id}/reviews
                                      v
                       +-----------------------------+
                       |   GitHub Pull Request UI    |
                       |   (Inline Code Comments)    |
                       +-----------------------------+

```

---

# Contents



* [The Data Set](https://www.google.com/search?q=%23the-data-set)

* [Constraints](https://www.google.com/search?q=%23constraints)

* [Used Tools](https://www.google.com/search?q=%23used-tools)

* [Connect](https://www.google.com/search?q=%23connect)

* [Buffer](https://www.google.com/search?q=%23buffer)

* [Processing](https://www.google.com/search?q=%23processing)

* [Storage](https://www.google.com/search?q=%23storage)

* [Visualization](https://www.google.com/search?q=%23visualization)



* [Pipelines](https://www.google.com/search?q=%23pipelines)

* [Stream Processing](https://www.google.com/search?q=%23stream-processing)

* [Storing Data Stream](https://www.google.com/search?q=%23storing-data-stream)

* [Processing Data Stream](https://www.google.com/search?q=%23processing-data-stream)



* [Batch Processing](https://www.google.com/search?q=%23batch-processing)

* [Visualizations](https://www.google.com/search?q=%23visualizations)



* [Demo](https://www.google.com/search?q=%23demo)

* [What Breaks](https://www.google.com/search?q=%23what-breaks)

* [Conclusion](https://www.google.com/search?q=%23conclusion)

* [Follow Me On](https://www.google.com/search?q=%23follow-me-on)

* [Appendix](https://www.google.com/search?q=%23appendix)


---

# The Data Set



The data processed by this pipeline consists of dynamic, semi-structured Git unified diffs and event-based JSON metadata generated by GitHub pull requests.

* **Why this data:** Git diffs represent the exact atomic changes introduced into a codebase. Inspecting diffs rather than entire repositories minimizes data volume and targets code governance directly where changes occur.


* **What works well:** Diffs provide structured hunk headers (`@@ -start,len +start,len @@`), filename headers, and unified change symbols (`+`, `-`) that map to precise line numbers.


* **What is problematic:** Diffs are unstructured free text within hunk bodies. Large binary blobs, minified build outputs, auto-generated lockfiles, and oversized diffs can easily saturate LLM context windows and exhaust token quotas.


* **Intended transformation:** Normalize raw unified diff text into isolated, file-scoped semantic chunks, filter out ignored file patterns (e.g., lockfiles, binary files), and transform code context into structured vulnerability, optimization, and style assessments.



## How much data is it



An engineering organization with **50 developers** averages **4 pull requests per developer daily**, totaling **200 PRs per day**. Each PR receives an average of **3 commits/updates**, resulting in **600 webhook events per day**.

$$\text{Daily Webhook Payload Data} = 600 \text{ events} \times 25 \text{ KB (JSON Metadata)} = 15.0 \text{ MB/day}$$

$$\text{Daily Raw Git Diff Data} = 600 \text{ events} \times 120 \text{ KB (Average Unified Diff)} = 72.0 \text{ MB/day}$$

$$\text{Total Daily Ingestion Volume} = 15.0 \text{ MB} + 72.0 \text{ MB} = 87.0 \text{ MB/day raw}$$

At an average of **120 KB per diff**, each event corresponds to approximately **30,000 tokens** of raw code and metadata. Over **1 year (250 working days)**, the pipeline processes:

$$\text{Annual Raw Event Ingestion} = 87.0 \text{ MB/day} \times 250 \text{ days} = 21.75 \text{ GB/year}$$

$$\text{Annual LLM Context Throughput} = 600 \text{ diffs/day} \times 30,000 \text{ tokens} \times 250 \text{ days} = 4.5 \times 10^9 \text{ tokens/year}$$

---

# Constraints



* **Budget:** Free tiers and developer credits (GitHub App API free limits, OpenAI/Anthropic pay-per-token credits capped under $20/month).


* **Compute:** Single container runtime / local development daemon (Python 3.11+, Uvicorn/FastAPI worker).


* **Data Outside Direct Control:** GitHub Webhook delivery latency, GitHub REST API rate limits (5,000 requests/hour per installation), and LLM API rate limits (TPM/RPM limits on model inference).


* **Time & Scope:** Strict focus on serverless webhook handling, deterministic hunk parsing, and structured review generation.



---

# Used Tools



## Connect



* **FastAPI (`app/api/webhooks.py`):** Asynchronous ASGI framework handling incoming GitHub HTTP POST webhook events.


* *Why chosen:* Native asynchronous event loop, integrated dependency injection, and high throughput under concurrent HTTP payloads.


* *Rejected:* Flask (synchronous request handling blocks event loop during long-running LLM API roundtrips) and Django (unnecessary ORM and framework overhead for webhook forwarding).




* **HMAC Cryptography Verification (`app/api/dependencies.py`):** Computes HMAC-SHA256 digests over incoming raw request bodies using `X-Hub-Signature-256` headers.



## Buffer



* **In-Memory Async Task Queue / Direct Async Pipeline:** Async execution threads process diff extraction and AI analysis immediately per event dispatch.


* *Why chosen:* Direct async pipelines eliminate Redis/Kafka infrastructure overhead for repositories processing fewer than 10 events per minute.


* *Rejected:* Apache Kafka and RabbitMQ (introduce broker provisioning, partition management, and network maintenance costs unnecessary for single-instance event ingestion).





## Processing



* **Pydantic v2 (`app/schemas/`):** Strict runtime schema validation, deserialization of webhook payloads, and structured JSON output parsing for LLM responses.


* **AI Review Engine (`app/services/ai_reviewer.py`):** Multi-model prompt orchestration with system instructions, diff context injection, and structured markdown comment generation.


* **GitHub Integration Engine (`app/services/github_service.py`):** PyJWT and `httpx` client generating short-lived GitHub App installation tokens, fetching unified diffs, and publishing pull request review comments.



## Storage



* **Stateless Ephemeral Processing:** The pipeline does not store raw repository code or diffs on disk.


* *Why chosen:* Ephemeral stateless processing complies with zero-retention security requirements for proprietary codebases. State is maintained upstream within GitHub's pull request database.


* *Rejected:* PostgreSQL / MongoDB (persisting proprietary source diffs introduces data compliance overhead without operational necessity).





## Visualization



* **GitHub Pull Request Conversation & Files Changed UI:** Consumes review markdown payloads natively via the GitHub Review API, placing contextual line annotations directly where code changes occur.


* **FastAPI Interactive Docs (`/docs`):** Swagger UI for endpoint inspection, manual testing, and health-check monitoring.



---

# Pipelines



## Stream Processing



```
Webhook Event ---> Signature Verification ---> Schema Validation ---> Diff Extraction ---> Semantic Chunking ---> LLM Review Engine ---> GitHub Comment Dispatch

```

The streaming pipeline processes code changes as discrete pull request lifecycle events:

1. **Ingestion & Cryptographic Verification:** Webhook endpoints receive the HTTP payload and evaluate `X-Hub-Signature-256` using constant-time string comparison. If the signature does not match the configured webhook secret, execution terminates immediately.


2. **Payload Parsing:** Pydantic models extract action types (`opened`, `synchronize`), pull request numbers, commit SHAs, repository identifiers, and installation tokens. Irrelevant actions (e.g., `labeled`, `assigned`) return an early `200 OK` without consuming compute resources.


3. **Diff Retrieval & Chunking:** The pipeline queries the GitHub API for the raw unified diff (`Accept: application/vnd.github.v3.diff`), separates changes per file, strips auto-generated assets, and enforces token bounds.


4. **AI Review Generation:** Formatted chunks are evaluated by the AI Review Engine against security rules (OWASP Top 10, SQL injection, secrets leakage), performance antipatterns, and clean code principles.


5. **Dispatch:** Formatted review comments are posted directly to the target pull request via the GitHub REST API (`POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews`).



```python
# Error-handling snippet during webhook ingestion and validation
@router.post("/github")
async def handle_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(...),
    signature: bool = Depends(verify_github_signature)
):
    if not signature:
        logger.error("Unauthorized webhook delivery attempt: invalid HMAC signature")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    
    payload = await request.json()
    if x_github_event == "pull_request" and payload.get("action") in ["opened", "synchronize"]:
        background_tasks.add_task(process_pull_request_review, payload)
        return {"status": "processing_queued", "pr": payload["pull_request"]["number"]}
    
    return {"status": "ignored", "event": x_github_event}

```

### Storing Data Stream



Events are stateless; audit logs are streamed to `stdout` in structured JSON for ingestion by standard observability collectors (e.g., Vector, CloudWatch, Datadog).

### Processing Data Stream



When upstream LLM APIs return `429 Too Many Requests` or network timeouts, the pipeline implements an exponential backoff retry mechanism (initial delay: 2s, factor: 2, max retries: 3). If retries are exhausted, the pipeline fails loudly by posting an error status notice to the PR instead of dropping the review silently.

## Batch Processing



*Not applicable.* The system is designed purely as an event-driven stream processor responding to real-time Git events. Batch backfilling of entire repository histories was intentionally omitted to prevent API quota exhaustion and keep the architecture lean.

## Visualizations



Output is directly consumed in the GitHub Pull Request interface, rendering markdown tables, collapsible details, and inline line-level code suggestions.

---

# Demo



Review the automated review pipeline in action:

```
+-------------------------------------------------------------------------------+
| GitHub Pull Request Review Summary                                            |
|                                                                               |
| [PASSED] Syntax & Standards Check                                             |
| [WARNING] Potential SQL Injection in `app/services/database.py:42`            |
|                                                                               |
| Comment: Parameterized query missing. Direct string interpolation detected.   |
| Suggested fix:                                                                |
| - query = f"SELECT * FROM users WHERE id = '{user_id}'"                       |
| + query = "SELECT * FROM users WHERE id = :user_id"                           |
+-------------------------------------------------------------------------------+

```

*Screenshots and demo recordings can be found under the [`/public`](https://www.google.com/search?q=./public) directory.*[cite: 1, 2]

---

# What Breaks



* **What breaks first (Large Diffs / Monorepos):** When a pull request introduces massive changes (>5,000 lines, such as lockfile updates or generated code), prompt tokens exceed model context limits. The chunking engine will truncate context if file-level chunk thresholds are exceeded.


* *Solution:* Implement strict regex filtering for generated files (`.lock`, `.min.js`, `.generated.ts`) and distribute file diff reviews across parallel asynchronous sub-requests.




* **What was deliberately skipped (External Queue Broker):** Dedicated message brokers (e.g., Redis Celery, RabbitMQ) were skipped to avoid infrastructure complexity. Under a sudden burst of concurrent PR webhooks, server memory will scale linearly with in-flight worker tasks.


* *Why skipped:* For small-to-medium teams, in-memory concurrency handles load reliably without maintaining extra cloud servers.




* **Accepted Risk (LLM Hallucinations & API Outages):** The system relies on third-party AI provider uptime. If the provider API degrades, reviews will fail after retries.


* *Why accepted:* Code reviews are non-blocking advisory checks; developers can always proceed with manual peer reviews if automated feedback is temporarily delayed.




* **Privacy & Compliance:** The application processes source code diffs in transient memory and forwards them over encrypted TLS to LLM providers under zero-data-retention API policies. No source code is persisted to external databases or local disks.



---

# Conclusion



This project demonstrates an industry-grade, event-driven AI workflow built with clean software architecture and security best practices.

Key takeaways:

* Relying strictly on raw webhook payloads is insufficient; separating verification, normalization, chunking, and API dispatch into distinct service layers prevents catastrophic failures on malformed diffs.


* Context engineering and deterministic diff-parsing are far more critical than raw model parameters—structured JSON schemas with strict Pydantic parsing prevent malformed markdown output from corrupting GitHub review comments.


* Designing the pipeline to be fully stateless simplifies operational maintenance, satisfies security and data-governance standards, and avoids persistent storage overhead.



---

# Follow Me On



* **GitHub:** [https://github.com/reh1t](https://github.com/reh1t)

* **LinkedIn:** [https://linkedin.com/in/rehantariqbhatti](https://www.linkedin.com/in/rehantariqbhatti)


---
