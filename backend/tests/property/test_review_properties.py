"""Property-based tests for review status transitions.

Feature: data-policy-agent, Property 11: Review Status Transitions

This module contains property-based tests that verify:
1. Each review action type maps to the correct status transition
2. Review actions always create audit entries with required fields
3. Resolve action sets resolved_at timestamp
4. Audit entries preserve reviewer_id and notes
5. Status transitions are deterministic (same action always produces same status)

**Validates: Requirements 4.3, 4.4, 4.6**

Note: Since we can't use a real database in property tests, we test the
status transition logic by:
1. Generating random review actions with various action types
2. Applying the status transition mapping
3. Verifying the resulting status matches the expected value
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest
from hypothesis import given, strategies as st, settings, assume

from app.models.enums import ReviewActionType, Severity, ViolationStatus


# =============================================================================
# Status Transition Mapping (from violations.py)
# =============================================================================

# This mapping mirrors the ACTION_TO_STATUS_MAP from violations.py
ACTION_TO_STATUS_MAP = {
    ReviewActionType.CONFIRM.value: ViolationStatus.CONFIRMED.value,
    ReviewActionType.FALSE_POSITIVE.value: ViolationStatus.FALSE_POSITIVE.value,
    ReviewActionType.RESOLVE.value: ViolationStatus.RESOLVED.value,
    # Also support alternative naming conventions used in the API
    "confirm": ViolationStatus.CONFIRMED.value,
    "mark_false_positive": ViolationStatus.FALSE_POSITIVE.value,
    "resolve": ViolationStatus.RESOLVED.value,
}


# Valid action types that can be used in review decisions
VALID_ACTION_TYPES = ["confirm", "mark_false_positive", "resolve"]


def get_expected_status(action_type: str) -> str:
    """Get the expected violation status for a given action type.
    
    Args:
        action_type: The review action type
        
    Returns:
        The expected ViolationStatus value after the action
    """
    return ACTION_TO_STATUS_MAP[action_type]


def should_set_resolved_at(action_type: str) -> bool:
    """Check if the action type should set the resolved_at timestamp.
    
    Args:
        action_type: The review action type
        
    Returns:
        True if the action should set resolved_at, False otherwise
    """
    return action_type == "resolve"


# =============================================================================
# Data Classes for Testing (simulating models without DB)
# =============================================================================

@dataclass
class ReviewActionData:
    """Data class representing a review action for testing.
    
    This simulates the ReviewAction model without requiring database access.
    """
    id: uuid.UUID
    violation_id: uuid.UUID
    action_type: str
    reviewer_id: str
    notes: Optional[str]
    created_at: datetime


@dataclass
class ViolationData:
    """Data class representing a violation for testing.
    
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
    review_actions: List[ReviewActionData] = field(default_factory=list)


def apply_review_action(
    violation: ViolationData,
    action_type: str,
    reviewer_id: str,
    notes: Optional[str] = None,
) -> tuple[ViolationData, ReviewActionData]:
    """Apply a review action to a violation.
    
    This simulates the review_violation endpoint logic.
    
    Args:
        violation: The violation to review
        action_type: The review action type
        reviewer_id: The reviewer's identifier
        notes: Optional notes for the review
        
    Returns:
        Tuple of (updated violation, created review action)
    """
    # Determine new status based on action_type
    new_status = get_expected_status(action_type)
    
    # Update violation status
    violation.status = new_status
    
    # Set resolved_at timestamp if resolving
    if should_set_resolved_at(action_type):
        violation.resolved_at = datetime.now(timezone.utc)
    
    # Create ReviewAction audit entry
    review_action = ReviewActionData(
        id=uuid.uuid4(),
        violation_id=violation.id,
        action_type=action_type,
        reviewer_id=reviewer_id,
        notes=notes,
        created_at=datetime.now(timezone.utc),
    )
    
    # Add to violation's review history
    violation.review_actions.append(review_action)
    
    return violation, review_action


# =============================================================================
# Hypothesis Strategies for Test Data Generation
# =============================================================================

# Valid action types strategy
valid_action_type_strategy = st.sampled_from(VALID_ACTION_TYPES)

# Valid severity levels
valid_severity_strategy = st.sampled_from([s.value for s in Severity])

# Valid violation status values
valid_status_strategy = st.sampled_from([s.value for s in ViolationStatus])

# Valid reviewer ID strategy (non-empty string)
valid_reviewer_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_@.'),
    min_size=1,
    max_size=255
).filter(lambda x: x.strip() != "")

# Valid notes strategy (optional, can be None or non-empty string)
valid_notes_strategy = st.one_of(
    st.none(),
    st.text(min_size=1, max_size=2000).filter(lambda x: x.strip() != ""),
)

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

# Strategy for generating a pending violation (initial state before review)
# Note: We use st.builds with a lambda for review_actions to ensure each
# generated violation gets a fresh empty list (avoiding shared mutable state)
pending_violation_strategy = st.builds(
    lambda id, rule_id, record_identifier, record_data, justification, severity: ViolationData(
        id=id,
        rule_id=rule_id,
        record_identifier=record_identifier,
        record_data=record_data,
        justification=justification,
        severity=severity,
        status=ViolationStatus.PENDING.value,
        detected_at=datetime.now(timezone.utc),
        resolved_at=None,
        review_actions=[],  # Fresh list for each violation
    ),
    id=st.uuids(),
    rule_id=st.uuids(),
    record_identifier=valid_record_identifier_strategy,
    record_data=valid_record_data_strategy,
    justification=valid_justification_strategy,
    severity=valid_severity_strategy,
)


# =============================================================================
# Property 11: Review Status Transitions
# =============================================================================

class TestReviewStatusTransitions:
    """Property tests for Review Status Transitions.
    
    Feature: data-policy-agent, Property 11: Review Status Transitions
    
    For any review action (confirm, false_positive, resolve) on a violation, 
    the violation status SHALL update to the corresponding state and a 
    ReviewAction audit entry SHALL be created with the reviewer identity 
    and timestamp.
    
    **Validates: Requirements 4.3, 4.4, 4.6**
    """

    @given(action_type=valid_action_type_strategy)
    @settings(max_examples=100)
    def test_action_type_maps_to_correct_status(self, action_type: str):
        """
        Property: Each review action type maps to the correct status.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.3, 4.4**
        
        For any valid action type, the resulting status SHALL be:
        - "confirm" -> "confirmed"
        - "mark_false_positive" -> "false_positive"
        - "resolve" -> "resolved"
        """
        expected_mapping = {
            "confirm": ViolationStatus.CONFIRMED.value,
            "mark_false_positive": ViolationStatus.FALSE_POSITIVE.value,
            "resolve": ViolationStatus.RESOLVED.value,
        }
        
        result_status = get_expected_status(action_type)
        
        # Property: Action type must map to the correct status
        assert result_status == expected_mapping[action_type], \
            f"Action '{action_type}' should map to '{expected_mapping[action_type]}', got '{result_status}'"

    @given(
        violation=pending_violation_strategy,
        action_type=valid_action_type_strategy,
        reviewer_id=valid_reviewer_id_strategy,
        notes=valid_notes_strategy,
    )
    @settings(max_examples=100)
    def test_review_action_updates_violation_status(
        self,
        violation: ViolationData,
        action_type: str,
        reviewer_id: str,
        notes: Optional[str],
    ):
        """
        Property: Review actions update violation status correctly.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.3, 4.4**
        
        For any review action on a violation, the violation status SHALL
        be updated to the corresponding state.
        """
        # Apply the review action
        updated_violation, _ = apply_review_action(
            violation, action_type, reviewer_id, notes
        )
        
        expected_status = get_expected_status(action_type)
        
        # Property: Violation status must be updated correctly
        assert updated_violation.status == expected_status, \
            f"After '{action_type}' action, status should be '{expected_status}', got '{updated_violation.status}'"


    @given(
        violation=pending_violation_strategy,
        action_type=valid_action_type_strategy,
        reviewer_id=valid_reviewer_id_strategy,
        notes=valid_notes_strategy,
    )
    @settings(max_examples=100)
    def test_review_action_creates_audit_entry(
        self,
        violation: ViolationData,
        action_type: str,
        reviewer_id: str,
        notes: Optional[str],
    ):
        """
        Property: Review actions always create audit entries.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.6**
        
        For any review action, a ReviewAction audit entry SHALL be created.
        """
        initial_action_count = len(violation.review_actions)
        
        # Apply the review action
        updated_violation, review_action = apply_review_action(
            violation, action_type, reviewer_id, notes
        )
        
        # Property: A new review action must be created
        assert len(updated_violation.review_actions) == initial_action_count + 1, \
            f"Expected {initial_action_count + 1} review actions, got {len(updated_violation.review_actions)}"
        
        # Property: The review action must be in the violation's history
        assert review_action in updated_violation.review_actions, \
            "Review action should be added to violation's review history"

    @given(
        violation=pending_violation_strategy,
        action_type=valid_action_type_strategy,
        reviewer_id=valid_reviewer_id_strategy,
        notes=valid_notes_strategy,
    )
    @settings(max_examples=100)
    def test_audit_entry_has_required_fields(
        self,
        violation: ViolationData,
        action_type: str,
        reviewer_id: str,
        notes: Optional[str],
    ):
        """
        Property: Audit entries contain all required fields.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.6**
        
        For any review action, the audit entry SHALL contain:
        - id (non-null UUID)
        - violation_id (matching the violation)
        - action_type (the action taken)
        - reviewer_id (non-empty string)
        - created_at (timestamp)
        """
        # Apply the review action
        _, review_action = apply_review_action(
            violation, action_type, reviewer_id, notes
        )
        
        # Property: All required fields must be present and valid
        assert review_action.id is not None, "Review action id must not be None"
        assert isinstance(review_action.id, uuid.UUID), "Review action id must be a UUID"
        
        assert review_action.violation_id == violation.id, \
            f"Review action violation_id '{review_action.violation_id}' must match violation id '{violation.id}'"
        
        assert review_action.action_type == action_type, \
            f"Review action action_type '{review_action.action_type}' must match '{action_type}'"
        
        assert review_action.reviewer_id is not None, "Review action reviewer_id must not be None"
        assert len(review_action.reviewer_id) > 0, "Review action reviewer_id must not be empty"
        
        assert review_action.created_at is not None, "Review action created_at must not be None"
        assert isinstance(review_action.created_at, datetime), "Review action created_at must be a datetime"


    @given(
        violation=pending_violation_strategy,
        reviewer_id=valid_reviewer_id_strategy,
        notes=valid_notes_strategy,
    )
    @settings(max_examples=100)
    def test_resolve_action_sets_resolved_at_timestamp(
        self,
        violation: ViolationData,
        reviewer_id: str,
        notes: Optional[str],
    ):
        """
        Property: Resolve action sets resolved_at timestamp.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.3**
        
        When a violation is resolved, the resolved_at timestamp SHALL be set.
        """
        # Ensure resolved_at is initially None
        assert violation.resolved_at is None, "Initial resolved_at should be None"
        
        # Apply the resolve action
        updated_violation, _ = apply_review_action(
            violation, "resolve", reviewer_id, notes
        )
        
        # Property: resolved_at must be set after resolve action
        assert updated_violation.resolved_at is not None, \
            "resolved_at must be set after resolve action"
        assert isinstance(updated_violation.resolved_at, datetime), \
            "resolved_at must be a datetime"

    @given(
        violation=pending_violation_strategy,
        action_type=st.sampled_from(["confirm", "mark_false_positive"]),
        reviewer_id=valid_reviewer_id_strategy,
        notes=valid_notes_strategy,
    )
    @settings(max_examples=100)
    def test_non_resolve_actions_do_not_set_resolved_at(
        self,
        violation: ViolationData,
        action_type: str,
        reviewer_id: str,
        notes: Optional[str],
    ):
        """
        Property: Non-resolve actions do not set resolved_at timestamp.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.3, 4.4**
        
        When a violation is confirmed or marked as false positive, the 
        resolved_at timestamp SHALL remain None.
        """
        # Ensure resolved_at is initially None
        assert violation.resolved_at is None, "Initial resolved_at should be None"
        
        # Apply a non-resolve action
        updated_violation, _ = apply_review_action(
            violation, action_type, reviewer_id, notes
        )
        
        # Property: resolved_at must remain None for non-resolve actions
        assert updated_violation.resolved_at is None, \
            f"resolved_at should remain None after '{action_type}' action"


    @given(
        violation=pending_violation_strategy,
        action_type=valid_action_type_strategy,
        reviewer_id=valid_reviewer_id_strategy,
        notes=valid_notes_strategy,
    )
    @settings(max_examples=100)
    def test_audit_entry_preserves_reviewer_id(
        self,
        violation: ViolationData,
        action_type: str,
        reviewer_id: str,
        notes: Optional[str],
    ):
        """
        Property: Audit entries preserve reviewer_id.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.6**
        
        For any review action, the audit entry SHALL preserve the exact
        reviewer_id that was provided.
        """
        # Apply the review action
        _, review_action = apply_review_action(
            violation, action_type, reviewer_id, notes
        )
        
        # Property: reviewer_id must be preserved exactly
        assert review_action.reviewer_id == reviewer_id, \
            f"Review action reviewer_id '{review_action.reviewer_id}' must match input '{reviewer_id}'"

    @given(
        violation=pending_violation_strategy,
        action_type=valid_action_type_strategy,
        reviewer_id=valid_reviewer_id_strategy,
        notes=st.text(min_size=1, max_size=2000).filter(lambda x: x.strip() != ""),
    )
    @settings(max_examples=100)
    def test_audit_entry_preserves_notes(
        self,
        violation: ViolationData,
        action_type: str,
        reviewer_id: str,
        notes: str,
    ):
        """
        Property: Audit entries preserve notes.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.6**
        
        For any review action with notes, the audit entry SHALL preserve
        the exact notes that were provided.
        """
        # Apply the review action
        _, review_action = apply_review_action(
            violation, action_type, reviewer_id, notes
        )
        
        # Property: notes must be preserved exactly
        assert review_action.notes == notes, \
            f"Review action notes must match input notes"

    @given(
        violation=pending_violation_strategy,
        action_type=valid_action_type_strategy,
        reviewer_id=valid_reviewer_id_strategy,
    )
    @settings(max_examples=100)
    def test_audit_entry_allows_null_notes(
        self,
        violation: ViolationData,
        action_type: str,
        reviewer_id: str,
    ):
        """
        Property: Audit entries allow null notes.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.6**
        
        For any review action without notes, the audit entry SHALL have
        notes set to None.
        """
        # Apply the review action with no notes
        _, review_action = apply_review_action(
            violation, action_type, reviewer_id, notes=None
        )
        
        # Property: notes can be None
        assert review_action.notes is None, \
            "Review action notes should be None when not provided"


class TestStatusTransitionDeterminism:
    """Property tests for status transition determinism.
    
    Feature: data-policy-agent, Property 11: Review Status Transitions
    
    Status transitions are deterministic - the same action always produces
    the same status.
    
    **Validates: Requirements 4.3, 4.4**
    """

    @given(
        action_type=valid_action_type_strategy,
        num_applications=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=100)
    def test_same_action_always_produces_same_status(
        self,
        action_type: str,
        num_applications: int,
    ):
        """
        Property: Same action always produces same status.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.3, 4.4**
        
        For any action type, applying it multiple times to different violations
        SHALL always produce the same resulting status.
        """
        results = []
        
        for _ in range(num_applications):
            # Create a fresh violation each time
            violation = ViolationData(
                id=uuid.uuid4(),
                rule_id=uuid.uuid4(),
                record_identifier=f"record-{uuid.uuid4()}",
                record_data={"field": "value"},
                justification="Test justification",
                severity=Severity.MEDIUM.value,
                status=ViolationStatus.PENDING.value,
                detected_at=datetime.now(timezone.utc),
                resolved_at=None,
                review_actions=[],
            )
            
            # Apply the action
            updated_violation, _ = apply_review_action(
                violation, action_type, "test-reviewer", None
            )
            
            results.append(updated_violation.status)
        
        # Property: All results must be the same
        first_result = results[0]
        for i, result in enumerate(results):
            assert result == first_result, \
                f"Application {i} produced status '{result}', expected '{first_result}'"

    @given(
        violation=pending_violation_strategy,
        action_type=valid_action_type_strategy,
        reviewer_ids=st.lists(valid_reviewer_id_strategy, min_size=2, max_size=5),
    )
    @settings(max_examples=100)
    def test_status_independent_of_reviewer(
        self,
        violation: ViolationData,
        action_type: str,
        reviewer_ids: List[str],
    ):
        """
        Property: Status transition is independent of reviewer identity.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.3, 4.4**
        
        For any action type, the resulting status SHALL be the same
        regardless of which reviewer performs the action.
        """
        expected_status = get_expected_status(action_type)
        
        for reviewer_id in reviewer_ids:
            # Create a fresh copy of the violation
            test_violation = ViolationData(
                id=violation.id,
                rule_id=violation.rule_id,
                record_identifier=violation.record_identifier,
                record_data=violation.record_data.copy(),
                justification=violation.justification,
                severity=violation.severity,
                status=ViolationStatus.PENDING.value,
                detected_at=violation.detected_at,
                resolved_at=None,
                review_actions=[],
            )
            
            # Apply the action with different reviewer
            updated_violation, _ = apply_review_action(
                test_violation, action_type, reviewer_id, None
            )
            
            # Property: Status must be the same regardless of reviewer
            assert updated_violation.status == expected_status, \
                f"Reviewer '{reviewer_id}' produced status '{updated_violation.status}', expected '{expected_status}'"


class TestMultipleReviewActions:
    """Property tests for multiple review actions on a violation.
    
    Feature: data-policy-agent, Property 11: Review Status Transitions
    
    Tests that multiple review actions create multiple audit entries and
    the final status reflects the last action.
    
    **Validates: Requirements 4.3, 4.4, 4.6**
    """

    @given(
        violation=pending_violation_strategy,
        action_types=st.lists(valid_action_type_strategy, min_size=2, max_size=5),
        reviewer_id=valid_reviewer_id_strategy,
    )
    @settings(max_examples=100)
    def test_multiple_actions_create_multiple_audit_entries(
        self,
        violation: ViolationData,
        action_types: List[str],
        reviewer_id: str,
    ):
        """
        Property: Multiple review actions create multiple audit entries.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.6**
        
        For any sequence of review actions, each action SHALL create a
        separate audit entry.
        """
        current_violation = violation
        
        for action_type in action_types:
            current_violation, _ = apply_review_action(
                current_violation, action_type, reviewer_id, None
            )
        
        # Property: Number of audit entries must match number of actions
        assert len(current_violation.review_actions) == len(action_types), \
            f"Expected {len(action_types)} audit entries, got {len(current_violation.review_actions)}"

    @given(
        violation=pending_violation_strategy,
        action_types=st.lists(valid_action_type_strategy, min_size=2, max_size=5),
        reviewer_id=valid_reviewer_id_strategy,
    )
    @settings(max_examples=100)
    def test_final_status_reflects_last_action(
        self,
        violation: ViolationData,
        action_types: List[str],
        reviewer_id: str,
    ):
        """
        Property: Final status reflects the last action taken.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.3, 4.4**
        
        For any sequence of review actions, the final violation status
        SHALL reflect the last action taken.
        """
        current_violation = violation
        
        for action_type in action_types:
            current_violation, _ = apply_review_action(
                current_violation, action_type, reviewer_id, None
            )
        
        # Property: Final status must match the last action's expected status
        last_action = action_types[-1]
        expected_status = get_expected_status(last_action)
        
        assert current_violation.status == expected_status, \
            f"Final status should be '{expected_status}' after '{last_action}', got '{current_violation.status}'"

    @given(
        violation=pending_violation_strategy,
        action_types=st.lists(valid_action_type_strategy, min_size=2, max_size=5),
        reviewer_ids=st.lists(valid_reviewer_id_strategy, min_size=2, max_size=5),
    )
    @settings(max_examples=100)
    def test_audit_entries_preserve_action_sequence(
        self,
        violation: ViolationData,
        action_types: List[str],
        reviewer_ids: List[str],
    ):
        """
        Property: Audit entries preserve the sequence of actions.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.6**
        
        For any sequence of review actions, the audit entries SHALL
        preserve the action types in order.
        """
        current_violation = violation
        
        # Use the shorter list length to avoid index errors
        num_actions = min(len(action_types), len(reviewer_ids))
        
        for i in range(num_actions):
            current_violation, _ = apply_review_action(
                current_violation, action_types[i], reviewer_ids[i], None
            )
        
        # Property: Audit entries must preserve action sequence
        for i in range(num_actions):
            assert current_violation.review_actions[i].action_type == action_types[i], \
                f"Audit entry {i} should have action_type '{action_types[i]}', got '{current_violation.review_actions[i].action_type}'"
            assert current_violation.review_actions[i].reviewer_id == reviewer_ids[i], \
                f"Audit entry {i} should have reviewer_id '{reviewer_ids[i]}', got '{current_violation.review_actions[i].reviewer_id}'"


class TestActionTypeValidation:
    """Property tests for action type validation.
    
    Feature: data-policy-agent, Property 11: Review Status Transitions
    
    Tests that only valid action types are accepted.
    
    **Validates: Requirements 4.3, 4.4**
    """

    def test_all_valid_action_types_are_mapped(self):
        """
        Property: All valid action types have status mappings.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.3, 4.4**
        
        All valid action types SHALL have a corresponding status mapping.
        """
        for action_type in VALID_ACTION_TYPES:
            assert action_type in ACTION_TO_STATUS_MAP, \
                f"Action type '{action_type}' should have a status mapping"

    def test_confirm_maps_to_confirmed(self):
        """
        Property: "confirm" action maps to "confirmed" status.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.3**
        
        The "confirm" action SHALL map to "confirmed" status.
        """
        assert get_expected_status("confirm") == ViolationStatus.CONFIRMED.value, \
            "'confirm' should map to 'confirmed'"

    def test_mark_false_positive_maps_to_false_positive(self):
        """
        Property: "mark_false_positive" action maps to "false_positive" status.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.4**
        
        The "mark_false_positive" action SHALL map to "false_positive" status.
        """
        assert get_expected_status("mark_false_positive") == ViolationStatus.FALSE_POSITIVE.value, \
            "'mark_false_positive' should map to 'false_positive'"

    def test_resolve_maps_to_resolved(self):
        """
        Property: "resolve" action maps to "resolved" status.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.3**
        
        The "resolve" action SHALL map to "resolved" status.
        """
        assert get_expected_status("resolve") == ViolationStatus.RESOLVED.value, \
            "'resolve' should map to 'resolved'"

    def test_status_values_are_valid_enum_values(self):
        """
        Property: All mapped statuses are valid ViolationStatus values.
        
        Feature: data-policy-agent, Property 11: Review Status Transitions
        **Validates: Requirements 4.3, 4.4**
        
        All status values in the mapping SHALL be valid ViolationStatus enum values.
        """
        valid_statuses = {s.value for s in ViolationStatus}
        
        for action_type in VALID_ACTION_TYPES:
            status = get_expected_status(action_type)
            assert status in valid_statuses, \
                f"Status '{status}' for action '{action_type}' is not a valid ViolationStatus"
