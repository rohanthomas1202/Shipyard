# Running Shipyard

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm
- OpenAI API key

## Setup (first time only)

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install frontend dependencies
cd web && npm install && cd ..

# 3. Create .env file
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Development (two terminals)

### Terminal 1: Backend
```bash
uvicorn server.main:app --reload --port 8000
```

### Terminal 2: Frontend
```bash
cd web && npm run dev
```

Open **http://localhost:5173** in your browser.

The Vite dev server proxies all API and WebSocket requests to the backend on port 8000.

## Production (single process)

```bash
# Build frontend
cd web && npm run build && cd ..

# Run server (serves both API and frontend)
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

## Quick test (verify backend works)

```bash
# Health check
curl http://localhost:8000/health

# Create a project
curl -X POST http://localhost:8000/projects \
  -H 'Content-Type: application/json' \
  -d '{"name": "my-project", "path": "/path/to/your/code"}'
```
