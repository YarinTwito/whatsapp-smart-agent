# WhatsApp PDF Assistant

A WhatsApp chatbot that can analyze PDFs and answer questions using LLMs.

## Features

- Upload and process PDF documents
- Extract text from PDFs
- Generate image previews from PDF pages
- Support for multiple image formats (.jpg, .jpeg, .png, .bmp, .tiff, .gif)

## API Endpoints

- `GET /health` - Health check endpoint
- `GET /` - Root endpoint
- `POST /upload-pdf` - Upload and process PDF files

## Setup

1. Install dependencies:

```bash
poetry install
```

2. Run tests:

```bash
poetry run pytest
```

3. Start the FastAPI server:

```bash
poetry run uvicorn app.main:app --reload
```

## Development

Run type and style checks:

```bash
./scripts/check.sh
```

