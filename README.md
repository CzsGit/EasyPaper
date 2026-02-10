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
- HTML preview + PDF download
- Self-hosted, runs locally with your own LLM API key

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- An LLM API key (e.g. OpenRouter, or any OpenAI-compatible API)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set up config
cp config/config.example.yaml config/config.yaml
# Edit config.yaml — add your API key and choose your model

uvicorn app.main:app --reload
```

### Frontend

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
  api_key: "YOUR_API_KEY"        # Your LLM API key
  base_url: "https://api.xxx.com/v1"  # API endpoint
  model: "gemini-2.5-flash"      # Model for processing
  judge_model: "gemini-2.5-flash"
processing:
  max_pages: 100
  preview_html: true
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI, PyMuPDF, ReportLab, pdf2zh |
| Frontend | React, TypeScript, Vite, Tailwind CSS, Radix UI |
| Database | SQLite (default) |

## License

MIT
