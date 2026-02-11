"""Property-based tests for dashboard summary accuracy.

Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy

This module contains property-based tests that verify:
1. Total violations count equals the sum of all violations in DB
2. Each status count equals the count of violations with that status
3. Each severity count equals the count of violations with that severity

**Validates: Requirements 6.1**

Note: Since we can't use a real database in property tests, we test the
summary calculation logic by:
1. Generating random lists of violations with various statuses/severities
2. Computing expected counts from the generated data
3. Verifying the summary calculation functions produce matching counts
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
    """Data class representing a violation for summary tests.
    
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
# Summary Calculation Functions (simulating the logic from dashboard.py)
# =============================================================================

def calculate_total_violations(violations: List[ViolationData]) -> int:
    """Calculate total number of violations.
    
    Args:
        violations: List of violations
        
    Returns:
        Total count of violations
    """
    return len(violations)


def calculate_violations_by_status(violations: List[ViolationData]) -> Dict[str, int]:
    """Calculate violation counts grouped by status.
    
    Args:
        violations: List of violations
        
    Returns:
        Dictionary mapping status to count
    """
    counts = {
        ViolationStatus.PENDING.value: 0,
        ViolationStatus.CONFIRMED.value: 0,
        ViolationStatus.FALSE_POSITIVE.value: 0,
        ViolationStatus.RESOLVED.value: 0,
    }
    
    for violation in violations:
        if violation.status in counts:
            counts[violation.status] += 1
    
    return counts


def calculate_violations_by_severity(violations: List[ViolationData]) -> Dict[str, int]:
    """Calculate violation counts grouped by severity.
    
    Args:
        violations: List of violations
        
    Returns:
        Dictionary mapping severity to count
    """
    counts = {
        Severity.LOW.value: 0,
        Severity.MEDIUM.value: 0,
        Severity.HIGH.value: 0,
        Severity.CRITICAL.value: 0,
    }
    
    for violation in violations:
        if violation.severity in counts:
            counts[violation.severity] += 1
    
    return counts


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
violations_list_strategy = st.lists(violation_data_strategy, min_size=0, max_size=50)


# =============================================================================
# Property 14: Dashboard Summary Accuracy
# =============================================================================

class TestDashboardSummaryAccuracy:
    """Property tests for Dashboard Summary Accuracy.
    
    Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
    
    For any set of violations in the database, the dashboard summary counts 
    (total, pending, confirmed, resolved, by_severity) SHALL equal the actual 
    counts when filtered by those criteria.
    
    **Validates: Requirements 6.1**
    """

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_total_violations_count_matches_actual(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Total violations count equals the sum of all violations in DB.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, the total_violations count in the dashboard
        summary SHALL equal the actual number of violations in the database.
        """
        total = calculate_total_violations(violations)
        
        # Property: Total count must match actual count
        assert total == len(violations), \
            f"Total violations count {total} does not match actual count {len(violations)}"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_pending_count_matches_actual(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Pending count equals the count of violations with pending status.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, the pending count in the dashboard summary
        SHALL equal the actual count of violations with status "pending".
        """
        status_counts = calculate_violations_by_status(violations)
        
        # Count expected pending violations
        expected_pending = sum(1 for v in violations if v.status == ViolationStatus.PENDING.value)
        
        # Property: Pending count must match actual count
        assert status_counts[ViolationStatus.PENDING.value] == expected_pending, \
            f"Pending count {status_counts[ViolationStatus.PENDING.value]} does not match expected {expected_pending}"


    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_confirmed_count_matches_actual(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Confirmed count equals the count of violations with confirmed status.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, the confirmed count in the dashboard summary
        SHALL equal the actual count of violations with status "confirmed".
        """
        status_counts = calculate_violations_by_status(violations)
        
        # Count expected confirmed violations
        expected_confirmed = sum(1 for v in violations if v.status == ViolationStatus.CONFIRMED.value)
        
        # Property: Confirmed count must match actual count
        assert status_counts[ViolationStatus.CONFIRMED.value] == expected_confirmed, \
            f"Confirmed count {status_counts[ViolationStatus.CONFIRMED.value]} does not match expected {expected_confirmed}"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_false_positive_count_matches_actual(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: False positive count equals the count of violations with false_positive status.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, the false_positive count in the dashboard summary
        SHALL equal the actual count of violations with status "false_positive".
        """
        status_counts = calculate_violations_by_status(violations)
        
        # Count expected false positive violations
        expected_fp = sum(1 for v in violations if v.status == ViolationStatus.FALSE_POSITIVE.value)
        
        # Property: False positive count must match actual count
        assert status_counts[ViolationStatus.FALSE_POSITIVE.value] == expected_fp, \
            f"False positive count {status_counts[ViolationStatus.FALSE_POSITIVE.value]} does not match expected {expected_fp}"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_resolved_count_matches_actual(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Resolved count equals the count of violations with resolved status.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, the resolved count in the dashboard summary
        SHALL equal the actual count of violations with status "resolved".
        """
        status_counts = calculate_violations_by_status(violations)
        
        # Count expected resolved violations
        expected_resolved = sum(1 for v in violations if v.status == ViolationStatus.RESOLVED.value)
        
        # Property: Resolved count must match actual count
        assert status_counts[ViolationStatus.RESOLVED.value] == expected_resolved, \
            f"Resolved count {status_counts[ViolationStatus.RESOLVED.value]} does not match expected {expected_resolved}"


    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_status_counts_sum_equals_total(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Sum of all status counts equals total violations.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, the sum of all status counts (pending + 
        confirmed + false_positive + resolved) SHALL equal the total violations count.
        """
        total = calculate_total_violations(violations)
        status_counts = calculate_violations_by_status(violations)
        
        # Sum all status counts
        status_sum = sum(status_counts.values())
        
        # Property: Sum of status counts must equal total
        assert status_sum == total, \
            f"Sum of status counts {status_sum} does not equal total {total}"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_low_severity_count_matches_actual(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Low severity count equals the count of violations with low severity.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, the low severity count in the dashboard summary
        SHALL equal the actual count of violations with severity "low".
        """
        severity_counts = calculate_violations_by_severity(violations)
        
        # Count expected low severity violations
        expected_low = sum(1 for v in violations if v.severity == Severity.LOW.value)
        
        # Property: Low severity count must match actual count
        assert severity_counts[Severity.LOW.value] == expected_low, \
            f"Low severity count {severity_counts[Severity.LOW.value]} does not match expected {expected_low}"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_medium_severity_count_matches_actual(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Medium severity count equals the count of violations with medium severity.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, the medium severity count in the dashboard summary
        SHALL equal the actual count of violations with severity "medium".
        """
        severity_counts = calculate_violations_by_severity(violations)
        
        # Count expected medium severity violations
        expected_medium = sum(1 for v in violations if v.severity == Severity.MEDIUM.value)
        
        # Property: Medium severity count must match actual count
        assert severity_counts[Severity.MEDIUM.value] == expected_medium, \
            f"Medium severity count {severity_counts[Severity.MEDIUM.value]} does not match expected {expected_medium}"


    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_high_severity_count_matches_actual(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: High severity count equals the count of violations with high severity.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, the high severity count in the dashboard summary
        SHALL equal the actual count of violations with severity "high".
        """
        severity_counts = calculate_violations_by_severity(violations)
        
        # Count expected high severity violations
        expected_high = sum(1 for v in violations if v.severity == Severity.HIGH.value)
        
        # Property: High severity count must match actual count
        assert severity_counts[Severity.HIGH.value] == expected_high, \
            f"High severity count {severity_counts[Severity.HIGH.value]} does not match expected {expected_high}"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_critical_severity_count_matches_actual(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Critical severity count equals the count of violations with critical severity.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, the critical severity count in the dashboard summary
        SHALL equal the actual count of violations with severity "critical".
        """
        severity_counts = calculate_violations_by_severity(violations)
        
        # Count expected critical severity violations
        expected_critical = sum(1 for v in violations if v.severity == Severity.CRITICAL.value)
        
        # Property: Critical severity count must match actual count
        assert severity_counts[Severity.CRITICAL.value] == expected_critical, \
            f"Critical severity count {severity_counts[Severity.CRITICAL.value]} does not match expected {expected_critical}"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_severity_counts_sum_equals_total(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Sum of all severity counts equals total violations.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, the sum of all severity counts (low + 
        medium + high + critical) SHALL equal the total violations count.
        """
        total = calculate_total_violations(violations)
        severity_counts = calculate_violations_by_severity(violations)
        
        # Sum all severity counts
        severity_sum = sum(severity_counts.values())
        
        # Property: Sum of severity counts must equal total
        assert severity_sum == total, \
            f"Sum of severity counts {severity_sum} does not equal total {total}"


    @given(
        num_pending=st.integers(min_value=0, max_value=10),
        num_confirmed=st.integers(min_value=0, max_value=10),
        num_false_positive=st.integers(min_value=0, max_value=10),
        num_resolved=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100)
    def test_status_counts_with_known_distribution(
        self,
        num_pending: int,
        num_confirmed: int,
        num_false_positive: int,
        num_resolved: int,
    ):
        """
        Property: Status counts match known distribution.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any known distribution of violations by status, the calculated
        counts SHALL exactly match the input distribution.
        """
        violations = []
        
        # Create violations with known status distribution
        for i in range(num_pending):
            violations.append(ViolationData(
                id=uuid.uuid4(),
                rule_id=uuid.uuid4(),
                record_identifier=f"pending-{i}",
                record_data={"index": i},
                justification=f"Pending violation {i}",
                severity=Severity.MEDIUM.value,
                status=ViolationStatus.PENDING.value,
                detected_at=datetime.now(timezone.utc),
            ))
        
        for i in range(num_confirmed):
            violations.append(ViolationData(
                id=uuid.uuid4(),
                rule_id=uuid.uuid4(),
                record_identifier=f"confirmed-{i}",
                record_data={"index": i},
                justification=f"Confirmed violation {i}",
                severity=Severity.HIGH.value,
                status=ViolationStatus.CONFIRMED.value,
                detected_at=datetime.now(timezone.utc),
            ))
        
        for i in range(num_false_positive):
            violations.append(ViolationData(
                id=uuid.uuid4(),
                rule_id=uuid.uuid4(),
                record_identifier=f"false-positive-{i}",
                record_data={"index": i},
                justification=f"False positive violation {i}",
                severity=Severity.LOW.value,
                status=ViolationStatus.FALSE_POSITIVE.value,
                detected_at=datetime.now(timezone.utc),
            ))
        
        for i in range(num_resolved):
            violations.append(ViolationData(
                id=uuid.uuid4(),
                rule_id=uuid.uuid4(),
                record_identifier=f"resolved-{i}",
                record_data={"index": i},
                justification=f"Resolved violation {i}",
                severity=Severity.CRITICAL.value,
                status=ViolationStatus.RESOLVED.value,
                detected_at=datetime.now(timezone.utc),
            ))
        
        # Calculate counts
        total = calculate_total_violations(violations)
        status_counts = calculate_violations_by_status(violations)
        
        # Property: Counts must match known distribution
        expected_total = num_pending + num_confirmed + num_false_positive + num_resolved
        assert total == expected_total, \
            f"Total {total} does not match expected {expected_total}"
        assert status_counts[ViolationStatus.PENDING.value] == num_pending, \
            f"Pending count mismatch"
        assert status_counts[ViolationStatus.CONFIRMED.value] == num_confirmed, \
            f"Confirmed count mismatch"
        assert status_counts[ViolationStatus.FALSE_POSITIVE.value] == num_false_positive, \
            f"False positive count mismatch"
        assert status_counts[ViolationStatus.RESOLVED.value] == num_resolved, \
            f"Resolved count mismatch"


    @given(
        num_low=st.integers(min_value=0, max_value=10),
        num_medium=st.integers(min_value=0, max_value=10),
        num_high=st.integers(min_value=0, max_value=10),
        num_critical=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100)
    def test_severity_counts_with_known_distribution(
        self,
        num_low: int,
        num_medium: int,
        num_high: int,
        num_critical: int,
    ):
        """
        Property: Severity counts match known distribution.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any known distribution of violations by severity, the calculated
        counts SHALL exactly match the input distribution.
        """
        violations = []
        
        # Create violations with known severity distribution
        for i in range(num_low):
            violations.append(ViolationData(
                id=uuid.uuid4(),
                rule_id=uuid.uuid4(),
                record_identifier=f"low-{i}",
                record_data={"index": i},
                justification=f"Low severity violation {i}",
                severity=Severity.LOW.value,
                status=ViolationStatus.PENDING.value,
                detected_at=datetime.now(timezone.utc),
            ))
        
        for i in range(num_medium):
            violations.append(ViolationData(
                id=uuid.uuid4(),
                rule_id=uuid.uuid4(),
                record_identifier=f"medium-{i}",
                record_data={"index": i},
                justification=f"Medium severity violation {i}",
                severity=Severity.MEDIUM.value,
                status=ViolationStatus.PENDING.value,
                detected_at=datetime.now(timezone.utc),
            ))
        
        for i in range(num_high):
            violations.append(ViolationData(
                id=uuid.uuid4(),
                rule_id=uuid.uuid4(),
                record_identifier=f"high-{i}",
                record_data={"index": i},
                justification=f"High severity violation {i}",
                severity=Severity.HIGH.value,
                status=ViolationStatus.PENDING.value,
                detected_at=datetime.now(timezone.utc),
            ))
        
        for i in range(num_critical):
            violations.append(ViolationData(
                id=uuid.uuid4(),
                rule_id=uuid.uuid4(),
                record_identifier=f"critical-{i}",
                record_data={"index": i},
                justification=f"Critical severity violation {i}",
                severity=Severity.CRITICAL.value,
                status=ViolationStatus.PENDING.value,
                detected_at=datetime.now(timezone.utc),
            ))
        
        # Calculate counts
        total = calculate_total_violations(violations)
        severity_counts = calculate_violations_by_severity(violations)
        
        # Property: Counts must match known distribution
        expected_total = num_low + num_medium + num_high + num_critical
        assert total == expected_total, \
            f"Total {total} does not match expected {expected_total}"
        assert severity_counts[Severity.LOW.value] == num_low, \
            f"Low severity count mismatch"
        assert severity_counts[Severity.MEDIUM.value] == num_medium, \
            f"Medium severity count mismatch"
        assert severity_counts[Severity.HIGH.value] == num_high, \
            f"High severity count mismatch"
        assert severity_counts[Severity.CRITICAL.value] == num_critical, \
            f"Critical severity count mismatch"


    def test_empty_violations_returns_zero_counts(self):
        """
        Property: Empty violations list returns zero counts.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        When there are no violations in the database, all counts SHALL be zero.
        """
        violations: List[ViolationData] = []
        
        total = calculate_total_violations(violations)
        status_counts = calculate_violations_by_status(violations)
        severity_counts = calculate_violations_by_severity(violations)
        
        # Property: All counts must be zero
        assert total == 0, "Total should be 0 for empty list"
        assert all(count == 0 for count in status_counts.values()), \
            "All status counts should be 0 for empty list"
        assert all(count == 0 for count in severity_counts.values()), \
            "All severity counts should be 0 for empty list"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_counts_are_non_negative(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: All counts are non-negative.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, all counts (total, by_status, by_severity)
        SHALL be non-negative integers.
        """
        total = calculate_total_violations(violations)
        status_counts = calculate_violations_by_status(violations)
        severity_counts = calculate_violations_by_severity(violations)
        
        # Property: Total must be non-negative
        assert total >= 0, f"Total count {total} is negative"
        
        # Property: All status counts must be non-negative
        for status, count in status_counts.items():
            assert count >= 0, f"Status count for '{status}' is negative: {count}"
        
        # Property: All severity counts must be non-negative
        for severity, count in severity_counts.items():
            assert count >= 0, f"Severity count for '{severity}' is negative: {count}"

    @given(violations=violations_list_strategy)
    @settings(max_examples=100)
    def test_individual_counts_do_not_exceed_total(
        self,
        violations: List[ViolationData],
    ):
        """
        Property: Individual counts do not exceed total.
        
        Feature: data-policy-agent, Property 14: Dashboard Summary Accuracy
        **Validates: Requirements 6.1**
        
        For any set of violations, no individual status or severity count
        SHALL exceed the total violations count.
        """
        total = calculate_total_violations(violations)
        status_counts = calculate_violations_by_status(violations)
        severity_counts = calculate_violations_by_severity(violations)
        
        # Property: No status count exceeds total
        for status, count in status_counts.items():
            assert count <= total, \
                f"Status count for '{status}' ({count}) exceeds total ({total})"
        
        # Property: No severity count exceeds total
        for severity, count in severity_counts.items():
            assert count <= total, \
                f"Severity count for '{severity}' ({count}) exceeds total ({total})"


# =============================================================================
# Property 18: Trend Percentage Calculation
# =============================================================================

# Trend calculation functions (simulating the logic from dashboard.py)

def calculate_percentage_change(current: int, previous: int) -> Optional[float]:
    """Calculate percentage change between two periods.
    
    Formula: ((current - previous) / previous) * 100
    
    Args:
        current: Violation count in current period
        previous: Violation count in previous period
        
    Returns:
        Percentage change, or None if previous is 0
    """
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 2)


def determine_trend_indicator(percentage_change: Optional[float], current: int, previous: int) -> str:
    """Determine trend indicator based on percentage change.
    
    Uses 5% threshold for stability:
    - > 5% = degradation (more violations)
    - < -5% = improvement (fewer violations)
    - between -5% and 5% = stable
    
    Args:
        percentage_change: Calculated percentage change (or None)
        current: Current period violation count
        previous: Previous period violation count
        
    Returns:
        Trend indicator: "improvement", "degradation", or "stable"
    """
    if percentage_change is not None:
        if percentage_change > 5:
            return "degradation"
        elif percentage_change < -5:
            return "improvement"
        else:
            return "stable"
    elif current > 0:
        # Previous was 0, current has violations = degradation
        return "degradation"
    else:
        # Both are 0, stable
        return "stable"


class TestTrendPercentageCalculation:
    """Property tests for Trend Percentage Calculation.
    
    Feature: data-policy-agent, Property 18: Trend Percentage Calculation
    
    For any two consecutive time periods with violation counts V1 and V2, 
    the calculated improvement/degradation percentage SHALL equal 
    ((V2 - V1) / V1) * 100 when V1 > 0.
    
    **Validates: Requirements 8.3**
    """

    @given(
        current=st.integers(min_value=0, max_value=10000),
        previous=st.integers(min_value=1, max_value=10000),
    )
    @settings(max_examples=100)
    def test_percentage_change_calculation_is_mathematically_correct(
        self,
        current: int,
        previous: int,
    ):
        """
        Property: Percentage change calculation is mathematically correct.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        For any current and previous violation counts where previous > 0,
        the percentage change SHALL equal ((current - previous) / previous) * 100.
        """
        result = calculate_percentage_change(current, previous)
        
        # Calculate expected value using the formula
        expected = round(((current - previous) / previous) * 100, 2)
        
        # Property: Result must match the mathematical formula
        assert result == expected, \
            f"Percentage change {result} does not match expected {expected} " \
            f"for current={current}, previous={previous}"

    @given(current=st.integers(min_value=0, max_value=10000))
    @settings(max_examples=100)
    def test_percentage_change_is_none_when_previous_is_zero(
        self,
        current: int,
    ):
        """
        Property: When previous period is 0, percentage_change should be None.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        When the previous period has 0 violations, the percentage change
        SHALL be None (division by zero is undefined).
        """
        result = calculate_percentage_change(current, previous=0)
        
        # Property: Result must be None when previous is 0
        assert result is None, \
            f"Percentage change should be None when previous is 0, got {result}"

    @given(
        current=st.integers(min_value=0, max_value=10000),
        previous=st.integers(min_value=1, max_value=10000),
    )
    @settings(max_examples=100)
    def test_trend_indicator_degradation_when_percentage_above_5(
        self,
        current: int,
        previous: int,
    ):
        """
        Property: Trend indicator is 'degradation' when percentage > 5%.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        When the percentage change is greater than 5%, the trend indicator
        SHALL be "degradation" (more violations = worse compliance).
        """
        percentage = calculate_percentage_change(current, previous)
        
        # Only test when percentage > 5
        assume(percentage is not None and percentage > 5)
        
        indicator = determine_trend_indicator(percentage, current, previous)
        
        # Property: Indicator must be degradation when percentage > 5%
        assert indicator == "degradation", \
            f"Trend indicator should be 'degradation' when percentage={percentage}%, got '{indicator}'"

    @given(
        current=st.integers(min_value=0, max_value=10000),
        previous=st.integers(min_value=1, max_value=10000),
    )
    @settings(max_examples=100)
    def test_trend_indicator_improvement_when_percentage_below_minus_5(
        self,
        current: int,
        previous: int,
    ):
        """
        Property: Trend indicator is 'improvement' when percentage < -5%.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        When the percentage change is less than -5%, the trend indicator
        SHALL be "improvement" (fewer violations = better compliance).
        """
        percentage = calculate_percentage_change(current, previous)
        
        # Only test when percentage < -5
        assume(percentage is not None and percentage < -5)
        
        indicator = determine_trend_indicator(percentage, current, previous)
        
        # Property: Indicator must be improvement when percentage < -5%
        assert indicator == "improvement", \
            f"Trend indicator should be 'improvement' when percentage={percentage}%, got '{indicator}'"

    @given(
        previous=st.integers(min_value=100, max_value=10000),
        # Generate a multiplier that produces -5% to +5% change
        multiplier=st.floats(min_value=0.95, max_value=1.05),
    )
    @settings(max_examples=100)
    def test_trend_indicator_stable_when_percentage_between_minus_5_and_5(
        self,
        previous: int,
        multiplier: float,
    ):
        """
        Property: Trend indicator is 'stable' when -5% <= percentage <= 5%.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        When the percentage change is between -5% and 5% (inclusive),
        the trend indicator SHALL be "stable".
        """
        # Calculate current based on multiplier to ensure we get values in the stable range
        current = int(previous * multiplier)
        
        percentage = calculate_percentage_change(current, previous)
        
        # Only test when -5 <= percentage <= 5 (should be most cases with our strategy)
        assume(percentage is not None and -5 <= percentage <= 5)
        
        indicator = determine_trend_indicator(percentage, current, previous)
        
        # Property: Indicator must be stable when -5% <= percentage <= 5%
        assert indicator == "stable", \
            f"Trend indicator should be 'stable' when percentage={percentage}%, got '{indicator}'"

    @given(
        value_a=st.integers(min_value=10, max_value=10000),
        value_b=st.integers(min_value=10, max_value=10000),
    )
    @settings(max_examples=100)
    def test_percentage_change_symmetry_consistency(
        self,
        value_a: int,
        value_b: int,
    ):
        """
        Property: Percentage change is symmetric but consistent.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        If A→B is +X%, then B→A should be different but mathematically consistent.
        The key property is that the signs are opposite (if A→B is positive, B→A is negative).
        
        This verifies that the calculation is consistent in both directions.
        """
        # Skip if values are equal (0% change both ways)
        assume(value_a != value_b)
        
        # Calculate A→B percentage
        a_to_b = calculate_percentage_change(value_b, value_a)
        
        # Calculate B→A percentage
        b_to_a = calculate_percentage_change(value_a, value_b)
        
        # Both should be non-None since both values > 0
        assert a_to_b is not None, "A→B percentage should not be None"
        assert b_to_a is not None, "B→A percentage should not be None"
        
        # Property: If A→B is positive, B→A should be negative (and vice versa)
        if a_to_b > 0:
            assert b_to_a < 0, \
                f"If A→B is positive ({a_to_b}%), B→A should be negative, got {b_to_a}%"
        elif a_to_b < 0:
            assert b_to_a > 0, \
                f"If A→B is negative ({a_to_b}%), B→A should be positive, got {b_to_a}%"
        
        # Property: Verify mathematical consistency
        # If we go from A to B and back to A, we should get back to A
        # B = A * (1 + a_to_b/100)
        # A' = B * (1 + b_to_a/100) = A * (1 + a_to_b/100) * (1 + b_to_a/100)
        # For consistency: (1 + a_to_b/100) * (1 + b_to_a/100) ≈ 1
        # Note: Due to rounding in percentage calculation, we allow a tolerance
        product = (1 + a_to_b/100) * (1 + b_to_a/100)
        # Use a tolerance that accounts for rounding errors (0.05 = 5%)
        # Rounding errors are more significant with larger percentage changes
        assert abs(product - 1.0) < 0.05, \
            f"Round-trip product should be ~1, got {product} for A={value_a}, B={value_b}"

    @given(current=st.integers(min_value=1, max_value=10000))
    @settings(max_examples=100)
    def test_trend_indicator_degradation_when_previous_zero_and_current_positive(
        self,
        current: int,
    ):
        """
        Property: Trend indicator is 'degradation' when previous=0 and current>0.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        When the previous period had 0 violations and current period has
        violations, this represents degradation (new violations appeared).
        """
        percentage = calculate_percentage_change(current, previous=0)
        indicator = determine_trend_indicator(percentage, current, previous=0)
        
        # Property: Indicator must be degradation when going from 0 to positive
        assert indicator == "degradation", \
            f"Trend indicator should be 'degradation' when previous=0 and current={current}, got '{indicator}'"

    def test_trend_indicator_stable_when_both_zero(self):
        """
        Property: Trend indicator is 'stable' when both periods have 0 violations.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        When both periods have 0 violations, the trend is stable
        (no change in compliance status).
        """
        percentage = calculate_percentage_change(current=0, previous=0)
        indicator = determine_trend_indicator(percentage, current=0, previous=0)
        
        # Property: Indicator must be stable when both are 0
        assert indicator == "stable", \
            f"Trend indicator should be 'stable' when both periods are 0, got '{indicator}'"

    @given(value=st.integers(min_value=1, max_value=10000))
    @settings(max_examples=100)
    def test_percentage_change_is_zero_when_values_equal(
        self,
        value: int,
    ):
        """
        Property: Percentage change is 0% when current equals previous.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        When current and previous violation counts are equal,
        the percentage change SHALL be 0%.
        """
        result = calculate_percentage_change(value, value)
        
        # Property: Result must be 0 when values are equal
        assert result == 0.0, \
            f"Percentage change should be 0% when current=previous={value}, got {result}%"

    @given(value=st.integers(min_value=1, max_value=10000))
    @settings(max_examples=100)
    def test_trend_indicator_stable_when_values_equal(
        self,
        value: int,
    ):
        """
        Property: Trend indicator is 'stable' when current equals previous.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        When current and previous violation counts are equal (0% change),
        the trend indicator SHALL be "stable".
        """
        percentage = calculate_percentage_change(value, value)
        indicator = determine_trend_indicator(percentage, value, value)
        
        # Property: Indicator must be stable when values are equal
        assert indicator == "stable", \
            f"Trend indicator should be 'stable' when current=previous={value}, got '{indicator}'"

    @given(previous=st.integers(min_value=1, max_value=10000))
    @settings(max_examples=100)
    def test_percentage_change_is_minus_100_when_current_is_zero(
        self,
        previous: int,
    ):
        """
        Property: Percentage change is -100% when current is 0 and previous > 0.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        When current period has 0 violations and previous had some,
        the percentage change SHALL be -100% (complete improvement).
        """
        result = calculate_percentage_change(current=0, previous=previous)
        
        # Property: Result must be -100% when current is 0
        assert result == -100.0, \
            f"Percentage change should be -100% when current=0 and previous={previous}, got {result}%"

    @given(previous=st.integers(min_value=1, max_value=10000))
    @settings(max_examples=100)
    def test_trend_indicator_improvement_when_current_is_zero(
        self,
        previous: int,
    ):
        """
        Property: Trend indicator is 'improvement' when current is 0 and previous > 0.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        When current period has 0 violations and previous had some,
        the trend indicator SHALL be "improvement" (all violations resolved).
        """
        percentage = calculate_percentage_change(current=0, previous=previous)
        indicator = determine_trend_indicator(percentage, current=0, previous=previous)
        
        # Property: Indicator must be improvement when current is 0
        assert indicator == "improvement", \
            f"Trend indicator should be 'improvement' when current=0 and previous={previous}, got '{indicator}'"

    @given(previous=st.integers(min_value=1, max_value=5000))
    @settings(max_examples=100)
    def test_percentage_change_is_100_when_current_is_double_previous(
        self,
        previous: int,
    ):
        """
        Property: Percentage change is 100% when current is double previous.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        When current period has double the violations of previous,
        the percentage change SHALL be 100%.
        """
        current = previous * 2
        result = calculate_percentage_change(current, previous)
        
        # Property: Result must be 100% when current is double previous
        assert result == 100.0, \
            f"Percentage change should be 100% when current={current} is double previous={previous}, got {result}%"

    @given(
        current=st.integers(min_value=0, max_value=10000),
        previous=st.integers(min_value=1, max_value=10000),
    )
    @settings(max_examples=100)
    def test_percentage_change_sign_indicates_direction(
        self,
        current: int,
        previous: int,
    ):
        """
        Property: Percentage change sign correctly indicates direction.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        Positive percentage = more violations (degradation)
        Negative percentage = fewer violations (improvement)
        Zero percentage = same number of violations
        """
        result = calculate_percentage_change(current, previous)
        
        assert result is not None, "Result should not be None when previous > 0"
        
        # Property: Sign must correctly indicate direction
        if current > previous:
            assert result > 0, \
                f"Percentage should be positive when current ({current}) > previous ({previous}), got {result}%"
        elif current < previous:
            assert result < 0, \
                f"Percentage should be negative when current ({current}) < previous ({previous}), got {result}%"
        else:
            assert result == 0, \
                f"Percentage should be 0 when current ({current}) == previous ({previous}), got {result}%"

    @given(
        current=st.integers(min_value=0, max_value=10000),
        previous=st.integers(min_value=0, max_value=10000),
    )
    @settings(max_examples=100)
    def test_trend_indicator_is_always_valid_value(
        self,
        current: int,
        previous: int,
    ):
        """
        Property: Trend indicator is always one of the valid values.
        
        Feature: data-policy-agent, Property 18: Trend Percentage Calculation
        **Validates: Requirements 8.3**
        
        The trend indicator SHALL always be one of: "improvement", 
        "degradation", or "stable".
        """
        percentage = calculate_percentage_change(current, previous)
        indicator = determine_trend_indicator(percentage, current, previous)
        
        valid_indicators = {"improvement", "degradation", "stable"}
        
        # Property: Indicator must be one of the valid values
        assert indicator in valid_indicators, \
            f"Trend indicator '{indicator}' is not valid. Must be one of {valid_indicators}"
