# AI-Powered Pull Request Reviewer

An event-driven, multi-agent AI code-review system that receives GitHub pull-request webhooks, guarantees idempotent processing, injects semantic repository context (RAG), and utilizes a LangGraph orchestrated multi-agent pipeline to publish structured feedback back to GitHub.

> **Project status:** Independent engineering project / prototype. It is not presented as a production deployment or enterprise adoption case study, but serves as a rigorous exploration of local LLM constraints.

## Problem

Building a reliable AI reviewer creates several complex engineering challenges:

1. **Context Limits & Blindness:** Raw diffs can exceed model context budgets, and without historical codebase knowledge, AI models hallucinate or misinterpret changes.
2. **Webhook Redelivery:** GitHub webhooks can be delivered multiple times. Processing them statelessly results in duplicate PR reviews and API spam.
3. **Cognitive Overload (Sycophancy):** Forcing a local 8B parameter model to act as a Security, Performance, and Style expert simultaneously causes extreme hallucination and degraded accuracy.

The project focuses on solving these boundaries locally rather than simply sending an entire PR to a cloud LLM.

## Architecture

```text
GitHub Pull Request
        |
        | HTTPS webhook
        v
+-------------------------+
| FastAPI Webhook Gateway |
| HMAC-SHA256 validation  |
+------------+------------+
             |
             v
+-------------------------+
| Idempotency Layer       |
| PostgreSQL Audit Ledger |
+------------+------------+
             |
             v
+-------------------------+
| Semantic Memory (RAG)   |
| pgvector & fastembed    |
| Context construction    |
+------------+------------+
             |
             v
+-------------------------+
| LangGraph Orchestration |
| Security Agent          |
| Performance Agent       |
| Style Agent             |
| Aggregator Agent        |
+------------+------------+
             |
             v
+-------------------------+
| Fast Regex Parser       |
| Markdown -> Pydantic    |
+------------+------------+
             |
             v
      GitHub Pull Request
```

## Workflow

1. GitHub sends a pull-request webhook.
2. The API verifies `X-Hub-Signature-256`.
3. PostgreSQL checks the Webhook Audit Ledger to guarantee **idempotent execution** (preventing duplicate processing).
4. The service retrieves the unified diff from GitHub.
5. `pgvector` performs a semantic search against the historical codebase, filtering out irrelevant files using Cosine Distance (`< 0.5`).
6. LangGraph orchestrates the task, sending the diff to specialized agents (Security, Performance, Style).
7. The Aggregator Agent deduplicates findings.
8. The raw Markdown output is parsed via fast Regex back into structured Pydantic models.
9. Review feedback is sent back to the pull request.

## Why memory and chunking matter

Passing an entire multi-file diff directly to a model becomes unreliable as repositories grow, and reviewing a diff without understanding the broader project architecture leads to false positives.

The processing layer therefore:
- guarantees exactly-once webhook processing via PostgreSQL.
- semantically searches the historical repository to inject architectural context (RAG).
- strictly bounds RAG context to prevent model confusion.
- utilizes Regex plain-text parsing to drastically reduce token overhead on local models.

This makes context engineering a first-class part of the AI application.

## Security boundary

```text
GitHub webhook
      |
      v
HMAC-SHA256 verification
      |
      +---- invalid ----> 401
      |
      v
Idempotent Audit Ledger (PostgreSQL)
      |
      v
AI processing
```

GitHub App authentication is also used for secure GitHub API communication.

## AI application design

```text
External event
      ↓
Deterministic context construction (pgvector RAG)
      ↓
Agentic Task Routing (LangGraph)
      ↓
LLM reasoning (Ollama / Local 8B)
      ↓
Regex Parsing & Aggregation
      ↓
GitHub API
```

The model reasons about code; deterministic application logic handles webhook validation, deduplication, context injection, and API integration.

## Stateful processing

Unlike simple stateless prototypes, this architecture recognizes that reliable webhook processing requires state. **PostgreSQL** is utilized as an Audit Ledger to track `webhook_id` and delivery states, ensuring that network retries from GitHub do not result in duplicate PR comments.

## Engineering decisions

### FastAPI
An asynchronous ASGI service perfectly fits the I/O-heavy webhook → Database → LLM → GitHub API workflow.

### PostgreSQL & pgvector
Added to solve the two biggest flaws in stateless AI apps: duplicate webhook execution (solved via relational audit ledgers) and AI codebase blindness (solved via semantic vector search).

### Multi-Agent Orchestration (LangGraph)
Local 8B models suffer from cognitive overload when asked to do too much. LangGraph was chosen to split the prompt into highly specialized tasks, allowing the model to focus purely on Security, or purely on Performance, in isolated sequential executions.

### Regex & Markdown vs. JSON Schemas
Initially, strict Pydantic JSON validation (`instructor`) was used. However, injecting heavy JSON schemas into an 8B model's prompt caused extreme GPU spikes (47-minute execution times) and hallucination loops. Ripping out JSON in favor of raw Markdown and Regex parsing dropped execution time to under 3 minutes.

## Failure modes and trade-offs

### The 8B Model Limitation (Sycophancy)
Small instruction-tuned models are trained to be "helpful." When instructed to find bugs, they feel intense pressure to invent them (e.g., hallucinating SQL injections in safe code). 
**Trade-off:** We traded cloud API costs for local privacy, but hit the physical intelligence ceiling of 8B parameters. 

**Possible next step:** Plug in a 70B+ model (Groq/Anthropic) to immediately cure sycophancy and achieve enterprise accuracy.

## Validation

The application includes deterministic controls around the AI workflow, as well as a rigorous **Automated LLM Evaluation Pipeline**:

- 20-scenario mathematical grading suite (`scripts/run_evals.py`).
- webhook signature validation.
- Idempotency database locking.
- Token-bounded RAG thresholding.

*Note: Evaluation tests on a local 8B model yielded a 20% accuracy score due to sycophancy, proving the necessity of larger models for broad-domain review.*

## Production considerations

A true production version would need durable message queues (Celery/RabbitMQ) for burst handling, provider fallback, concurrency limits, repository authorization, secret rotation, and structured observability.

## What I learned

An LLM code-review system is largely a **context-engineering and systems-integration problem**. However, the ultimate lesson is in **Model Capability vs. Prompt Engineering**: No amount of architecture (RAG, CoT, Multi-Agent routing) can force an 8B parameter model to reliably act as an expert software engineer across broad domains. High-accuracy code review strictly requires the semantic depth of a 70B+ model.

## Status

Independent prototype exploring event-driven AI application architecture, secure webhook ingestion, Idempotent PostgreSQL ledgers, `pgvector` codebase memory, LangGraph orchestration, and the strict physical limitations of local LLMs.

## Links

- GitHub: https://github.com/Reh1t/AI-Powered_PR_Reviewer
- LinkedIn: https://www.linkedin.com/in/rehantariqbhatti
