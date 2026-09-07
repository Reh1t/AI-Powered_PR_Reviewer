# 🛡️ AI-Powered PR Reviewer: Enterprise-Grade AppSec Bot

> 🚀 **V2 Architecture: Fully Local & Agentic** 🚀
> *This project has been fully upgraded to a multi-agent LangGraph architecture, backed by PostgreSQL for idempotency, `pgvector` for semantic RAG memory, and optimized for local execution via Ollama (Llama 3.1 8B).*

An autonomous, agentic code reviewer engineered to act as a virtual **Senior Application Security Engineer**. This system intercepts Pull Requests in real-time via GitHub Webhooks, analyzes code changes using high-speed LLMs, and publishes context-aware, batched reviews directly to GitHub.

---

## 🚀 Key Features

- **⚡ Fully Local & Private:** Powered by Ollama (`llama3.1-parallel`) to ensure your proprietary code never leaves your machine. (Easily swappable to Groq/OpenAI).
- **🧠 Multi-Agent Orchestration:** Utilizes LangGraph to coordinate specialized agents (Security, Performance, Style) and an Aggregator to deduplicate findings.
- **📚 Codebase-Aware Memory:** Uses `pgvector` and `fastembed` to semantically chunk and inject historical context into the prompt (RAG).
- **🛡️ Idempotent Processing:** Backed by PostgreSQL to guarantee that webhooks are processed exactly once, preventing duplicate PR reviews.
- **📊 Automated Eval Pipeline:** Includes a complete 20-scenario mathematical evaluation suite (`scripts/run_evals.py`) to grade the LLM's accuracy across false positives, security flaws, and style bugs.
- **🔐 Cryptographic Security:** Validates every incoming request using HMAC SHA-256 signature verification.

---

## 🛠️ Technology Stack

- **Backend:** FastAPI (Python 3.13+)
- **Database:** PostgreSQL (with `pgvector` extension) & Alembic
- **Orchestration:** LangGraph (Multi-Agent framework)
- **AI Engine:** Ollama (Llama-3.1 8B) / OpenAI API compatible
- **Embeddings:** `fastembed` (BAAI/bge-small-en-v1.5)
- **Auth:** GitHub App (JWT & RSA)

---

## 📋 Prerequisites

- **Python 3.11+**
- **PostgreSQL** (with `pgvector` extension installed)
- **Ollama** (for local testing with `llama3.1`) or a Groq/OpenAI API key
- **ngrok** (for local webhook testing)
- **GitHub App** (Permissions: `Pull requests: Read/Write`, `Contents: Read-only`)

---

## ⚙️ Installation & Setup

### 1. Clone & Environment
```bash
git clone https://github.com/your-username/ai-powered-pr-reviewer.git
cd ai-powered-pr-reviewer
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Credentials (`.env`)
Create a `.env` file in the root directory:
```bash
# Security
GITHUB_WEBHOOK_SECRET="your_chosen_secret"

# GitHub App
GITHUB_APP_ID="123456"
GITHUB_INSTALLATION_ID="7891011"
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
... (multi-line key content)
-----END RSA PRIVATE KEY-----"

# Database
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/pr_reviewer"

# AI Engine (Local Ollama Example)
OLLAMA_BASE_URL="http://localhost:11434/v1"
LLM_API_KEY="ollama"
LLM_MODEL_NAME="llama3.1-parallel"
```

### 3. Database Migrations
Initialize the PostgreSQL schema and `pgvector` tables:
```bash
alembic upgrade head
```

---

## 🧪 Local Testing Workflow

### 1. Expose Local Server
```bash
ngrok http 8000
```
*Copy the forwarding URL (e.g., `https://a1b2.ngrok-free.app`).*

### 2. Configure GitHub App
- **Webhook URL:** `https://your-url.ngrok-free.app/api/webhook`
- **Webhook Secret:** Must match `.env`.
- **Events:** Subscribe to **"Pull request"**.

### 3. Start the Backend
```bash
uvicorn app.main:app --reload
```

---

## 🌍 Testing on Other Repositories

To test the bot on a different project without modifying this one:

1. **Install the App:** Go to your GitHub App settings → **Install App** → Select the target repository.
2. **Create a Buggy Branch:** In the target repo, push code with an obvious flaw (e.g., `eval(input())` or hardcoded keys).
3. **Open a PR:** Open a Pull Request on the target repo.
4. **Observe:**
   - **ngrok** will show activity.
   - **FastAPI** will log the analysis process.
   - **GitHub** will display the bot's review under the "Conversation" tab.

---

## ✅ Quality Standards
This project maintains strict code quality via:
- **Linting:** `ruff check .`
- **Type Safety:** `mypy .`
- **Security Audit:** `.agent/scripts/checklist.py`

---

## 📄 License
MIT License - See [LICENSE](LICENSE) for details.
