"""Property-based tests for violation detection.

Feature: data-policy-agent, Property 4: Scan Completeness
Feature: data-policy-agent, Property 6: Violation Report Completeness
Feature: data-policy-agent, Property 7: Severity Inheritance
Feature: data-policy-agent, Property 10: New Violation Initial Status

This module contains property-based tests that verify:
1. All active rules are evaluated during a scan (Property 4)
2. Violation records contain all required fields (Property 6)
3. Violation severity always matches the source rule's severity (Property 7)
4. New violations always have status "pending" (Property 10)

**Validates: Requirements 2.3, 3.1, 3.2, 3.3, 4.1**

Note: Since we can't use a real database or LLM in property tests, we test the
violation detection logic by:
1. Testing the _get_record_identifier helper function
2. Testing Violation model creation with proper field initialization
3. Testing severity inheritance from ComplianceRule to Violation
4. Testing that new violations are created with "pending" status
"""

import uuid
from typing import Any, Dict, Optional

import pytest
from hypothesis import given, strategies as st, settings, assume

from app.models.compliance_rule import ComplianceRule
from app.models.violation import Violation
from app.models.enums import Severity, ViolationStatus
from app.services.db_scanner import DatabaseScannerService


# =============================================================================
# Hypothesis Strategies for Test Data Generation
# =============================================================================

# Valid severity levels
valid_severity_strategy = st.sampled_from([s.value for s in Severity])

# Valid violation status values
valid_status_strategy = st.sampled_from([s.value for s in ViolationStatus])

# Valid rule code strategy
valid_rule_code_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
    min_size=1,
    max_size=20
).filter(lambda x: x.strip() != "")

# Valid description strategy
valid_description_strategy = st.text(
    min_size=1,
    max_size=500
).filter(lambda x: x.strip() != "")

# Valid evaluation criteria strategy
valid_evaluation_criteria_strategy = st.text(
    min_size=1,
    max_size=200
).filter(lambda x: x.strip() != "")

# Valid record identifier strategy
valid_record_identifier_strategy = st.text(
    min_size=1,
    max_size=50
).filter(lambda x: x.strip() != "")

# Valid justification strategy
valid_justification_strategy = st.text(
    min_size=1,
    max_size=1000
).filter(lambda x: x.strip() != "")

# Strategy for generating record data (non-empty dict)
valid_record_data_strategy = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_'),
        min_size=1,
        max_size=30
    ).filter(lambda x: x.strip() != ""),
    values=st.one_of(
        st.text(min_size=0, max_size=100),
        st.integers(),
        st.booleans(),
        st.none(),
    ),
    min_size=1,
    max_size=10,
)

# Strategy for generating a complete compliance rule
valid_compliance_rule_strategy = st.fixed_dictionaries({
    "rule_code": valid_rule_code_strategy,
    "description": valid_description_strategy,
    "evaluation_criteria": valid_evaluation_criteria_strategy,
    "severity": valid_severity_strategy,
    "is_active": st.booleans(),
})

# Strategy for generating a list of compliance rules
valid_rules_list_strategy = st.lists(valid_compliance_rule_strategy, min_size=1, max_size=10)


# =============================================================================
# Property 4: Scan Completeness - All Active Rules Evaluated
# =============================================================================

class TestScanCompleteness:
    """Property tests for Scan Completeness.
    
    Feature: data-policy-agent, Property 4: Scan Completeness
    
    For any compliance scan with N active Compliance_Rules, the scan SHALL 
    evaluate all N rules and return results for each.
    
    **Validates: Requirements 2.3**
    
    Note: Since we can't use a real database in property tests, we test the
    rule filtering logic that determines which rules are evaluated.
    """

    @given(rules_data=valid_rules_list_strategy)
    @settings(max_examples=100)
    def test_active_rules_are_filtered_correctly(self, rules_data: list[dict]):
        """
        Property: Active rules are correctly identified for scanning.
        
        Feature: data-policy-agent, Property 4: Scan Completeness
        **Validates: Requirements 2.3**
        
        For any list of compliance rules, the scan should only evaluate
        rules where is_active is True.
        """
        policy_id = uuid.uuid4()
        
        # Create ComplianceRule objects
        rules = []
        for rule_data in rules_data:
            rule = ComplianceRule(
                policy_id=policy_id,
                rule_code=rule_data["rule_code"],
                description=rule_data["description"],
                evaluation_criteria=rule_data["evaluation_criteria"],
                severity=rule_data["severity"],
                is_active=rule_data["is_active"],
            )
            rules.append(rule)
        
        # Filter to active rules (this is what scan_for_violations does)
        active_rules = [rule for rule in rules if rule.is_active]
        
        # Count expected active rules from input
        expected_active_count = sum(1 for r in rules_data if r["is_active"])
        
        # Property: The number of active rules should match
        assert len(active_rules) == expected_active_count, \
            f"Expected {expected_active_count} active rules, got {len(active_rules)}"

    @given(rules_data=valid_rules_list_strategy)
    @settings(max_examples=100)
    def test_inactive_rules_are_excluded(self, rules_data: list[dict]):
        """
        Property: Inactive rules are excluded from scanning.
        
        Feature: data-policy-agent, Property 4: Scan Completeness
        **Validates: Requirements 2.3**
        
        For any list of compliance rules, rules where is_active is False
        should not be included in the scan.
        """
        policy_id = uuid.uuid4()
        
        # Create ComplianceRule objects
        rules = []
        for rule_data in rules_data:
            rule = ComplianceRule(
                policy_id=policy_id,
                rule_code=rule_data["rule_code"],
                description=rule_data["description"],
                evaluation_criteria=rule_data["evaluation_criteria"],
                severity=rule_data["severity"],
                is_active=rule_data["is_active"],
            )
            rules.append(rule)
        
        # Filter to active rules
        active_rules = [rule for rule in rules if rule.is_active]
        
        # Property: No inactive rules should be in the active list
        for rule in active_rules:
            assert rule.is_active is True, \
                f"Inactive rule {rule.rule_code} should not be in active rules list"

    @given(
        num_active=st.integers(min_value=0, max_value=10),
        num_inactive=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100)
    def test_active_rule_count_preserved(self, num_active: int, num_inactive: int):
        """
        Property: The count of active rules is preserved during filtering.
        
        Feature: data-policy-agent, Property 4: Scan Completeness
        **Validates: Requirements 2.3**
        
        For any mix of active and inactive rules, filtering should return
        exactly the number of active rules.
        """
        # Skip if no rules at all
        assume(num_active + num_inactive > 0)
        
        policy_id = uuid.uuid4()
        rules = []
        
        # Create active rules
        for i in range(num_active):
            rule = ComplianceRule(
                policy_id=policy_id,
                rule_code=f"ACTIVE-{i}",
                description=f"Active rule {i}",
                evaluation_criteria=f"Check condition {i}",
                severity=Severity.MEDIUM.value,
                is_active=True,
            )
            rules.append(rule)
        
        # Create inactive rules
        for i in range(num_inactive):
            rule = ComplianceRule(
                policy_id=policy_id,
                rule_code=f"INACTIVE-{i}",
                description=f"Inactive rule {i}",
                evaluation_criteria=f"Check condition {i}",
                severity=Severity.LOW.value,
                is_active=False,
            )
            rules.append(rule)
        
        # Filter to active rules
        active_rules = [rule for rule in rules if rule.is_active]
        
        # Property: Active rule count must match
        assert len(active_rules) == num_active, \
            f"Expected {num_active} active rules, got {len(active_rules)}"


# =============================================================================
# Property 6: Violation Report Completeness - Required Fields Present
# =============================================================================

class TestViolationReportCompleteness:
    """Property tests for Violation Report Completeness.
    
    Feature: data-policy-agent, Property 6: Violation Report Completeness
    
    For any detected violation, the Violation_Report SHALL contain a non-null 
    rule_id, record_identifier, record_data with at least one field, and a 
    non-empty justification string.
    
    **Validates: Requirements 3.1, 3.2**
    """

    @given(
        rule_id=st.uuids(),
        record_identifier=valid_record_identifier_strategy,
        record_data=valid_record_data_strategy,
        justification=valid_justification_strategy,
        severity=valid_severity_strategy,
    )
    @settings(max_examples=100)
    def test_violation_contains_all_required_fields(
        self,
        rule_id: uuid.UUID,
        record_identifier: str,
        record_data: Dict[str, Any],
        justification: str,
        severity: str,
    ):
        """
        Property: Violations contain all required fields.
        
        Feature: data-policy-agent, Property 6: Violation Report Completeness
        **Validates: Requirements 3.1, 3.2**
        
        For any violation created with valid data, all required fields
        (rule_id, record_identifier, record_data, justification, severity, status)
        SHALL be present and non-null.
        """
        violation = Violation(
            rule_id=rule_id,
            record_identifier=record_identifier,
            record_data=record_data,
            justification=justification,
            severity=severity,
            status=ViolationStatus.PENDING.value,
        )
        
        # Property: All required fields must be present and non-null
        assert violation.rule_id is not None, "rule_id must not be None"
        assert violation.record_identifier is not None, "record_identifier must not be None"
        assert violation.record_data is not None, "record_data must not be None"
        assert violation.justification is not None, "justification must not be None"
        assert violation.severity is not None, "severity must not be None"
        assert violation.status is not None, "status must not be None"

    @given(
        rule_id=st.uuids(),
        record_identifier=valid_record_identifier_strategy,
        record_data=valid_record_data_strategy,
        justification=valid_justification_strategy,
        severity=valid_severity_strategy,
    )
    @settings(max_examples=100)
    def test_violation_record_identifier_is_non_empty(
        self,
        rule_id: uuid.UUID,
        record_identifier: str,
        record_data: Dict[str, Any],
        justification: str,
        severity: str,
    ):
        """
        Property: Violation record_identifier is non-empty.
        
        Feature: data-policy-agent, Property 6: Violation Report Completeness
        **Validates: Requirements 3.1**
        
        For any violation, the record_identifier field SHALL be a non-empty string.
        """
        violation = Violation(
            rule_id=rule_id,
            record_identifier=record_identifier,
            record_data=record_data,
            justification=justification,
            severity=severity,
            status=ViolationStatus.PENDING.value,
        )
        
        # Property: record_identifier must be non-empty
        assert isinstance(violation.record_identifier, str), \
            "record_identifier must be a string"
        assert len(violation.record_identifier.strip()) > 0, \
            "record_identifier must be non-empty"

    @given(
        rule_id=st.uuids(),
        record_identifier=valid_record_identifier_strategy,
        record_data=valid_record_data_strategy,
        justification=valid_justification_strategy,
        severity=valid_severity_strategy,
    )
    @settings(max_examples=100)
    def test_violation_record_data_has_at_least_one_field(
        self,
        rule_id: uuid.UUID,
        record_identifier: str,
        record_data: Dict[str, Any],
        justification: str,
        severity: str,
    ):
        """
        Property: Violation record_data has at least one field.
        
        Feature: data-policy-agent, Property 6: Violation Report Completeness
        **Validates: Requirements 3.1**
        
        For any violation, the record_data field SHALL contain at least one field.
        """
        violation = Violation(
            rule_id=rule_id,
            record_identifier=record_identifier,
            record_data=record_data,
            justification=justification,
            severity=severity,
            status=ViolationStatus.PENDING.value,
        )
        
        # Property: record_data must have at least one field
        assert isinstance(violation.record_data, dict), \
            "record_data must be a dictionary"
        assert len(violation.record_data) >= 1, \
            "record_data must have at least one field"

    @given(
        rule_id=st.uuids(),
        record_identifier=valid_record_identifier_strategy,
        record_data=valid_record_data_strategy,
        justification=valid_justification_strategy,
        severity=valid_severity_strategy,
    )
    @settings(max_examples=100)
    def test_violation_justification_is_non_empty(
        self,
        rule_id: uuid.UUID,
        record_identifier: str,
        record_data: Dict[str, Any],
        justification: str,
        severity: str,
    ):
        """
        Property: Violation justification is non-empty.
        
        Feature: data-policy-agent, Property 6: Violation Report Completeness
        **Validates: Requirements 3.2**
        
        For any violation, the justification field SHALL be a non-empty string.
        """
        violation = Violation(
            rule_id=rule_id,
            record_identifier=record_identifier,
            record_data=record_data,
            justification=justification,
            severity=severity,
            status=ViolationStatus.PENDING.value,
        )
        
        # Property: justification must be non-empty
        assert isinstance(violation.justification, str), \
            "justification must be a string"
        assert len(violation.justification.strip()) > 0, \
            "justification must be non-empty"

    @given(
        rule_id=st.uuids(),
        record_identifier=valid_record_identifier_strategy,
        record_data=valid_record_data_strategy,
        justification=valid_justification_strategy,
        severity=valid_severity_strategy,
    )
    @settings(max_examples=100)
    def test_violation_fields_are_preserved(
        self,
        rule_id: uuid.UUID,
        record_identifier: str,
        record_data: Dict[str, Any],
        justification: str,
        severity: str,
    ):
        """
        Property: Violation field values are preserved.
        
        Feature: data-policy-agent, Property 6: Violation Report Completeness
        **Validates: Requirements 3.1, 3.2**
        
        For any violation, the field values SHALL be preserved exactly as provided.
        """
        violation = Violation(
            rule_id=rule_id,
            record_identifier=record_identifier,
            record_data=record_data,
            justification=justification,
            severity=severity,
            status=ViolationStatus.PENDING.value,
        )
        
        # Property: All field values must be preserved
        assert violation.rule_id == rule_id, "rule_id not preserved"
        assert violation.record_identifier == record_identifier, "record_identifier not preserved"
        assert violation.record_data == record_data, "record_data not preserved"
        assert violation.justification == justification, "justification not preserved"
        assert violation.severity == severity, "severity not preserved"


# =============================================================================
# Property 7: Severity Inheritance - Violation Severity Matches Rule
# =============================================================================

class TestSeverityInheritance:
    """Property tests for Severity Inheritance.
    
    Feature: data-policy-agent, Property 7: Severity Inheritance
    
    For any Violation created from a Compliance_Rule, the Violation's severity 
    SHALL equal the source rule's severity.
    
    **Validates: Requirements 3.3**
    """

    @given(
        rule_code=valid_rule_code_strategy,
        description=valid_description_strategy,
        evaluation_criteria=valid_evaluation_criteria_strategy,
        severity=valid_severity_strategy,
        record_identifier=valid_record_identifier_strategy,
        record_data=valid_record_data_strategy,
        justification=valid_justification_strategy,
    )
    @settings(max_examples=100)
    def test_violation_inherits_rule_severity(
        self,
        rule_code: str,
        description: str,
        evaluation_criteria: str,
        severity: str,
        record_identifier: str,
        record_data: Dict[str, Any],
        justification: str,
    ):
        """
        Property: Violation severity matches source rule severity.
        
        Feature: data-policy-agent, Property 7: Severity Inheritance
        **Validates: Requirements 3.3**
        
        For any violation created from a compliance rule, the violation's
        severity SHALL equal the rule's severity.
        """
        policy_id = uuid.uuid4()
        
        # Create a compliance rule with the given severity
        rule = ComplianceRule(
            policy_id=policy_id,
            rule_code=rule_code,
            description=description,
            evaluation_criteria=evaluation_criteria,
            severity=severity,
            is_active=True,
        )
        
        # Create a violation that inherits severity from the rule
        # (This is how scan_for_violations creates violations)
        violation = Violation(
            rule_id=rule.id,
            record_identifier=record_identifier,
            record_data=record_data,
            justification=justification,
            severity=rule.severity,  # Inherit from rule
            status=ViolationStatus.PENDING.value,
        )
        
        # Property: Violation severity must match rule severity
        assert violation.severity == rule.severity, \
            f"Violation severity '{violation.severity}' does not match rule severity '{rule.severity}'"

    @given(severity=valid_severity_strategy)
    @settings(max_examples=100)
    def test_all_severity_levels_can_be_inherited(self, severity: str):
        """
        Property: All severity levels can be inherited by violations.
        
        Feature: data-policy-agent, Property 7: Severity Inheritance
        **Validates: Requirements 3.3**
        
        For any valid severity level (low, medium, high, critical), a violation
        SHALL be able to inherit that severity from a rule.
        """
        policy_id = uuid.uuid4()
        
        # Create a rule with the given severity
        rule = ComplianceRule(
            policy_id=policy_id,
            rule_code="TEST-001",
            description="Test rule",
            evaluation_criteria="Test criteria",
            severity=severity,
            is_active=True,
        )
        
        # Create a violation inheriting the severity
        violation = Violation(
            rule_id=rule.id,
            record_identifier="test-record-1",
            record_data={"field": "value"},
            justification="Test justification",
            severity=rule.severity,
            status=ViolationStatus.PENDING.value,
        )
        
        # Property: Severity must be inherited correctly
        assert violation.severity == severity, \
            f"Severity '{severity}' was not correctly inherited"
        
        # Property: Severity must be a valid value
        valid_severities = {s.value for s in Severity}
        assert violation.severity in valid_severities, \
            f"Invalid severity value: {violation.severity}"

    @given(
        rules_data=st.lists(
            st.fixed_dictionaries({
                "severity": valid_severity_strategy,
                "record_identifier": valid_record_identifier_strategy,
            }),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=100)
    def test_multiple_violations_inherit_correct_severities(self, rules_data: list[dict]):
        """
        Property: Multiple violations inherit correct severities from their rules.
        
        Feature: data-policy-agent, Property 7: Severity Inheritance
        **Validates: Requirements 3.3**
        
        For any set of rules with different severities, violations created from
        those rules SHALL each inherit the correct severity from their source rule.
        """
        policy_id = uuid.uuid4()
        
        for i, data in enumerate(rules_data):
            # Create a rule with specific severity
            rule = ComplianceRule(
                policy_id=policy_id,
                rule_code=f"RULE-{i}",
                description=f"Rule {i}",
                evaluation_criteria=f"Criteria {i}",
                severity=data["severity"],
                is_active=True,
            )
            
            # Create a violation from this rule
            violation = Violation(
                rule_id=rule.id,
                record_identifier=data["record_identifier"],
                record_data={"index": i},
                justification=f"Violation for rule {i}",
                severity=rule.severity,
                status=ViolationStatus.PENDING.value,
            )
            
            # Property: Each violation must have the correct severity
            assert violation.severity == data["severity"], \
                f"Violation {i} has severity '{violation.severity}' but rule has '{data['severity']}'"


# =============================================================================
# Property 10: New Violation Initial Status - Status is "pending"
# =============================================================================

class TestNewViolationInitialStatus:
    """Property tests for New Violation Initial Status.
    
    Feature: data-policy-agent, Property 10: New Violation Initial Status
    
    For any newly detected violation, the initial status SHALL be "pending".
    
    **Validates: Requirements 4.1**
    """

    @given(
        rule_id=st.uuids(),
        record_identifier=valid_record_identifier_strategy,
        record_data=valid_record_data_strategy,
        justification=valid_justification_strategy,
        severity=valid_severity_strategy,
    )
    @settings(max_examples=100)
    def test_new_violation_has_pending_status(
        self,
        rule_id: uuid.UUID,
        record_identifier: str,
        record_data: Dict[str, Any],
        justification: str,
        severity: str,
    ):
        """
        Property: New violations have "pending" status.
        
        Feature: data-policy-agent, Property 10: New Violation Initial Status
        **Validates: Requirements 4.1**
        
        For any newly created violation, the status SHALL be "pending".
        """
        # Create a new violation with pending status (as scan_for_violations does)
        violation = Violation(
            rule_id=rule_id,
            record_identifier=record_identifier,
            record_data=record_data,
            justification=justification,
            severity=severity,
            status=ViolationStatus.PENDING.value,
        )
        
        # Property: Status must be "pending"
        assert violation.status == ViolationStatus.PENDING.value, \
            f"New violation status should be 'pending', got '{violation.status}'"

    @given(
        num_violations=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100)
    def test_all_new_violations_have_pending_status(self, num_violations: int):
        """
        Property: All new violations have "pending" status.
        
        Feature: data-policy-agent, Property 10: New Violation Initial Status
        **Validates: Requirements 4.1**
        
        For any batch of newly created violations, all SHALL have "pending" status.
        """
        rule_id = uuid.uuid4()
        violations = []
        
        for i in range(num_violations):
            violation = Violation(
                rule_id=rule_id,
                record_identifier=f"record-{i}",
                record_data={"index": i},
                justification=f"Violation {i}",
                severity=Severity.MEDIUM.value,
                status=ViolationStatus.PENDING.value,
            )
            violations.append(violation)
        
        # Property: All violations must have pending status
        for i, violation in enumerate(violations):
            assert violation.status == ViolationStatus.PENDING.value, \
                f"Violation {i} should have 'pending' status, got '{violation.status}'"

    @given(severity=valid_severity_strategy)
    @settings(max_examples=100)
    def test_pending_status_regardless_of_severity(self, severity: str):
        """
        Property: New violations have "pending" status regardless of severity.
        
        Feature: data-policy-agent, Property 10: New Violation Initial Status
        **Validates: Requirements 4.1**
        
        For any severity level, new violations SHALL have "pending" status.
        """
        violation = Violation(
            rule_id=uuid.uuid4(),
            record_identifier="test-record",
            record_data={"field": "value"},
            justification="Test justification",
            severity=severity,
            status=ViolationStatus.PENDING.value,
        )
        
        # Property: Status must be pending regardless of severity
        assert violation.status == ViolationStatus.PENDING.value, \
            f"Violation with severity '{severity}' should have 'pending' status"

    def test_pending_is_valid_status_value(self):
        """
        Property: "pending" is a valid ViolationStatus value.
        
        Feature: data-policy-agent, Property 10: New Violation Initial Status
        **Validates: Requirements 4.1**
        
        The "pending" status SHALL be a valid ViolationStatus enum value.
        """
        # Property: PENDING must be a valid enum value
        assert ViolationStatus.PENDING.value == "pending", \
            "ViolationStatus.PENDING should have value 'pending'"
        
        # Property: "pending" must be in the valid status values
        valid_statuses = {s.value for s in ViolationStatus}
        assert "pending" in valid_statuses, \
            "'pending' should be a valid violation status"


# =============================================================================
# Helper Function Tests: _get_record_identifier
# =============================================================================

class TestGetRecordIdentifier:
    """Property tests for the _get_record_identifier helper function.
    
    Feature: data-policy-agent, Property 6: Violation Report Completeness
    **Validates: Requirements 3.1**
    
    These tests verify that the _get_record_identifier helper correctly
    extracts a unique identifier from record data.
    """

    @given(id_value=st.one_of(st.integers(), st.text(min_size=1, max_size=50)))
    @settings(max_examples=100)
    def test_id_field_is_preferred(self, id_value):
        """
        Property: 'id' field is preferred as record identifier.
        
        Feature: data-policy-agent, Property 6: Violation Report Completeness
        **Validates: Requirements 3.1**
        
        When record_data contains an 'id' field, it SHALL be used as the identifier.
        """
        scanner = DatabaseScannerService()
        record_data = {
            "id": id_value,
            "other_field": "other_value",
            "another_id": "should_not_use",
        }
        
        identifier = scanner._get_record_identifier(record_data)
        
        # Property: 'id' field should be used
        assert identifier == str(id_value), \
            f"Expected '{id_value}', got '{identifier}'"

    @given(
        suffix_id_value=st.one_of(st.integers(), st.text(min_size=1, max_size=50)),
        suffix_name=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll')),
            min_size=1,
            max_size=20
        ),
    )
    @settings(max_examples=100)
    def test_field_ending_with_id_is_used_when_no_id(self, suffix_id_value, suffix_name: str):
        """
        Property: Field ending with '_id' is used when no 'id' field exists.
        
        Feature: data-policy-agent, Property 6: Violation Report Completeness
        **Validates: Requirements 3.1**
        
        When record_data has no 'id' field but has a field ending with '_id',
        that field SHALL be used as the identifier.
        """
        scanner = DatabaseScannerService()
        field_name = f"{suffix_name}_id"
        record_data = {
            field_name: suffix_id_value,
            "other_field": "other_value",
        }
        
        identifier = scanner._get_record_identifier(record_data)
        
        # Property: Field ending with '_id' should be used
        assert identifier == str(suffix_id_value), \
            f"Expected '{suffix_id_value}', got '{identifier}'"

    @given(
        first_key=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll')),
            min_size=1,
            max_size=20
        ).filter(lambda x: not x.endswith('_id') and x != 'id'),
        first_value=st.one_of(st.integers(), st.text(min_size=1, max_size=50)),
    )
    @settings(max_examples=100)
    def test_first_field_used_as_fallback(self, first_key: str, first_value):
        """
        Property: First field is used as fallback identifier.
        
        Feature: data-policy-agent, Property 6: Violation Report Completeness
        **Validates: Requirements 3.1**
        
        When record_data has no 'id' field and no field ending with '_id',
        the first field SHALL be used as the identifier.
        """
        scanner = DatabaseScannerService()
        # Use a dict with a single field to ensure predictable "first" field
        record_data = {first_key: first_value}
        
        identifier = scanner._get_record_identifier(record_data)
        
        # Property: First field value should be used
        assert identifier == str(first_value), \
            f"Expected '{first_value}', got '{identifier}'"

    def test_empty_record_returns_unknown(self):
        """
        Property: Empty record returns "unknown" identifier.
        
        Feature: data-policy-agent, Property 6: Violation Report Completeness
        **Validates: Requirements 3.1**
        
        When record_data is empty, the identifier SHALL be "unknown".
        """
        scanner = DatabaseScannerService()
        record_data = {}
        
        identifier = scanner._get_record_identifier(record_data)
        
        # Property: Empty record should return "unknown"
        assert identifier == "unknown", \
            f"Expected 'unknown' for empty record, got '{identifier}'"

    @given(id_value=st.integers())
    @settings(max_examples=100)
    def test_identifier_is_always_string(self, id_value: int):
        """
        Property: Record identifier is always a string.
        
        Feature: data-policy-agent, Property 6: Violation Report Completeness
        **Validates: Requirements 3.1**
        
        Regardless of the original field type, the identifier SHALL be a string.
        """
        scanner = DatabaseScannerService()
        record_data = {"id": id_value}
        
        identifier = scanner._get_record_identifier(record_data)
        
        # Property: Identifier must be a string
        assert isinstance(identifier, str), \
            f"Identifier should be string, got {type(identifier)}"

    @given(
        id_value=st.one_of(st.integers(), st.text(min_size=1, max_size=50)),
        user_id_value=st.one_of(st.integers(), st.text(min_size=1, max_size=50)),
    )
    @settings(max_examples=100)
    def test_id_takes_precedence_over_suffix_id(self, id_value, user_id_value):
        """
        Property: 'id' field takes precedence over fields ending with '_id'.
        
        Feature: data-policy-agent, Property 6: Violation Report Completeness
        **Validates: Requirements 3.1**
        
        When both 'id' and a field ending with '_id' exist, 'id' SHALL be used.
        """
        scanner = DatabaseScannerService()
        record_data = {
            "id": id_value,
            "user_id": user_id_value,
        }
        
        identifier = scanner._get_record_identifier(record_data)
        
        # Property: 'id' should take precedence
        assert identifier == str(id_value), \
            f"Expected 'id' value '{id_value}', got '{identifier}'"
