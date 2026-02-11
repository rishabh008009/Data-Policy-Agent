#!/usr/bin/env python3
"""
Seed script for the Data Policy Agent demo.

This script creates sample data in the application database including:
- A sample policy with extracted compliance rules
- Sample violations with various statuses and severities
- Sample review actions for audit trail demonstration

Usage:
    cd backend
    python ../demo/seed_data.py

Or from the project root:
    PYTHONPATH=backend python demo/seed_data.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent / "backend"
if backend_path.exists():
    sys.path.insert(0, str(backend_path))
else:
    # Already in backend directory or backend is in path
    pass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker, engine, Base
from app.models.policy import Policy
from app.models.compliance_rule import ComplianceRule
from app.models.violation import Violation
from app.models.review_action import ReviewAction
from app.models.scan_history import ScanHistory
from app.models.monitoring_config import MonitoringConfig
from app.models.enums import (
    PolicyStatus,
    Severity,
    ViolationStatus,
    ScanStatus,
    ReviewActionType,
)


# Sample policy data
SAMPLE_POLICY = {
    "filename": "acme_compliance_policy.pdf",
    "raw_text": """ACME Corporation Data Compliance Policy
    
This document outlines the data compliance requirements for ACME Corporation.

Rule 2.1: Email Validation - All customer email addresses must be valid.
Rule 2.2: Age Verification - Customer age must be 18 or older.
Rule 2.3: Phone Number Format - Phone numbers must be numeric only.
Rule 3.1: Positive Account Balance - Balances should not be negative.
Rule 3.2: Transaction Amount Limits - Transactions over $10,000 need verification.
Rule 5.1: Required Fields - Name, email, and status must not be null.
Rule 5.2: Status Value Validation - Status must be a valid predefined value.""",
    "status": PolicyStatus.COMPLETED.value,
}

# Sample compliance rules
SAMPLE_RULES = [
    {
        "rule_code": "DATA-001",
        "description": "Email Validation: All customer email addresses must contain @ symbol and valid domain",
        "evaluation_criteria": "Email field must match pattern containing @ and domain extension",
        "target_table": "customers",
        "generated_sql": "SELECT id, email, name FROM customers WHERE email NOT LIKE '%@%.%'",
        "severity": Severity.MEDIUM.value,
        "is_active": True,
    },
    {
        "rule_code": "DATA-002",
        "description": "Age Verification: Customer age must be 18 years or older",
        "evaluation_criteria": "Age field must be >= 18",
        "target_table": "customers",
        "generated_sql": "SELECT id, name, age FROM customers WHERE age < 18",
        "severity": Severity.HIGH.value,
        "is_active": True,
    },
    {
        "rule_code": "DATA-003",
        "description": "Phone Number Format: Phone numbers must contain only digits",
        "evaluation_criteria": "Phone field must contain only numeric characters",
        "target_table": "customers",
        "generated_sql": "SELECT id, name, phone FROM customers WHERE phone ~ '[^0-9+]'",
        "severity": Severity.LOW.value,
        "is_active": True,
    },
    {
        "rule_code": "FIN-001",
        "description": "Positive Account Balance: Account balances should not be negative",
        "evaluation_criteria": "Balance field must be >= 0",
        "target_table": "accounts",
        "generated_sql": "SELECT id, customer_id, balance FROM accounts WHERE balance < 0",
        "severity": Severity.HIGH.value,
        "is_active": True,
    },
    {
        "rule_code": "FIN-002",
        "description": "Transaction Amount Limits: Transactions over $10,000 require verification",
        "evaluation_criteria": "Transactions with amount > 10000 must have verified flag set",
        "target_table": "transactions",
        "generated_sql": "SELECT id, amount, verified FROM transactions WHERE amount > 10000 AND verified = false",
        "severity": Severity.CRITICAL.value,
        "is_active": True,
    },
    {
        "rule_code": "DATA-004",
        "description": "Required Fields: Customer name and email must not be null",
        "evaluation_criteria": "Name and email fields must have non-null, non-empty values",
        "target_table": "customers",
        "generated_sql": "SELECT id, name, email FROM customers WHERE name IS NULL OR email IS NULL OR name = '' OR email = ''",
        "severity": Severity.HIGH.value,
        "is_active": True,
    },
    {
        "rule_code": "DATA-005",
        "description": "Status Value Validation: Status must be active, inactive, suspended, or pending",
        "evaluation_criteria": "Status field must be one of the predefined valid values",
        "target_table": "customers",
        "generated_sql": "SELECT id, name, status FROM customers WHERE status NOT IN ('active', 'inactive', 'suspended', 'pending')",
        "severity": Severity.MEDIUM.value,
        "is_active": True,
    },
]

# Sample violations with various statuses
SAMPLE_VIOLATIONS = [
    # Pending violations (need review)
    {
        "record_identifier": "customer_1042",
        "record_data": {"id": 1042, "name": "John Doe", "email": "johndoe.invalid", "age": 25},
        "justification": "The email address 'johndoe.invalid' does not contain an @ symbol or valid domain extension, violating the email validation rule.",
        "remediation_suggestion": "Update the email field to include a valid email format (e.g., johndoe@example.com). Contact the customer to verify their correct email address.",
        "severity": Severity.MEDIUM.value,
        "status": ViolationStatus.PENDING.value,
        "rule_index": 0,  # DATA-001
    },
    {
        "record_identifier": "customer_1087",
        "record_data": {"id": 1087, "name": "Jane Smith", "age": 16},
        "justification": "Customer age is 16, which is below the minimum required age of 18 for account creation.",
        "remediation_suggestion": "Verify the customer's actual age. If confirmed under 18, the account must be suspended until the customer reaches legal age or parental consent is obtained.",
        "severity": Severity.HIGH.value,
        "status": ViolationStatus.PENDING.value,
        "rule_index": 1,  # DATA-002
    },
    {
        "record_identifier": "transaction_50234",
        "record_data": {"id": 50234, "amount": 15000.00, "verified": False, "customer_id": 1001},
        "justification": "Transaction amount of $15,000 exceeds the $10,000 threshold and lacks required verification documentation.",
        "remediation_suggestion": "Obtain verification documentation for this transaction. Flag the transaction as verified once documentation is received and reviewed.",
        "severity": Severity.CRITICAL.value,
        "status": ViolationStatus.PENDING.value,
        "rule_index": 4,  # FIN-002
    },
    {
        "record_identifier": "account_2045",
        "record_data": {"id": 2045, "customer_id": 1055, "balance": -250.00},
        "justification": "Account balance is -$250.00, which is negative without an approved credit line.",
        "remediation_suggestion": "Review the account for unauthorized overdraft. Either approve a credit line or contact the customer to resolve the negative balance.",
        "severity": Severity.HIGH.value,
        "status": ViolationStatus.PENDING.value,
        "rule_index": 3,  # FIN-001
    },
    # Confirmed violations
    {
        "record_identifier": "customer_1023",
        "record_data": {"id": 1023, "name": "Bob Wilson", "phone": "555-CALL-ME"},
        "justification": "Phone number '555-CALL-ME' contains alphabetic characters, violating the numeric-only phone format rule.",
        "remediation_suggestion": "Update the phone number to contain only numeric digits. Contact the customer to obtain their correct phone number.",
        "severity": Severity.LOW.value,
        "status": ViolationStatus.CONFIRMED.value,
        "rule_index": 2,  # DATA-003
    },
    {
        "record_identifier": "customer_1099",
        "record_data": {"id": 1099, "name": "", "email": "test@example.com"},
        "justification": "Customer name field is empty, violating the required fields rule.",
        "remediation_suggestion": "Update the customer record with a valid name. Contact the customer to obtain their full name.",
        "severity": Severity.HIGH.value,
        "status": ViolationStatus.CONFIRMED.value,
        "rule_index": 5,  # DATA-004
    },
    # False positives
    {
        "record_identifier": "customer_1015",
        "record_data": {"id": 1015, "name": "Test User", "status": "vip"},
        "justification": "Status value 'vip' is not in the predefined list of valid statuses.",
        "remediation_suggestion": "Update the status to one of the valid values: active, inactive, suspended, or pending.",
        "severity": Severity.MEDIUM.value,
        "status": ViolationStatus.FALSE_POSITIVE.value,
        "rule_index": 6,  # DATA-005
    },
    # Resolved violations
    {
        "record_identifier": "transaction_50100",
        "record_data": {"id": 50100, "amount": 12500.00, "verified": True, "customer_id": 1033},
        "justification": "Transaction amount of $12,500 exceeded the $10,000 threshold without verification at time of detection.",
        "remediation_suggestion": "Verification documentation has been obtained and reviewed.",
        "severity": Severity.CRITICAL.value,
        "status": ViolationStatus.RESOLVED.value,
        "rule_index": 4,  # FIN-002
    },
    {
        "record_identifier": "customer_1050",
        "record_data": {"id": 1050, "name": "Alice Brown", "email": "alice@company.com", "age": 17},
        "justification": "Customer age was 17 at time of detection, below the minimum required age of 18.",
        "remediation_suggestion": "Customer has since turned 18. Age verified and updated in system.",
        "severity": Severity.HIGH.value,
        "status": ViolationStatus.RESOLVED.value,
        "rule_index": 1,  # DATA-002
    },
]

# Sample review actions for audit trail
SAMPLE_REVIEW_ACTIONS = [
    # For confirmed violation (customer_1023)
    {
        "violation_index": 4,
        "action_type": ReviewActionType.CONFIRM.value,
        "reviewer_id": "admin@acme-corp.com",
        "notes": "Verified that phone number format is indeed invalid. Customer service will contact for correction.",
    },
    # For confirmed violation (customer_1099)
    {
        "violation_index": 5,
        "action_type": ReviewActionType.CONFIRM.value,
        "reviewer_id": "compliance@acme-corp.com",
        "notes": "Confirmed missing name. Data entry error during import.",
    },
    # For false positive (customer_1015)
    {
        "violation_index": 6,
        "action_type": ReviewActionType.FALSE_POSITIVE.value,
        "reviewer_id": "admin@acme-corp.com",
        "notes": "VIP is a valid status in our extended status list. Rule needs to be updated to include VIP status.",
    },
    # For resolved violations
    {
        "violation_index": 7,
        "action_type": ReviewActionType.CONFIRM.value,
        "reviewer_id": "finance@acme-corp.com",
        "notes": "Large transaction confirmed. Requesting verification documents.",
    },
    {
        "violation_index": 7,
        "action_type": ReviewActionType.RESOLVE.value,
        "reviewer_id": "finance@acme-corp.com",
        "notes": "Verification documents received and approved. Transaction cleared.",
    },
    {
        "violation_index": 8,
        "action_type": ReviewActionType.CONFIRM.value,
        "reviewer_id": "compliance@acme-corp.com",
        "notes": "Age violation confirmed. Account flagged for review.",
    },
    {
        "violation_index": 8,
        "action_type": ReviewActionType.RESOLVE.value,
        "reviewer_id": "compliance@acme-corp.com",
        "notes": "Customer turned 18. Age updated and verified with ID documentation.",
    },
]


async def clear_existing_data(session: AsyncSession) -> None:
    """Clear existing demo data from the database."""
    print("Clearing existing data...")
    
    # Delete in order respecting foreign keys
    await session.execute(text("DELETE FROM review_actions"))
    await session.execute(text("DELETE FROM violations"))
    await session.execute(text("DELETE FROM compliance_rules"))
    await session.execute(text("DELETE FROM policies"))
    await session.execute(text("DELETE FROM scan_history"))
    await session.execute(text("DELETE FROM monitoring_config"))
    
    await session.commit()
    print("Existing data cleared.")


async def seed_policy_and_rules(session: AsyncSession) -> tuple[Policy, list[ComplianceRule]]:
    """Create sample policy and compliance rules."""
    print("Creating sample policy...")
    
    policy = Policy(
        id=uuid.uuid4(),
        filename=SAMPLE_POLICY["filename"],
        raw_text=SAMPLE_POLICY["raw_text"],
        status=SAMPLE_POLICY["status"],
        uploaded_at=datetime.now(timezone.utc) - timedelta(days=7),
    )
    session.add(policy)
    await session.flush()
    
    print(f"Created policy: {policy.filename} (ID: {policy.id})")
    
    print("Creating compliance rules...")
    rules = []
    for rule_data in SAMPLE_RULES:
        rule = ComplianceRule(
            id=uuid.uuid4(),
            policy_id=policy.id,
            rule_code=rule_data["rule_code"],
            description=rule_data["description"],
            evaluation_criteria=rule_data["evaluation_criteria"],
            target_table=rule_data["target_table"],
            generated_sql=rule_data["generated_sql"],
            severity=rule_data["severity"],
            is_active=rule_data["is_active"],
            created_at=datetime.now(timezone.utc) - timedelta(days=7),
        )
        session.add(rule)
        rules.append(rule)
        print(f"  Created rule: {rule.rule_code} - {rule.description[:50]}...")
    
    await session.flush()
    return policy, rules


async def seed_violations(session: AsyncSession, rules: list[ComplianceRule]) -> list[Violation]:
    """Create sample violations."""
    print("Creating sample violations...")
    
    violations = []
    base_time = datetime.now(timezone.utc)
    
    for i, violation_data in enumerate(SAMPLE_VIOLATIONS):
        rule = rules[violation_data["rule_index"]]
        
        # Stagger detection times for realistic data
        detected_at = base_time - timedelta(days=6 - i, hours=i * 2)
        
        # Set resolved_at for resolved violations
        resolved_at = None
        if violation_data["status"] == ViolationStatus.RESOLVED.value:
            resolved_at = detected_at + timedelta(days=2)
        
        violation = Violation(
            id=uuid.uuid4(),
            rule_id=rule.id,
            record_identifier=violation_data["record_identifier"],
            record_data=violation_data["record_data"],
            justification=violation_data["justification"],
            remediation_suggestion=violation_data["remediation_suggestion"],
            severity=violation_data["severity"],
            status=violation_data["status"],
            detected_at=detected_at,
            resolved_at=resolved_at,
        )
        session.add(violation)
        violations.append(violation)
        print(f"  Created violation: {violation.record_identifier} ({violation.status})")
    
    await session.flush()
    return violations


async def seed_review_actions(session: AsyncSession, violations: list[Violation]) -> None:
    """Create sample review actions for audit trail."""
    print("Creating review actions...")
    
    base_time = datetime.now(timezone.utc)
    
    for i, action_data in enumerate(SAMPLE_REVIEW_ACTIONS):
        violation = violations[action_data["violation_index"]]
        
        action = ReviewAction(
            id=uuid.uuid4(),
            violation_id=violation.id,
            action_type=action_data["action_type"],
            reviewer_id=action_data["reviewer_id"],
            notes=action_data["notes"],
            created_at=base_time - timedelta(days=5 - i, hours=i),
        )
        session.add(action)
        print(f"  Created review action: {action.action_type} by {action.reviewer_id}")
    
    await session.flush()


async def seed_scan_history(session: AsyncSession) -> None:
    """Create sample scan history."""
    print("Creating scan history...")
    
    base_time = datetime.now(timezone.utc)
    
    scans = [
        {
            "started_at": base_time - timedelta(days=6),
            "completed_at": base_time - timedelta(days=6) + timedelta(minutes=5),
            "status": ScanStatus.COMPLETED.value,
            "violations_found": 5,
            "new_violations": 5,
        },
        {
            "started_at": base_time - timedelta(days=4),
            "completed_at": base_time - timedelta(days=4) + timedelta(minutes=3),
            "status": ScanStatus.COMPLETED.value,
            "violations_found": 7,
            "new_violations": 2,
        },
        {
            "started_at": base_time - timedelta(days=2),
            "completed_at": base_time - timedelta(days=2) + timedelta(minutes=4),
            "status": ScanStatus.COMPLETED.value,
            "violations_found": 9,
            "new_violations": 2,
        },
        {
            "started_at": base_time - timedelta(hours=6),
            "completed_at": base_time - timedelta(hours=6) + timedelta(minutes=2),
            "status": ScanStatus.COMPLETED.value,
            "violations_found": 9,
            "new_violations": 0,
        },
    ]
    
    for scan_data in scans:
        scan = ScanHistory(
            id=uuid.uuid4(),
            started_at=scan_data["started_at"],
            completed_at=scan_data["completed_at"],
            status=scan_data["status"],
            violations_found=scan_data["violations_found"],
            new_violations=scan_data["new_violations"],
        )
        session.add(scan)
        print(f"  Created scan: {scan.started_at.date()} - {scan.violations_found} violations found")
    
    await session.flush()


async def seed_monitoring_config(session: AsyncSession) -> None:
    """Create monitoring configuration."""
    print("Creating monitoring configuration...")
    
    config = MonitoringConfig(
        id=uuid.uuid4(),
        interval_minutes=360,  # 6 hours
        is_enabled=True,
        next_run_at=datetime.now(timezone.utc) + timedelta(hours=6),
        last_run_at=datetime.now(timezone.utc) - timedelta(hours=6),
    )
    session.add(config)
    print(f"  Monitoring enabled: every {config.interval_minutes} minutes")
    
    await session.flush()


async def main() -> None:
    """Main function to seed the database."""
    print("=" * 60)
    print("Data Policy Agent - Demo Data Seeder")
    print("=" * 60)
    print()
    
    try:
        async with async_session_maker() as session:
            # Clear existing data
            await clear_existing_data(session)
            
            # Seed data
            policy, rules = await seed_policy_and_rules(session)
            violations = await seed_violations(session, rules)
            await seed_review_actions(session, violations)
            await seed_scan_history(session)
            await seed_monitoring_config(session)
            
            # Commit all changes
            await session.commit()
            
            print()
            print("=" * 60)
            print("Demo data seeded successfully!")
            print("=" * 60)
            print()
            print("Summary:")
            print(f"  - 1 policy document")
            print(f"  - {len(rules)} compliance rules")
            print(f"  - {len(violations)} violations")
            print(f"    - Pending: {sum(1 for v in violations if v.status == ViolationStatus.PENDING.value)}")
            print(f"    - Confirmed: {sum(1 for v in violations if v.status == ViolationStatus.CONFIRMED.value)}")
            print(f"    - False Positive: {sum(1 for v in violations if v.status == ViolationStatus.FALSE_POSITIVE.value)}")
            print(f"    - Resolved: {sum(1 for v in violations if v.status == ViolationStatus.RESOLVED.value)}")
            print(f"  - {len(SAMPLE_REVIEW_ACTIONS)} review actions")
            print(f"  - 4 scan history records")
            print(f"  - Monitoring configured (6-hour interval)")
            print()
            
    except Exception as e:
        print(f"Error seeding data: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
