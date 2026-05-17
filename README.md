# 🛡️ AI-Powered PR Reviewer: Enterprise-Grade AppSec Bot

An autonomous, agentic code reviewer engineered to act as a virtual **Senior Application Security Engineer**. This system intercepts Pull Requests in real-time via GitHub Webhooks, analyzes code changes using high-speed LLMs (Llama 3.3 via Groq), and publishes context-aware, batched reviews directly to GitHub.

---

## 🚀 Key Features

- **⚡ Instant Feedback:** Powered by Groq for sub-second token generation.
- **🛡️ Security Focused:** Specifically trained to hunt for the OWASP Top 10 (SQLi, XSS, Hardcoded Secrets, etc.).
- **🤖 Structured Reasoning:** Uses Pydantic and `instructor` to enforce mathematical JSON compliance, eliminating AI hallucinations.
- **📦 Batched Reviews:** Groups all findings into a single, professional GitHub Review to avoid notification fatigue.
- **🔐 Cryptographic Security:** Validates every incoming request using HMAC SHA-256 signature verification.

---

## 🛠️ Technology Stack

- **Backend:** FastAPI (Python 3.13+)
- **AI Engine:** Groq (Llama-3.3-70b-versatile)
- **Validation:** Pydantic / Instructor
- **Auth:** GitHub App (JWT & RSA)
- **Networking:** HTTPX (Async)
- **Security:** HMAC, Hashlib

---

## 📋 Prerequisites

- **Python 3.11+**
- **ngrok** (for local testing)
- **Groq API Key**
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

# AI Engine
LLM_API_KEY="gsk_your_groq_key"
LLM_MODEL_NAME="llama-3.3-70b-versatile"
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
