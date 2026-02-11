# Implementation Plan: Data Policy Agent

## Overview

This implementation plan breaks down the Data Policy Agent into incremental coding tasks suitable for a hackathon timeline. Tasks are ordered to deliver a working demo as quickly as possible, with core functionality prioritized over optional features. Each task builds on previous work to ensure no orphaned code.

## Tasks

- [x] 1. Project Setup and Core Infrastructure
  - [x] 1.1 Initialize Python backend project structure
    - Create FastAPI project with `backend/` directory structure
    - Set up `pyproject.toml` with dependencies: fastapi, uvicorn, sqlalchemy, asyncpg, pdfplumber, openai, apscheduler, hypothesis, pytest
    - Create `backend/app/main.py` with FastAPI app initialization
    - Create `backend/app/config.py` for environment configuration
    - _Requirements: Project foundation_

  - [x] 1.2 Initialize React frontend project
    - Create React TypeScript project in `frontend/` using Vite
    - Install dependencies: axios, react-router-dom, recharts, tailwindcss
    - Set up basic project structure with `src/components/`, `src/pages/`, `src/api/`
    - _Requirements: Project foundation_

  - [x] 1.3 Set up application database schema
    - Create SQLAlchemy models in `backend/app/models/` for Policy, ComplianceRule, Violation, ReviewAction, DatabaseConnection, ScanHistory, MonitoringConfig
    - Create Alembic migration for initial schema
    - Create `backend/app/database.py` for database session management
    - _Requirements: Data persistence foundation_

- [x] 2. Checkpoint - Verify project setup
  - Ensure project structure is correct and dependencies install
  - Ensure database migrations run successfully
  - Ask the user if questions arise

- [x] 3. LLM Client Implementation
  - [x] 3.1 Create LLM client abstraction
    - Create `backend/app/services/llm_client.py` with LLMClient class
    - Implement `extract_rules()` method with prompt template for rule extraction
    - Implement `generate_sql()` method with prompt template for SQL generation
    - Implement `explain_violation()` method for justification generation
    - Implement `suggest_remediation()` method for remediation suggestions
    - Support both OpenAI and Gemini APIs via configuration
    - _Requirements: 1.2, 1.3, 3.2, 7.1_

  - [x] 3.2 Write property test for rule extraction structure
    - **Property 1: Compliance Rule Structure Validity**
    - Test that parsed rules always contain required fields
    - **Validates: Requirements 1.3**

- [x] 4. Policy Parser Service
  - [x] 4.1 Implement PDF text extraction
    - Create `backend/app/services/policy_parser.py` with PolicyParserService class
    - Implement `extract_text()` using pdfplumber for PDF parsing
    - Handle corrupted/empty PDF errors with descriptive messages
    - _Requirements: 1.1, 1.4_

  - [x] 4.2 Implement policy processing pipeline
    - Implement `parse_rules()` to send extracted text to LLM and parse response
    - Implement `process_policy()` for full pipeline: extract → parse → store
    - Store extracted rules with reference to source policy
    - _Requirements: 1.2, 1.3, 1.6_

  - [x] 4.3 Write property test for policy-to-rules round trip
    - **Property 2: Policy-to-Rules Round Trip**
    - Test that stored rules can be retrieved with correct policy reference
    - **Validates: Requirements 1.6**

- [x] 5. Policy Management API Endpoints
  - [x] 5.1 Create policy API routes
    - Create `backend/app/routers/policies.py` with FastAPI router
    - Implement `POST /api/policies/upload` for PDF upload
    - Implement `GET /api/policies` to list all policies
    - Implement `GET /api/policies/{id}` to get policy with rules
    - Implement `DELETE /api/policies/{id}` to remove policy
    - _Requirements: 1.1, 1.6_

  - [x] 5.2 Create rules API routes
    - Create `backend/app/routers/rules.py` with FastAPI router
    - Implement `GET /api/rules` to list all rules
    - Implement `GET /api/rules/{id}` to get rule details
    - Implement `PATCH /api/rules/{id}` to enable/disable rules
    - _Requirements: 1.3_

- [x] 6. Checkpoint - Verify policy ingestion works
  - Test uploading a sample PDF policy document
  - Verify rules are extracted and stored correctly
  - Ask the user if questions arise

- [x] 7. Database Scanner Service
  - [x] 7.1 Implement database connection management
    - Create `backend/app/services/db_scanner.py` with DatabaseScannerService class
    - Implement `connect()` to establish PostgreSQL connection to target database
    - Implement `get_schema()` to retrieve table/column metadata
    - Handle connection errors with diagnostic messages
    - _Requirements: 2.1, 2.2, 2.5_

  - [x] 7.2 Write property test for schema retrieval
    - **Property 3: Schema Retrieval Accuracy**
    - Test that retrieved schema matches actual database structure
    - **Validates: Requirements 2.2**

  - [x] 7.3 Implement SQL query generation
    - Implement `generate_query()` using LLM to create SQL from rule criteria
    - Validate generated SQL syntax before execution
    - Flag rules that cannot be translated for human review
    - _Requirements: 2.4, 2.6_

  - [x] 7.4 Write property test for SQL validity
    - **Property 5: Generated SQL Validity**
    - Test that generated SQL is syntactically valid PostgreSQL
    - **Validates: Requirements 2.4**

  - [x] 7.5 Implement violation scanning
    - Implement `scan_for_violations()` to execute queries and collect results
    - Implement `generate_justification()` for each detected violation
    - Implement `generate_remediation()` for remediation suggestions
    - Create Violation records with all required fields
    - _Requirements: 2.3, 3.1, 3.2, 3.3, 7.1_

  - [x] 7.6 Write property tests for violation detection
    - **Property 4: Scan Completeness** - All active rules evaluated
    - **Property 6: Violation Report Completeness** - Required fields present
    - **Property 7: Severity Inheritance** - Violation severity matches rule
    - **Property 10: New Violation Initial Status** - Status is "pending"
    - **Validates: Requirements 2.3, 3.1, 3.2, 3.3, 4.1**

- [x] 8. Database and Scanning API Endpoints
  - [x] 8.1 Create database connection API routes
    - Create `backend/app/routers/database.py` with FastAPI router
    - Implement `POST /api/database/connect` to test and save connection
    - Implement `GET /api/database/schema` to retrieve target schema
    - _Requirements: 2.1, 2.2_

  - [x] 8.2 Create scan API routes
    - Implement `POST /api/database/scan` to trigger manual compliance scan
    - Return scan results with violation counts
    - _Requirements: 2.3_

- [x] 9. Checkpoint - Verify scanning works end-to-end
  - Test connecting to a sample PostgreSQL database
  - Test running a compliance scan with sample rules
  - Verify violations are detected and stored
  - Ask the user if questions arise

- [x] 10. Violation Management and Human Review
  - [x] 10.1 Create violations API routes
    - Create `backend/app/routers/violations.py` with FastAPI router
    - Implement `GET /api/violations` with filtering (status, severity, rule, date)
    - Implement `GET /api/violations/{id}` for violation details
    - _Requirements: 3.1, 6.5_

  - [x] 10.2 Write property test for violation filtering
    - **Property 15: Violation Filtering Correctness**
    - Test that filters return only matching violations
    - **Validates: Requirements 6.5**

  - [x] 10.3 Implement human review workflow
    - Implement `PATCH /api/violations/{id}/review` for review decisions
    - Create ReviewAction audit entries for all review actions
    - Update violation status based on review decision
    - _Requirements: 4.3, 4.4, 4.6_

  - [x] 10.4 Write property test for review status transitions
    - **Property 11: Review Status Transitions**
    - Test that review actions update status and create audit entries
    - **Validates: Requirements 4.3, 4.4, 4.6**

- [x] 11. Monitoring Scheduler
  - [x] 11.1 Implement monitoring scheduler service
    - Create `backend/app/services/scheduler.py` with MonitoringScheduler class
    - Implement `schedule_scan()` using APScheduler for periodic scans
    - Implement `cancel_schedule()` to stop scheduled scans
    - Implement `get_status()` to return scheduler state
    - Implement `run_scheduled_scan()` to execute scans and detect new violations
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6_

  - [x] 11.2 Write property tests for monitoring
    - **Property 12: New Violation Detection** - New violations correctly identified
    - **Property 13: Scan Interval Configuration** - Valid intervals accepted
    - **Validates: Requirements 5.2, 5.6**

  - [x] 11.3 Create monitoring API routes
    - Create `backend/app/routers/monitoring.py` with FastAPI router
    - Implement `GET /api/monitoring/status` for scheduler status
    - Implement `POST /api/monitoring/schedule` to configure schedule
    - Implement `DELETE /api/monitoring/schedule` to disable scheduling
    - _Requirements: 5.1, 5.6_

- [x] 12. Dashboard API Endpoints
  - [x] 12.1 Create dashboard summary API
    - Create `backend/app/routers/dashboard.py` with FastAPI router
    - Implement `GET /api/dashboard/summary` for compliance overview stats
    - Calculate totals by status and severity
    - _Requirements: 6.1_

  - [x] 12.2 Write property test for summary accuracy
    - **Property 14: Dashboard Summary Accuracy**
    - Test that summary counts match actual database records
    - **Validates: Requirements 6.1**

  - [x] 12.3 Implement trends API
    - Implement `GET /api/dashboard/trends` for violation trends over time
    - Calculate improvement/degradation percentages
    - _Requirements: 6.4, 8.3_

  - [x] 12.4 Write property test for trend calculations
    - **Property 18: Trend Percentage Calculation**
    - Test that percentage calculations are mathematically correct
    - **Validates: Requirements 8.3**

- [x] 13. Checkpoint - Verify backend is complete
  - Test all API endpoints with sample data
  - Verify monitoring scheduler works correctly
  - Ensure all backend functionality is working
  - Ask the user if questions arise

- [x] 14. React Dashboard - Core Components
  - [x] 14.1 Create API client and types
    - Create `frontend/src/api/client.ts` with axios instance
    - Create `frontend/src/api/types.ts` with TypeScript interfaces matching backend models
    - Create API functions for all endpoints
    - _Requirements: Frontend foundation_

  - [x] 14.2 Create layout and navigation
    - Create `frontend/src/components/Layout.tsx` with navigation sidebar
    - Create `frontend/src/pages/` with page components for Dashboard, Policies, Violations, Settings
    - Set up React Router for navigation
    - _Requirements: 6.6_

  - [x] 14.3 Implement dashboard overview page
    - Create `frontend/src/pages/DashboardPage.tsx` with summary cards
    - Display violation counts by status and severity
    - Show last scan time and next scheduled scan
    - _Requirements: 6.1, 6.2_

- [x] 15. React Dashboard - Policy Management
  - [x] 15.1 Create policy upload component
    - Create `frontend/src/components/PolicyUploadForm.tsx` with drag-and-drop
    - Handle file upload to backend API
    - Display upload progress and success/error states
    - _Requirements: 1.1_

  - [x] 15.2 Create policy list and detail views
    - Create `frontend/src/pages/PoliciesPage.tsx` with policy list
    - Display extracted rules for each policy
    - Allow enabling/disabling rules
    - _Requirements: 1.3, 1.6_

- [x] 16. React Dashboard - Violation Management
  - [x] 16.1 Create violation list component
    - Create `frontend/src/components/ViolationList.tsx` with filterable table
    - Implement filters for status, severity, rule, date range
    - Display violation summary with severity indicators
    - _Requirements: 6.5_

  - [x] 16.2 Create violation detail and review panel
    - Create `frontend/src/components/ViolationDetail.tsx` for full report view
    - Create `frontend/src/components/ReviewPanel.tsx` for review decisions
    - Display justification and remediation suggestion
    - Allow confirm/false positive/resolve actions
    - _Requirements: 4.2, 4.3, 4.4, 7.3_

- [x] 17. React Dashboard - Trends and Settings
  - [x] 17.1 Create trend visualization
    - Create `frontend/src/components/TrendChart.tsx` using Recharts
    - Display violation counts over time
    - Show improvement/degradation indicators
    - _Requirements: 6.4, 8.4_

  - [x] 17.2 Create settings page
    - Create `frontend/src/pages/SettingsPage.tsx` for configuration
    - Create `frontend/src/components/DatabaseConfig.tsx` for DB connection setup
    - Create `frontend/src/components/ScheduleConfig.tsx` for monitoring schedule
    - _Requirements: 2.1, 5.1, 5.6_

- [x] 18. Final Integration and Polish
  - [x] 18.1 Wire frontend to backend
    - Ensure all API calls work correctly
    - Add loading states and error handling throughout
    - Test full user workflows end-to-end
    - _Requirements: All_

  - [x] 18.2 Add demo data and documentation
    - Create sample PDF policy document for demo
    - Create sample PostgreSQL database with test data
    - Write README with setup instructions
    - _Requirements: Demo readiness_

- [x] 19. Final Checkpoint - Demo Ready
  - Verify complete workflow: upload policy → scan database → review violations
  - Test monitoring scheduler with short interval
  - Ensure dashboard displays all data correctly
  - Ask the user if questions arise

## Notes

- Tasks marked with `*` are optional property-based tests that can be skipped for faster MVP
- Core functionality (tasks 1-13) should be prioritized for the hackathon deadline
- Frontend tasks (14-17) can be simplified if time is short
- Each checkpoint ensures incremental progress and catches issues early
- Property tests use Hypothesis library for Python backend testing
