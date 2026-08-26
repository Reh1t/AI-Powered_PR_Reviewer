# AI-Powered Pull Request Reviewer

An event-driven AI code-review prototype that receives GitHub pull-request webhooks, validates the event, retrieves the unified diff, chunks large changes into model-sized inputs, sends relevant context to an LLM review layer, and publishes structured feedback back to GitHub.

> **Project status:** Independent engineering project / prototype. It is not presented as a production deployment or enterprise adoption case study.

## Problem

Large pull requests create two problems for LLM-based review:

1. Raw diffs can exceed model context budgets.
2. Webhook endpoints must not trust arbitrary external requests.

The project focuses on those boundaries rather than simply sending an entire PR to an LLM.

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
| Payload / Schema Layer  |
| Pydantic validation     |
+------------+------------+
             |
             v
+-------------------------+
| Git Diff Retrieval      |
| GitHub App auth         |
+------------+------------+
             |
             v
+-------------------------+
| Diff Processing         |
| file boundaries         |
| hunk parsing            |
| filtering / chunking    |
+------------+------------+
             |
             v
+-------------------------+
| AI Review Engine        |
| security / style /     |
| architecture analysis   |
+------------+------------+
             |
             v
+-------------------------+
| Structured Review       |
| Markdown / JSON         |
+------------+------------+
             |
             v
      GitHub Pull Request
```

## Workflow

1. GitHub sends a pull-request webhook.
2. The API verifies `X-Hub-Signature-256`.
3. Pydantic models validate and normalize the payload.
4. Relevant actions such as `opened` and `synchronize` continue.
5. The service retrieves the unified diff from GitHub.
6. The diff is separated into file/hunk-level chunks and bounded for LLM context.
7. The AI review layer analyzes security, performance, style, and architectural concerns.
8. Review feedback is sent back to the pull request.

## Why diff processing matters

Passing an entire multi-file diff directly to a model becomes unreliable as repositories grow.

The processing layer therefore:

- separates changes by file
- parses unified-diff structure
- filters unsuitable/generated content
- keeps chunks within a token budget
- preserves useful surrounding context

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
Payload validation
      |
      v
AI processing
```

GitHub App authentication is also used for GitHub API communication.

## AI application design

```text
External event
      ↓
Deterministic parsing
      ↓
Deterministic context construction
      ↓
LLM reasoning
      ↓
Structured application output
      ↓
GitHub API
```

The model reasons about code; deterministic application logic handles webhook validation, diff parsing, context construction, and API integration.

## Stateless processing

The intended model is ephemeral: repository diffs are processed without an application database, while GitHub remains the system of record for PR state.

## Engineering decisions

### FastAPI

An asynchronous ASGI service fits the I/O-heavy webhook → GitHub API → LLM → GitHub API workflow.

### Deterministic diff parsing

The LLM should reason about code, not decide how a Git diff should be split. Parsing and chunking are deterministic preprocessing steps.

### No persistent application database

For this prototype, PR state already exists in GitHub. Adding another database would introduce state without being necessary for the core experiment.

### Lightweight async processing

The current project deliberately keeps infrastructure small. A durable queue becomes more appropriate as event volume and retry requirements grow.

## Failure modes and trade-offs

### Very large diffs

Generated files, lockfiles, or very large changes can make review expensive or exceed useful context limits.

**Possible next step:** stronger filtering and parallel per-file review with aggregation.

### LLM provider failure

The application depends on external model APIs.

**Possible next step:** provider fallback, durable retry queues, and explicit review-state tracking.

### Webhook bursts

The lightweight async architecture is not intended to replace a distributed durable queue.

**Possible next step:** introduce queue-backed workers when throughput requires it.

## Validation

The application includes deterministic controls around the AI workflow:

- webhook signature validation
- Pydantic schema validation
- token-bounded diff processing
- structured review payload handling
- GitHub review API integration

Performance figures in the original project should be treated as prototype measurements/targets rather than production SLAs unless independently benchmarked.

## Production considerations

A production version would need durable webhook queues, retry/dead-letter handling, provider fallback, concurrency limits, repository authorization, secret rotation, structured observability, cost controls, review-quality evaluation, and explicit privacy/compliance controls.

## What I learned

An LLM code-review system is largely a **context-engineering and systems-integration problem**. Reliable behavior depends on validating events, constructing useful code context, bounding inputs, enforcing output structure, and integrating results safely with GitHub.

## Status

Independent prototype exploring event-driven AI application architecture, secure webhook ingestion, deterministic context construction, and LLM-assisted code review.

## Links

- GitHub: https://github.com/Reh1t/AI-Powered_PR_Reviewer
- LinkedIn: https://www.linkedin.com/in/rehantariqbhatti
