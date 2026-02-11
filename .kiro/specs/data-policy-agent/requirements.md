# Requirements Document

## Introduction

The Data Policy Agent is a hackathon project designed to automate compliance monitoring for organizations. It ingests free-text PDF policy documents, extracts actionable compliance rules using AI/LLM, connects to a PostgreSQL database to scan for violations, and provides continuous monitoring with human-in-the-loop review capabilities. The system presents findings through a React dashboard with explainable justifications and remediation suggestions.

## Glossary

- **Policy_Document**: A PDF file containing free-text compliance rules and business policies
- **Compliance_Rule**: An actionable, machine-interpretable rule extracted from a Policy_Document
- **Violation**: A database record that fails to comply with one or more Compliance_Rules
- **Violation_Report**: A structured output containing the violated rule, affected records, justification, and suggested remediation
- **Policy_Parser**: The component that extracts text from PDF documents and uses AI/LLM to interpret compliance rules
- **Database_Scanner**: The component that connects to PostgreSQL and evaluates records against Compliance_Rules
- **Monitoring_Scheduler**: The component that triggers periodic compliance scans
- **Review_Queue**: A collection of flagged violations awaiting human review and decision
- **Dashboard**: The React-based web interface for viewing compliance status and managing violations
- **Remediation_Suggestion**: An AI-generated recommendation for resolving a detected violation

## Requirements

### Requirement 1: PDF Policy Document Ingestion

**User Story:** As an Operations Manager, I want to upload PDF policy documents, so that the system can extract compliance rules without manual data entry.

#### Acceptance Criteria

1. WHEN a user uploads a PDF file THEN the Policy_Parser SHALL extract all text content from the document
2. WHEN text extraction completes THEN the Policy_Parser SHALL send the extracted text to the AI/LLM API for rule interpretation
3. WHEN the AI/LLM processes the policy text THEN the Policy_Parser SHALL return a structured list of Compliance_Rules with rule ID, description, and evaluation criteria
4. IF a PDF file is corrupted or unreadable THEN the Policy_Parser SHALL return a descriptive error message indicating the failure reason
5. IF the AI/LLM API is unavailable THEN the Policy_Parser SHALL queue the document for retry and notify the user of the delay
6. WHEN a Policy_Document is successfully parsed THEN the system SHALL store the extracted Compliance_Rules with a reference to the source document

### Requirement 2: Database Connection and Scanning

**User Story:** As an Operations Manager, I want the system to connect to our PostgreSQL database and scan for violations, so that I can identify non-compliant records automatically.

#### Acceptance Criteria

1. WHEN a user provides database connection credentials THEN the Database_Scanner SHALL establish a secure connection to the PostgreSQL database
2. WHEN connected to the database THEN the Database_Scanner SHALL retrieve the database schema including table names, column names, and data types
3. WHEN a compliance scan is initiated THEN the Database_Scanner SHALL evaluate records against all active Compliance_Rules
4. WHEN evaluating records THEN the Database_Scanner SHALL generate SQL queries based on the Compliance_Rule evaluation criteria
5. IF database connection fails THEN the Database_Scanner SHALL return an error message with connection diagnostics
6. IF a Compliance_Rule cannot be translated to a valid SQL query THEN the Database_Scanner SHALL flag the rule for human review

### Requirement 3: Violation Detection and Reporting

**User Story:** As an Operations Manager, I want detected violations to be clearly flagged with explanations, so that I can understand why each record is non-compliant.

#### Acceptance Criteria

1. WHEN a record violates a Compliance_Rule THEN the system SHALL create a Violation_Report containing the rule ID, record identifier, and affected field values
2. WHEN creating a Violation_Report THEN the system SHALL include an AI-generated justification explaining why the record violates the rule
3. WHEN a violation is detected THEN the system SHALL assign a severity level based on the Compliance_Rule priority
4. WHEN multiple violations exist for the same record THEN the system SHALL group them in a single Violation_Report
5. THE system SHALL persist all Violation_Reports with timestamps for audit purposes

### Requirement 4: Human Review and Intervention

**User Story:** As an Operations Manager, I want to review flagged violations and make decisions, so that I can ensure accuracy and handle edge cases appropriately.

#### Acceptance Criteria

1. WHEN a violation is detected THEN the system SHALL add it to the Review_Queue with status "pending"
2. WHEN a reviewer views a violation THEN the Dashboard SHALL display the full Violation_Report with all supporting details
3. WHEN a reviewer marks a violation as "confirmed" THEN the system SHALL update the violation status and log the reviewer action
4. WHEN a reviewer marks a violation as "false positive" THEN the system SHALL update the status and optionally refine the Compliance_Rule
5. WHEN a reviewer requests more context THEN the system SHALL retrieve additional related records from the database
6. THE system SHALL maintain an audit log of all human review actions with timestamps and reviewer identity

### Requirement 5: Periodic Monitoring

**User Story:** As an Operations Manager, I want the system to automatically check for new violations on a schedule, so that I can catch compliance issues as they occur.

#### Acceptance Criteria

1. WHEN a monitoring schedule is configured THEN the Monitoring_Scheduler SHALL trigger compliance scans at the specified intervals
2. WHEN a scheduled scan completes THEN the system SHALL compare results with previous scans to identify new violations
3. WHEN new violations are detected THEN the system SHALL add them to the Review_Queue and optionally send notifications
4. WHILE a scheduled scan is running THEN the Dashboard SHALL display the scan status and progress
5. IF a scheduled scan fails THEN the Monitoring_Scheduler SHALL retry with exponential backoff and log the failure
6. THE system SHALL support configurable scan frequencies from hourly to daily intervals

### Requirement 6: Compliance Dashboard

**User Story:** As an Operations Manager, I want a visual dashboard to view compliance status, so that I can quickly understand our organization's compliance posture.

#### Acceptance Criteria

1. WHEN a user accesses the Dashboard THEN the system SHALL display a summary of total violations by status and severity
2. WHEN viewing the Dashboard THEN the system SHALL show the most recent scan timestamp and next scheduled scan time
3. WHEN a user selects a violation THEN the Dashboard SHALL display the complete Violation_Report with justification
4. WHEN viewing trends THEN the Dashboard SHALL display a chart showing violation counts over time
5. THE Dashboard SHALL provide filtering options by violation status, severity, rule, and date range
6. THE Dashboard SHALL be responsive and accessible on desktop browsers

### Requirement 7: Remediation Suggestions

**User Story:** As an Operations Manager, I want the system to suggest how to fix violations, so that I can take corrective action efficiently.

#### Acceptance Criteria

1. WHEN a Violation_Report is created THEN the system SHALL generate a Remediation_Suggestion using the AI/LLM
2. WHEN generating a Remediation_Suggestion THEN the system SHALL consider the specific field values and rule requirements
3. WHEN displaying a violation THEN the Dashboard SHALL show the Remediation_Suggestion alongside the justification
4. IF a remediation cannot be automatically suggested THEN the system SHALL indicate that manual review is required

### Requirement 8: Compliance Status Summarization

**User Story:** As an Operations Manager, I want to see compliance trends and summaries, so that I can report on our compliance posture to stakeholders.

#### Acceptance Criteria

1. WHEN requested THEN the system SHALL generate a compliance summary report for a specified time period
2. WHEN generating a summary THEN the system SHALL include total violations found, resolved, and pending by category
3. WHEN generating a summary THEN the system SHALL calculate compliance improvement or degradation percentages
4. THE Dashboard SHALL display trend charts showing compliance status changes over time
