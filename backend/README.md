# Data Policy Agent - Backend

AI-powered compliance monitoring system for automated policy violation detection.

## Overview

The Data Policy Agent backend is built with FastAPI and provides:
- PDF policy document ingestion and AI-powered rule extraction
- PostgreSQL database scanning for compliance violations
- Human-in-the-loop review workflow
- Periodic monitoring with configurable schedules
- RESTful API for the React dashboard

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [Running the Server](#running-the-server)
- [Running Tests](#running-tests)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Demo Workflow](#demo-workflow)

## Prerequisites

- Python 3.11+ - https://www.python.org/downloads/
- PostgreSQL 14+ - https://www.postgresql.org/download/
- Node.js 18+ (for frontend) - https://nodejs.org/

### Verify Prerequisites

```bash
python --version    # Should be 3.11 or higher
psql --version      # Should be 14 or higher
node --version      # Should be 18 or higher (for frontend)
```

## Quick Start

```bash
# 1. Clone and navigate to backend
cd backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Set up environment
cp .env.example .env
# Edit .env with your configuration (see Configuration section)

# 5. Create database and run migrations
createdb policy_agent
alembic upgrade head

# 6. Start the server
uvicorn app.main:app --reload --port 8000
```

## Installation

### 1. Create Virtual Environment

```bash
python -m venv venv

# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -e ".[dev]"
```

## Configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Application database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/policy_agent

# LLM Configuration
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=your-openai-api-key-here

# CORS (frontend URLs)
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
```

### Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `OPENAI_API_KEY` | OpenAI API key | Required* |
| `GEMINI_API_KEY` | Google Gemini API key | Required* |
| `LLM_PROVIDER` | LLM provider (openai/gemini) | openai |
| `LLM_MODEL` | LLM model name | gpt-4o |
| `DEBUG` | Enable debug mode | false |
| `HOST` | Server host | 0.0.0.0 |
| `PORT` | Server port | 8000 |

*Either OPENAI_API_KEY or GEMINI_API_KEY required.

## Database Setup

### 1. Create Application Database

```bash
createdb policy_agent
```

### 2. Run Migrations

```bash
alembic upgrade head
```

### 3. (Optional) Create Sample Target Database

```bash
createdb sample_target
psql -d sample_target -f ../demo/sample_target_db.sql
```

### 4. (Optional) Seed Demo Data

```bash
python -m demo.seed_data
```

## Running the Server

### Development Mode

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app

# Unit tests only
pytest tests/unit/

# Property tests only
pytest tests/property/
```

## API Documentation

Once running, access the API docs at:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/policies/upload | POST | Upload PDF policy |
| /api/policies | GET | List policies |
| /api/rules | GET | List compliance rules |
| /api/database/connect | POST | Configure target DB |
| /api/database/scan | POST | Trigger scan |
| /api/violations | GET | List violations |
| /api/violations/{id}/review | PATCH | Review violation |
| /api/monitoring/schedule | POST | Configure schedule |
| /api/dashboard/summary | GET | Get summary |
| /api/dashboard/trends | GET | Get trends |

## Project Structure

```
backend/
├── app/
│   ├── main.py           # FastAPI app
│   ├── config.py         # Configuration
│   ├── database.py       # DB session
│   ├── models/           # SQLAlchemy models
│   ├── routers/          # API routes
│   └── services/         # Business logic
├── tests/
│   ├── unit/             # Unit tests
│   ├── property/         # Property tests
│   └── integration/      # Integration tests
├── alembic/              # Migrations
├── .env.example
├── alembic.ini
└── pyproject.toml
```

## Demo Workflow

1. Set up databases:
   ```bash
   createdb policy_agent
   createdb sample_target
   ```

2. Run migrations:
   ```bash
   alembic upgrade head
   ```

3. Load sample data:
   ```bash
   psql -d sample_target -f ../demo/sample_target_db.sql
   python -m demo.seed_data
   ```

4. Start backend:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

5. Start frontend:
   ```bash
   cd ../frontend && npm run dev
   ```

6. Open http://localhost:5173

### Target Database Connection

| Field | Value |
|-------|-------|
| Host | localhost |
| Port | 5432 |
| Database | sample_target |
| Username | postgres |
| Password | (your password) |

## Troubleshooting

- "Database does not exist": `createdb policy_agent`
- "Relation does not exist": `alembic upgrade head`
- "Module not found": `pip install -e ".[dev]"`
