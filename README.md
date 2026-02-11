# Data Policy Agent

AI-powered compliance monitoring system that automatically detects policy violations in your PostgreSQL databases.

## Features

- **PDF Policy Ingestion** - Upload policy documents and automatically extract compliance rules using AI
- **Database Scanning** - Connect to PostgreSQL databases and scan for violations
- **Violation Detection** - AI-generated explanations and remediation suggestions
- **Human Review** - Review queue for confirming or dismissing violations
- **Periodic Monitoring** - Configurable scheduled scans
- **Dashboard** - React-based UI for managing compliance

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  React Frontend │────▶│  FastAPI Backend │────▶│  PostgreSQL DB  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  OpenAI/Gemini  │
                        └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- OpenAI API key (or Gemini API key)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd data-policy-agent
```

### 2. Set Up Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL and OPENAI_API_KEY

# Create database and run migrations
createdb policy_agent
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

### 3. Set Up Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### 4. Access the Application

Open http://localhost:5173 in your browser.

## Demo Setup

For a quick demo with sample data:

```bash
# Create sample target database
createdb sample_target
psql -d sample_target -f demo/sample_target_db.sql

# Seed application with demo data
cd backend
python -m demo.seed_data
```

See [demo/README.md](demo/README.md) for detailed demo instructions.

## Project Structure

```
data-policy-agent/
├── backend/              # FastAPI backend
│   ├── app/              # Application code
│   │   ├── models/       # SQLAlchemy models
│   │   ├── routers/      # API endpoints
│   │   └── services/     # Business logic
│   ├── tests/            # Backend tests
│   └── alembic/          # Database migrations
├── frontend/             # React frontend
│   └── src/
│       ├── components/   # React components
│       ├── pages/        # Page components
│       └── api/          # API client
└── demo/                 # Demo data and scripts
    ├── sample_policy.txt # Sample policy document
    ├── sample_target_db.sql # Sample database
    └── seed_data.py      # Demo data seeder
```

## Documentation

- [Backend README](backend/README.md) - Detailed backend setup and API docs
- [Frontend README](frontend/README.md) - Frontend development guide
- [Demo README](demo/README.md) - Demo setup instructions

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| POST /api/policies/upload | Upload PDF policy |
| GET /api/policies | List policies |
| GET /api/rules | List compliance rules |
| POST /api/database/connect | Configure target database |
| POST /api/database/scan | Trigger compliance scan |
| GET /api/violations | List violations |
| PATCH /api/violations/{id}/review | Review violation |
| POST /api/monitoring/schedule | Configure monitoring |
| GET /api/dashboard/summary | Get compliance summary |

## Tech Stack

**Backend:**
- FastAPI - Web framework
- SQLAlchemy - ORM
- PostgreSQL - Database
- pdfplumber - PDF processing
- OpenAI/Gemini - LLM integration
- APScheduler - Background jobs
- Hypothesis - Property-based testing

**Frontend:**
- React 18 - UI framework
- TypeScript - Type safety
- Vite - Build tool
- Tailwind CSS - Styling
- Recharts - Data visualization
- React Router - Navigation

## License

MIT
