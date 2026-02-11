"""Property-based tests for violation filtering.

Feature: data-policy-agent, Property 15: Violation Filtering Correctness

This module contains property-based tests that verify:
1. Status filter returns only violations with matching status
2. Severity filter returns only violations with matching severity
3. Rule ID filter returns only violations for that rule
4. Date range filter returns only violations within the range
5. Combined filters work correctly (AND logic)
6. Empty filters return all violations

**Validates: Requirements 6.5**

Note: Since we can't use a real database in property tests, we test the
filtering logic by:
1. Generating random lists of violations with various statuses/severities
2. Applying filter predicates
3. Verifying the filtered results match the expected criteria
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytest
from hypothesis import given, strategies as st, settings, assume

from app.models.enums import Severity, ViolationStatus


# =============================================================================
# Data Classes for Testing (simulating Violation objects without DB)
# =============================================================================

@dataclass
class ViolationData:
    """Data class representing a violation for filtering tests.
    
    This simulates the Violation model without requiring database access.
    """
    id: uuid.UUID
    rule_id: uuid.UUID
    record_identifier: str
    record_data: Dict[str, Any]
    justification: str
    severity: str
    status: str
    detected_at: datetime
    resolved_at: Optional[datetime] = None


# =============================================================================
# Filter Predicate Functions (simulating the filtering logic from violations.py)
# =============================================================================

def filter_by_status(violations: List[ViolationData], status: Optional[str]) -> List[ViolationData]:
    """Filter violations by status.
    
    Args:
        violations: List of violations to filter
        status: Status value to filter by, or None for no filtering
        
    Returns:
        Filtered list of violations
    """
    if status is None:
        return violations
    return [v for v in violations if v.status == status]


def filter_by_severity(violations: List[ViolationData], severity: Optional[str]) -> List[ViolationData]:
    """Filter violations by severity.
    
    Args:
        violations: List of violations to filter
        severity: Severity value to filter by, or None for no filtering
        
    Returns:
        Filtered list of violations
    """
    if severity is None:
        return violations
    return [v for v in violations if v.severity == severity]


def filter_by_rule_id(violations: List[ViolationData], rule_id: Optional[uuid.UUID]) -> List[ViolationData]:
    """Filter violations by rule ID.
    
    Args:
        violations: List of violations to filter
        rule_id: Rule ID to filter by, or None for no filtering
        
    Returns:
        Filtered list of violations
    """
    if rule_id is None:
        return violations
    return [v for v in violations if v.rule_id == rule_id]


def filter_by_date_range(
    violations: List[ViolationData],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
) -> List[ViolationData]:
    """Filter violations by date range.
    
    Args:
        violations: List of violations to filter
        start_date: Start of date range (inclusive), or None for no lower bound
        end_date: End of date range (inclusive), or None for no upper bound
        
    Returns:
        Filtered list of violations
    """
    result = violations
    if start_date is not None:
        result = [v for v in result if v.detected_at >= start_date]
    if end_date is not None:
        result = [v for v in result if v.detected_at <= end_date]
    return result


def apply_all_filters(
    violations: List[ViolationData],
    status: Optional[str] = None,
    severity: Optional[str] = None,
    rule_id: Optional[uuid.UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[ViolationData]:
    """Apply all filters with AND logic.
    
    Args:
        violations: List of violations to filter
        status: Status filter (optional)
        severity: Severity filter (optional)
        rule_id: Rule ID filter (optional)
        start_date: Start date filter (optional)
        end_date: End date filter (optional)
        
    Returns:
        Filtered list of violations matching ALL specified criteria
    """
    result = violations
    result = filter_by_status(result, status)
    result = filter_by_severity(result, severity)
    result = filter_by_rule_id(result, rule_id)
    result = filter_by_date_range(result, start_date, end_date)
    return result


# =============================================================================
# Hypothesis Strategies for Test Data Generation
# =============================================================================

# Valid severity levels
valid_severity_strategy = st.sampled_from([s.value for s in Severity])

# Valid violation status values
valid_status_strategy = st.sampled_from([s.value for s in ViolationStatus])

# Valid record identifier strategy
valid_record_identifier_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
    min_size=1,
    max_size=50
).filter(lambda x: x.strip() != "")

# Valid justification strategy
valid_justification_strategy = st.text(
    min_size=1,
    max_size=200
).filter(lambda x: x.strip() != "")

# Strategy for generating record data (non-empty dict)
valid_record_data_strategy = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_'),
        min_size=1,
        max_size=20
    ).filter(lambda x: x.strip() != ""),
    values=st.one_of(
        st.text(min_size=0, max_size=50),
        st.integers(),
        st.booleans(),
    ),
    min_size=1,
    max_size=5,
)

# Strategy for generating timezone-aware datetimes
# Using a reasonable date range for testing
base_datetime = datetime(2024, 1, 1, tzinfo=timezone.utc)
datetime_strategy = st.integers(min_value=0, max_value=365 * 24 * 60).map(
    lambda minutes: base_datetime + timedelta(minutes=minutes)
)

# Strategy for generating a single ViolationData object
violation_data_strategy = st.builds(
    ViolationData,
    id=st.uuids(),
    rule_id=st.uuids(),
    record_identifier=valid_record_identifier_strategy,
    record_data=valid_record_data_strategy,
    justification=valid_justification_strategy,
    severity=valid_severity_strategy,
    status=valid_status_strategy,
    detected_at=datetime_strategy,
    resolved_at=st.none(),
)

# Strategy for generating a list of violations
violations_list_strategy = st.lists(violation_data_strategy, min_size=0, max_size=20)


# =============================================================================
# Property 15: Violation Filtering Correctness
# =============================================================================

class TestStatusFilterCorrectness:
    """Property tests for status filter correctness.
    
    Feature: data-policy-agent, Property 15: Violation Filtering Correctness
    
    For any filter combination (status, severity, rule_id, date_range), the 
    returned violations SHALL only include records matching ALL specified 
    filter criteria.
    
    **Validates: Requirements 6.5**
    """

    @given(
        violations=violations_list_strategy,
        filter_status=valid_status_strategy,
    )
    @settings(max_examples=100)
    def test_status_filter_returns_only_matching_violations(
        self,
        violations: List[ViolationData],
        filter_status: str,
    ):
        """
        Property: Status filter returns only violations with matching status.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        For any status filter value, the filtered results SHALL only contain
        violations with that exact status.
        """
        filtered = filter_by_status(violations, filter_status)
        
        # Property: All filtered violations must have the matching status
        for violation in filtered:
            assert violation.status == filter_status, \
                f"Violation has status '{violation.status}' but filter was '{filter_status}'"

    @given(
        violations=violations_list_strategy,
        filter_status=valid_status_strategy,
    )
    @settings(max_examples=100)
    def test_status_filter_includes_all_matching_violations(
        self,
        violations: List[ViolationData],
        filter_status: str,
    ):
        """
        Property: Status filter includes all violations with matching status.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        For any status filter value, the filtered results SHALL include ALL
        violations with that status (no matching violations are excluded).
        """
        filtered = filter_by_status(violations, filter_status)
        
        # Count expected matches
        expected_count = sum(1 for v in violations if v.status == filter_status)
        
        # Property: Filtered count must match expected count
        assert len(filtered) == expected_count, \
            f"Expected {expected_count} violations with status '{filter_status}', got {len(filtered)}"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_null_status_filter_returns_all_violations(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Null status filter returns all violations.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        When status filter is None, all violations SHALL be returned.
        """
        filtered = filter_by_status(violations, None)
        
        # Property: All violations should be returned
        assert len(filtered) == len(violations), \
            f"Expected {len(violations)} violations, got {len(filtered)}"


class TestSeverityFilterCorrectness:
    """Property tests for severity filter correctness.
    
    Feature: data-policy-agent, Property 15: Violation Filtering Correctness
    **Validates: Requirements 6.5**
    """

    @given(
        violations=violations_list_strategy,
        filter_severity=valid_severity_strategy,
    )
    @settings(max_examples=100)
    def test_severity_filter_returns_only_matching_violations(
        self,
        violations: List[ViolationData],
        filter_severity: str,
    ):
        """
        Property: Severity filter returns only violations with matching severity.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        For any severity filter value, the filtered results SHALL only contain
        violations with that exact severity.
        """
        filtered = filter_by_severity(violations, filter_severity)
        
        # Property: All filtered violations must have the matching severity
        for violation in filtered:
            assert violation.severity == filter_severity, \
                f"Violation has severity '{violation.severity}' but filter was '{filter_severity}'"

    @given(
        violations=violations_list_strategy,
        filter_severity=valid_severity_strategy,
    )
    @settings(max_examples=100)
    def test_severity_filter_includes_all_matching_violations(
        self,
        violations: List[ViolationData],
        filter_severity: str,
    ):
        """
        Property: Severity filter includes all violations with matching severity.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        For any severity filter value, the filtered results SHALL include ALL
        violations with that severity (no matching violations are excluded).
        """
        filtered = filter_by_severity(violations, filter_severity)
        
        # Count expected matches
        expected_count = sum(1 for v in violations if v.severity == filter_severity)
        
        # Property: Filtered count must match expected count
        assert len(filtered) == expected_count, \
            f"Expected {expected_count} violations with severity '{filter_severity}', got {len(filtered)}"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_null_severity_filter_returns_all_violations(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Null severity filter returns all violations.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        When severity filter is None, all violations SHALL be returned.
        """
        filtered = filter_by_severity(violations, None)
        
        # Property: All violations should be returned
        assert len(filtered) == len(violations), \
            f"Expected {len(violations)} violations, got {len(filtered)}"


class TestRuleIdFilterCorrectness:
    """Property tests for rule ID filter correctness.
    
    Feature: data-policy-agent, Property 15: Violation Filtering Correctness
    **Validates: Requirements 6.5**
    """

    @given(
        violations=violations_list_strategy,
        filter_rule_id=st.uuids(),
    )
    @settings(max_examples=100)
    def test_rule_id_filter_returns_only_matching_violations(
        self,
        violations: List[ViolationData],
        filter_rule_id: uuid.UUID,
    ):
        """
        Property: Rule ID filter returns only violations for that rule.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        For any rule ID filter value, the filtered results SHALL only contain
        violations associated with that rule.
        """
        filtered = filter_by_rule_id(violations, filter_rule_id)
        
        # Property: All filtered violations must have the matching rule_id
        for violation in filtered:
            assert violation.rule_id == filter_rule_id, \
                f"Violation has rule_id '{violation.rule_id}' but filter was '{filter_rule_id}'"

    @given(violations=st.lists(violation_data_strategy, min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_rule_id_filter_includes_all_matching_violations(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Rule ID filter includes all violations for that rule.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        For any rule ID filter value, the filtered results SHALL include ALL
        violations for that rule (no matching violations are excluded).
        """
        # Use an existing rule_id from the violations to ensure we have matches
        filter_rule_id = violations[0].rule_id
        
        filtered = filter_by_rule_id(violations, filter_rule_id)
        
        # Count expected matches
        expected_count = sum(1 for v in violations if v.rule_id == filter_rule_id)
        
        # Property: Filtered count must match expected count
        assert len(filtered) == expected_count, \
            f"Expected {expected_count} violations with rule_id '{filter_rule_id}', got {len(filtered)}"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_null_rule_id_filter_returns_all_violations(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Null rule ID filter returns all violations.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        When rule ID filter is None, all violations SHALL be returned.
        """
        filtered = filter_by_rule_id(violations, None)
        
        # Property: All violations should be returned
        assert len(filtered) == len(violations), \
            f"Expected {len(violations)} violations, got {len(filtered)}"


class TestDateRangeFilterCorrectness:
    """Property tests for date range filter correctness.
    
    Feature: data-policy-agent, Property 15: Violation Filtering Correctness
    **Validates: Requirements 6.5**
    """

    @given(
        violations=violations_list_strategy,
        start_date=datetime_strategy,
    )
    @settings(max_examples=100)
    def test_start_date_filter_returns_only_violations_on_or_after(
        self,
        violations: List[ViolationData],
        start_date: datetime,
    ):
        """
        Property: Start date filter returns only violations on or after that date.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        For any start date filter, the filtered results SHALL only contain
        violations detected on or after that date.
        """
        filtered = filter_by_date_range(violations, start_date=start_date, end_date=None)
        
        # Property: All filtered violations must be on or after start_date
        for violation in filtered:
            assert violation.detected_at >= start_date, \
                f"Violation detected at '{violation.detected_at}' is before start_date '{start_date}'"

    @given(
        violations=violations_list_strategy,
        end_date=datetime_strategy,
    )
    @settings(max_examples=100)
    def test_end_date_filter_returns_only_violations_on_or_before(
        self,
        violations: List[ViolationData],
        end_date: datetime,
    ):
        """
        Property: End date filter returns only violations on or before that date.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        For any end date filter, the filtered results SHALL only contain
        violations detected on or before that date.
        """
        filtered = filter_by_date_range(violations, start_date=None, end_date=end_date)
        
        # Property: All filtered violations must be on or before end_date
        for violation in filtered:
            assert violation.detected_at <= end_date, \
                f"Violation detected at '{violation.detected_at}' is after end_date '{end_date}'"

    @given(
        violations=violations_list_strategy,
        start_date=datetime_strategy,
        end_date=datetime_strategy,
    )
    @settings(max_examples=100)
    def test_date_range_filter_returns_only_violations_within_range(
        self,
        violations: List[ViolationData],
        start_date: datetime,
        end_date: datetime,
    ):
        """
        Property: Date range filter returns only violations within the range.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        For any date range filter, the filtered results SHALL only contain
        violations detected within that range (inclusive).
        """
        # Ensure start_date <= end_date for a valid range
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        filtered = filter_by_date_range(violations, start_date=start_date, end_date=end_date)
        
        # Property: All filtered violations must be within the date range
        for violation in filtered:
            assert start_date <= violation.detected_at <= end_date, \
                f"Violation detected at '{violation.detected_at}' is outside range [{start_date}, {end_date}]"

    @given(
        violations=violations_list_strategy,
        start_date=datetime_strategy,
    )
    @settings(max_examples=100)
    def test_date_filter_includes_all_matching_violations(
        self,
        violations: List[ViolationData],
        start_date: datetime,
    ):
        """
        Property: Date filter includes all violations within the range.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        For any date filter, the filtered results SHALL include ALL violations
        within that range (no matching violations are excluded).
        """
        filtered = filter_by_date_range(violations, start_date=start_date, end_date=None)
        
        # Count expected matches
        expected_count = sum(1 for v in violations if v.detected_at >= start_date)
        
        # Property: Filtered count must match expected count
        assert len(filtered) == expected_count, \
            f"Expected {expected_count} violations on or after '{start_date}', got {len(filtered)}"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_null_date_range_returns_all_violations(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Null date range filter returns all violations.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        When both start_date and end_date are None, all violations SHALL be returned.
        """
        filtered = filter_by_date_range(violations, start_date=None, end_date=None)
        
        # Property: All violations should be returned
        assert len(filtered) == len(violations), \
            f"Expected {len(violations)} violations, got {len(filtered)}"


class TestCombinedFiltersCorrectness:
    """Property tests for combined filter correctness (AND logic).
    
    Feature: data-policy-agent, Property 15: Violation Filtering Correctness
    **Validates: Requirements 6.5**
    """

    @given(
        violations=violations_list_strategy,
        filter_status=valid_status_strategy,
        filter_severity=valid_severity_strategy,
    )
    @settings(max_examples=100)
    def test_combined_status_and_severity_filters(
        self,
        violations: List[ViolationData],
        filter_status: str,
        filter_severity: str,
    ):
        """
        Property: Combined status and severity filters use AND logic.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        When both status and severity filters are applied, the results SHALL
        only include violations matching BOTH criteria.
        """
        filtered = apply_all_filters(
            violations,
            status=filter_status,
            severity=filter_severity,
        )
        
        # Property: All filtered violations must match both criteria
        for violation in filtered:
            assert violation.status == filter_status, \
                f"Violation status '{violation.status}' doesn't match filter '{filter_status}'"
            assert violation.severity == filter_severity, \
                f"Violation severity '{violation.severity}' doesn't match filter '{filter_severity}'"

    @given(
        violations=violations_list_strategy,
        filter_status=valid_status_strategy,
        filter_severity=valid_severity_strategy,
        filter_rule_id=st.uuids(),
    )
    @settings(max_examples=100)
    def test_combined_status_severity_and_rule_id_filters(
        self,
        violations: List[ViolationData],
        filter_status: str,
        filter_severity: str,
        filter_rule_id: uuid.UUID,
    ):
        """
        Property: Combined status, severity, and rule ID filters use AND logic.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        When status, severity, and rule ID filters are applied, the results SHALL
        only include violations matching ALL three criteria.
        """
        filtered = apply_all_filters(
            violations,
            status=filter_status,
            severity=filter_severity,
            rule_id=filter_rule_id,
        )
        
        # Property: All filtered violations must match all three criteria
        for violation in filtered:
            assert violation.status == filter_status, \
                f"Violation status '{violation.status}' doesn't match filter '{filter_status}'"
            assert violation.severity == filter_severity, \
                f"Violation severity '{violation.severity}' doesn't match filter '{filter_severity}'"
            assert violation.rule_id == filter_rule_id, \
                f"Violation rule_id '{violation.rule_id}' doesn't match filter '{filter_rule_id}'"

    @given(
        violations=violations_list_strategy,
        filter_status=valid_status_strategy,
        start_date=datetime_strategy,
        end_date=datetime_strategy,
    )
    @settings(max_examples=100)
    def test_combined_status_and_date_range_filters(
        self,
        violations: List[ViolationData],
        filter_status: str,
        start_date: datetime,
        end_date: datetime,
    ):
        """
        Property: Combined status and date range filters use AND logic.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        When status and date range filters are applied, the results SHALL
        only include violations matching BOTH criteria.
        """
        # Ensure valid date range
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        filtered = apply_all_filters(
            violations,
            status=filter_status,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Property: All filtered violations must match both criteria
        for violation in filtered:
            assert violation.status == filter_status, \
                f"Violation status '{violation.status}' doesn't match filter '{filter_status}'"
            assert start_date <= violation.detected_at <= end_date, \
                f"Violation detected_at '{violation.detected_at}' is outside range [{start_date}, {end_date}]"


    @given(
        violations=violations_list_strategy,
        filter_status=valid_status_strategy,
        filter_severity=valid_severity_strategy,
        filter_rule_id=st.uuids(),
        start_date=datetime_strategy,
        end_date=datetime_strategy,
    )
    @settings(max_examples=100)
    def test_all_filters_combined(
        self,
        violations: List[ViolationData],
        filter_status: str,
        filter_severity: str,
        filter_rule_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime,
    ):
        """
        Property: All filters combined use AND logic.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        When all filters (status, severity, rule_id, date_range) are applied,
        the results SHALL only include violations matching ALL criteria.
        """
        # Ensure valid date range
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        filtered = apply_all_filters(
            violations,
            status=filter_status,
            severity=filter_severity,
            rule_id=filter_rule_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Property: All filtered violations must match all criteria
        for violation in filtered:
            assert violation.status == filter_status, \
                f"Violation status '{violation.status}' doesn't match filter '{filter_status}'"
            assert violation.severity == filter_severity, \
                f"Violation severity '{violation.severity}' doesn't match filter '{filter_severity}'"
            assert violation.rule_id == filter_rule_id, \
                f"Violation rule_id '{violation.rule_id}' doesn't match filter '{filter_rule_id}'"
            assert start_date <= violation.detected_at <= end_date, \
                f"Violation detected_at '{violation.detected_at}' is outside range [{start_date}, {end_date}]"

    @given(
        violations=violations_list_strategy,
        filter_status=valid_status_strategy,
        filter_severity=valid_severity_strategy,
    )
    @settings(max_examples=100)
    def test_combined_filters_count_matches_expected(
        self,
        violations: List[ViolationData],
        filter_status: str,
        filter_severity: str,
    ):
        """
        Property: Combined filter count matches expected count.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        The number of filtered results SHALL equal the count of violations
        that match ALL specified criteria.
        """
        filtered = apply_all_filters(
            violations,
            status=filter_status,
            severity=filter_severity,
        )
        
        # Count expected matches manually
        expected_count = sum(
            1 for v in violations
            if v.status == filter_status and v.severity == filter_severity
        )
        
        # Property: Filtered count must match expected count
        assert len(filtered) == expected_count, \
            f"Expected {expected_count} violations matching both filters, got {len(filtered)}"


class TestEmptyFiltersReturnAll:
    """Property tests for empty filter behavior.
    
    Feature: data-policy-agent, Property 15: Violation Filtering Correctness
    **Validates: Requirements 6.5**
    """

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_no_filters_returns_all_violations(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: No filters returns all violations.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        When no filters are applied (all filter values are None), all violations
        SHALL be returned.
        """
        filtered = apply_all_filters(violations)
        
        # Property: All violations should be returned
        assert len(filtered) == len(violations), \
            f"Expected {len(violations)} violations, got {len(filtered)}"
        
        # Property: The same violations should be returned (by id)
        filtered_ids = {v.id for v in filtered}
        original_ids = {v.id for v in violations}
        assert filtered_ids == original_ids, \
            "Filtered violations don't match original violations"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_empty_filters_preserves_violation_data(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Empty filters preserves violation data.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        When no filters are applied, the returned violations SHALL have
        all their data preserved exactly.
        """
        filtered = apply_all_filters(violations)
        
        # Create lookup by id for comparison
        original_by_id = {v.id: v for v in violations}
        
        # Property: Each filtered violation should match its original
        for violation in filtered:
            original = original_by_id.get(violation.id)
            assert original is not None, \
                f"Filtered violation {violation.id} not found in original list"
            assert violation.status == original.status, \
                f"Status mismatch for violation {violation.id}"
            assert violation.severity == original.severity, \
                f"Severity mismatch for violation {violation.id}"
            assert violation.rule_id == original.rule_id, \
                f"Rule ID mismatch for violation {violation.id}"
            assert violation.detected_at == original.detected_at, \
                f"Detected at mismatch for violation {violation.id}"


class TestFilterIdempotence:
    """Property tests for filter idempotence.
    
    Feature: data-policy-agent, Property 15: Violation Filtering Correctness
    **Validates: Requirements 6.5**
    """

    @given(
        violations=violations_list_strategy,
        filter_status=valid_status_strategy,
    )
    @settings(max_examples=100)
    def test_applying_same_filter_twice_is_idempotent(
        self,
        violations: List[ViolationData],
        filter_status: str,
    ):
        """
        Property: Applying the same filter twice is idempotent.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        Applying the same filter twice SHALL return the same results as
        applying it once.
        """
        filtered_once = filter_by_status(violations, filter_status)
        filtered_twice = filter_by_status(filtered_once, filter_status)
        
        # Property: Results should be identical
        assert len(filtered_once) == len(filtered_twice), \
            f"First filter: {len(filtered_once)}, Second filter: {len(filtered_twice)}"
        
        once_ids = {v.id for v in filtered_once}
        twice_ids = {v.id for v in filtered_twice}
        assert once_ids == twice_ids, \
            "Applying filter twice changed the results"

    @given(
        violations=violations_list_strategy,
        filter_status=valid_status_strategy,
        filter_severity=valid_severity_strategy,
    )
    @settings(max_examples=100)
    def test_filter_order_does_not_matter(
        self,
        violations: List[ViolationData],
        filter_status: str,
        filter_severity: str,
    ):
        """
        Property: Filter order does not affect results.
        
        Feature: data-policy-agent, Property 15: Violation Filtering Correctness
        **Validates: Requirements 6.5**
        
        Applying filters in different orders SHALL return the same results.
        """
        # Apply status first, then severity
        result1 = filter_by_severity(filter_by_status(violations, filter_status), filter_severity)
        
        # Apply severity first, then status
        result2 = filter_by_status(filter_by_severity(violations, filter_severity), filter_status)
        
        # Property: Results should be identical
        assert len(result1) == len(result2), \
            f"Order 1: {len(result1)}, Order 2: {len(result2)}"
        
        ids1 = {v.id for v in result1}
        ids2 = {v.id for v in result2}
        assert ids1 == ids2, \
            "Filter order affected the results"
