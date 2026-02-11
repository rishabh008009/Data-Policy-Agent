# Data Policy Agent - Demo Setup

This directory contains sample data and scripts for demonstrating the Data Policy Agent.

## Contents

- `sample_policy.txt` - Sample compliance policy document (text format for easy viewing)
- `sample_target_db.sql` - SQL script to create a sample database with test data
- `seed_data.py` - Python script to seed the application database with demo data

## Quick Start

### 1. Set Up the Application Database

```bash
# Create the application database
createdb policy_agent

# Navigate to backend directory
cd backend

# Run migrations
alembic upgrade head
```

### 2. Set Up the Sample Target Database

```bash
# Create a sample database to scan
createdb sample_target

# Load sample data with intentional violations
psql -d sample_target -f demo/sample_target_db.sql
```

### 3. Seed Demo Data

```bash
# From the project root
cd backend
python -m demo.seed_data
```

Or:

```bash
# From project root with PYTHONPATH
PYTHONPATH=backend python demo/seed_data.py
```

### 4. Start the Application

```bash
# Terminal 1: Start backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend
npm run dev
```

### 5. Access the Dashboard

Open http://localhost:5173 in your browser.

## Demo Workflow

1. **View Dashboard** - See compliance summary with pre-seeded violations
2. **Browse Violations** - Filter by status, severity, or rule
3. **Review Violations** - Confirm, mark as false positive, or resolve
4. **View Policies** - See the sample policy and extracted rules
5. **Configure Database** - Connect to the sample target database
6. **Run Scan** - Trigger a compliance scan to detect new violations
7. **Configure Monitoring** - Set up periodic scans

## Sample Data Overview

### Policy & Rules

The demo includes 1 policy document with 7 compliance rules:

| Rule Code | Description | Severity |
|-----------|-------------|----------|
| DATA-001 | Email Validation | Medium |
| DATA-002 | Age Verification (18+) | High |
| DATA-003 | Phone Number Format | Low |
| DATA-004 | Required Fields | High |
| DATA-005 | Status Value Validation | Medium |
| FIN-001 | Positive Account Balance | High |
| FIN-002 | Transaction Amount Limits | Critical |

### Violations

The demo includes 9 pre-seeded violations:

- 4 Pending (awaiting review)
- 2 Confirmed (verified violations)
- 1 False Positive (incorrectly flagged)
- 2 Resolved (addressed violations)

### Target Database Violations

The sample target database contains intentional violations:

- 3 invalid email addresses
- 3 underage customers (< 18)
- 3 invalid phone numbers
- 4 missing required fields
- 3 invalid status values
- 3 negative account balances
- 5 large unverified transactions (> $10,000)

## Database Connection for Demo

When configuring the database connection in the UI, use:

| Field | Value |
|-------|-------|
| Host | localhost |
| Port | 5432 |
| Database | sample_target |
| Username | postgres |
| Password | (your postgres password) |

## Troubleshooting

### "Database does not exist" error

Make sure you've created both databases:

```bash
createdb policy_agent
createdb sample_target
```

### "Relation does not exist" error

Run the migrations:

```bash
cd backend
alembic upgrade head
```

### Seed script fails

Ensure the backend dependencies are installed:

```bash
cd backend
pip install -e ".[dev]"
```

### Frontend can't connect to backend

Check that the backend is running on port 8000 and CORS is configured correctly in `.env`.
