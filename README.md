# EasyPaper

**Make academic papers easy to read.**

EasyPaper is a self-hosted web app that helps you read English academic papers more easily. It can:

- **Translate** English papers into Chinese while preserving layout, images, and formulas
- **Simplify** complex English vocabulary to A2/B1 level (English-to-English rewriting)

Upload a PDF, get back a clean, readable version — with all figures, equations, and formatting intact.

[中文说明](README_zh.md)

## Screenshots

### Translate to Chinese
![Translate to Chinese](imgs/img-0.png)

### Simplify English
![Simplify English](imgs/img-1.png)

### Layout-Preserving Technology
![Layout analysis](imgs/test.png)

## Features

- PDF-in, PDF-out — preserves original layout, images, and mathematical formulas
- English → Chinese translation with formatting retention
- English → Simple English vocabulary simplification (CEFR A2/B1)
- Real-time processing progress tracking
- Side-by-side comparison reader (original vs. processed)
- Drag-and-drop file upload with progress bar
- Task management — search, filter, and delete tasks
- Mobile-responsive reader with focus mode
- JWT authentication with API rate limiting
- Docker support for one-command deployment
- Self-hosted, runs locally with your own LLM API key

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Set up config
cp backend/config/config.example.yaml backend/config/config.yaml
# Edit config.yaml — add your API key and choose your model

docker compose up --build
```

Open http://localhost in your browser.

### Option 2: Local Development

**Prerequisites:** Python 3.10+, Node.js 18+, an LLM API key

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp config/config.example.yaml config/config.yaml
# Edit config.yaml — add your API key and choose your model

uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

## Configuration

Edit `backend/config/config.yaml`:

```yaml
llm:
  api_key: "YOUR_API_KEY"
  base_url: "https://openrouter.ai/api/v1"
  model: "gemini-2.5-flash"
  judge_model: "gemini-2.5-flash"

processing:
  max_pages: 100
  max_upload_mb: 50          # Max upload file size
  max_concurrent: 3          # Max concurrent processing tasks
  preview_html: true

database:
  url: "sqlite:///./data/app.db"

security:
  secret_key: "CHANGE_THIS_TO_A_SECURE_SECRET_KEY"
  cors_origins:
    - "http://localhost:5173"
```

## Development

```bash
# Backend — lint & test
cd backend
ruff check app/ tests/
pytest

# Frontend — lint, type-check & test
cd frontend
npm run lint
npm run type-check
npm test
```

CI runs automatically on push/PR via GitHub Actions.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI, PyMuPDF, ReportLab, pdf2zh |
| Frontend | React, TypeScript, Vite, Tailwind CSS, Radix UI |
| Database | SQLite (via SQLModel + Alembic) |
| DevOps | Docker, GitHub Actions, ruff, ESLint, Prettier |

## License

MIT
