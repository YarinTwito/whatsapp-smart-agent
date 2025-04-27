# 📄 WhatsApp PDF Assistant 🤖

A cloud-hosted **WhatsApp agent** that lets users upload PDFs and then query, summarise or explore them with an LLM – all from chat.

| Tech | Role |
|------|------|
| **FastAPI + SQLModel** | REST API & lightweight DB (SQLite) |
| **Twilio WhatsApp Business** | Receive messages / send replies |
| **OpenAI API + LangChain** | Embeddings, chat completions, semantic search |
| **LangGraph-Platform / LangSmith** | Visual debug graph & tracing |
| **Azure App Service** | Deploy app & serve traffic |
| **GitHub Actions** | CI/CD – lint, tests, Docker build & push |

---

## ⚡ Quick-start (local, 90 seconds)

```bash
# 1 – Install deps & drop into virtual-env
poetry install && poetry shell

# 2 – Run API (hot-reload)
poetry run uvicorn run:app --reload
#      ➜  http://localhost:8000/health  →  {"status":"healthy"}

# 3 – Expose webhook for Twilio Sandbox
ngrok http 8000
#      copy the https URL → Twilio Sandbox → "WHEN A MESSAGE COMES IN"
```

---

## 🐳 Docker

```bash
# Build image
docker build -t whatsapp-pdf-assistant .

# Run container
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-… \
  -e TWILIO_ACCOUNT_SID=AC… \
  -e TWILIO_AUTH_TOKEN=… \
  -e TWILIO_PHONE_NUMBER=whatsapp:+1234567890 \
  whatsapp-pdf-assistant
```

---

## ⚙️ Configuration (`.env`)

| Key | Example / Default | Description |
|-----|-------------------|-------------|
| **Database** | | |
| `DATABASE_URL` | `sqlite:///./pdf_assistant.db` | SQLModel connection |
| `UPLOAD_DIR` | `uploads` | Local storage for PDFs/images |
| **OpenAI / LangChain** | | |
| `OPENAI_API_KEY` | — | OpenAI credentials |
| `LANGCHAIN_API_KEY` | — | Optional, enables LangSmith tracing |
| **Twilio WhatsApp** | | |
| `TWILIO_ACCOUNT_SID` | — | Twilio credentials |
| `TWILIO_AUTH_TOKEN` | — | ″ |
| `TWILIO_PHONE_NUMBER` | `whatsapp:+1234567890` | WhatsApp-enabled number |
| **Admin** | | |
| `ADMIN_API_KEY` | `admin_secret_key` | Token for `/admin/*` routes |

---

## 📑 HTTP Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | Liveness probe |
| POST | `/webhook` | Twilio webhook receiver |
| POST | `/upload-pdf` | (Optional) REST upload |
| GET  | `/admin/feedback?api_key=…` | List user feedback |
| GET  | `/admin/reports?api_key=…` | List bug reports |
| PUT  | `/admin/reports/{id}/status?api_key=…&status=resolved` | Update bug status |

---

## 💬 WhatsApp User Commands

| Command | Action |
|---------|--------|
| `/help` | Show all commands |
| `/list` | List uploaded PDFs |
| `/select <n>` | Pick PDF number `n` |
| `/delete <n>` | Delete one PDF |
| `/delete_all` | Wipe all PDFs |
| `/report` | Start bug-report flow |
| *(any other text)* | Ask about the selected / latest PDF |

---

## 🧪 Tests & Checks

```bash
poetry run pytest --cov=app --cov-report=term   # unit tests + coverage
./scripts/check.sh                              # black + isort + flake8 + mypy
```

---

## 📈 CI / CD

| Workflow file | What it does |
|---------------|--------------|
| `.github/workflows/ci.yml` | Lint + tests on every push / PR |
| `.github/workflows/main_pdf-assistant.yml` | Build & push Docker image (adjust registry) |

Disable a workflow temporarily via *Actions → Workflow → “Disable”*.

---

## 📱 Try it live

The agent is running on WhatsApp: **+1 (438) 813-5945**  
Send it a PDF and see what it can tell you!