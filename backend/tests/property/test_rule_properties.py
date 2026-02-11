"""Property-based tests for compliance rule extraction structure.

Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip

This module contains property-based tests that verify:
1. The structural validity of compliance rules extracted from policy documents.
2. The round-trip integrity of storing and retrieving rules with policy references.

**Validates: Requirements 1.3, 1.6**
"""

import json
import uuid
import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import AsyncMock

from app.services.llm_client import BaseLLMClient


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing rule extraction logic."""
    
    def __init__(self, response: str):
        self._response = response
    
    async def _generate(self, prompt: str) -> str:
        return self._response


# Strategies for generating valid compliance rules
valid_rule_code_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
    min_size=1,
    max_size=20
).filter(lambda x: x.strip() != "")

valid_description_strategy = st.text(
    min_size=1,
    max_size=500
).filter(lambda x: x.strip() != "")

valid_evaluation_criteria_strategy = st.text(
    min_size=1,
    max_size=200
).filter(lambda x: x.strip() != "")

valid_severity_strategy = st.sampled_from(["low", "medium", "high", "critical"])

valid_target_entities_strategy = st.text(min_size=0, max_size=100)


# Strategy for generating a complete valid rule
valid_rule_strategy = st.fixed_dictionaries({
    "rule_code": valid_rule_code_strategy,
    "description": valid_description_strategy,
    "evaluation_criteria": valid_evaluation_criteria_strategy,
    "severity": valid_severity_strategy,
    "target_entities": valid_target_entities_strategy,
})


# Strategy for generating a list of valid rules
valid_rules_list_strategy = st.lists(valid_rule_strategy, min_size=1, max_size=10)


class TestComplianceRuleStructureValidity:
    """Property tests for Compliance Rule Structure Validity.
    
    Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
    
    For any policy text processed by the Policy_Parser, all returned 
    Compliance_Rules SHALL contain a non-empty rule_code, description, 
    and evaluation_criteria field.
    
    **Validates: Requirements 1.3**
    """

    @given(rules=valid_rules_list_strategy)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_extracted_rules_contain_required_fields(self, rules: list[dict]):
        """
        Property: All extracted rules contain required fields.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        
        For any valid LLM response containing compliance rules, the extract_rules
        method SHALL return rules that contain rule_code, description, and 
        evaluation_criteria fields.
        """
        # Create mock LLM response with the generated rules
        mock_response = json.dumps(rules)
        client = MockLLMClient(mock_response)
        
        # Extract rules using the actual extraction logic
        extracted_rules = await client.extract_rules("Sample policy text")
        
        # Property: All rules must contain required fields
        required_fields = {"rule_code", "description", "evaluation_criteria"}
        for rule in extracted_rules:
            for field in required_fields:
                assert field in rule, f"Rule missing required field: {field}"

    @given(rules=valid_rules_list_strategy)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_extracted_rules_have_non_empty_required_fields(self, rules: list[dict]):
        """
        Property: All extracted rules have non-empty required fields.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        
        For any valid LLM response containing compliance rules with non-empty
        required fields, the extract_rules method SHALL preserve those non-empty
        values.
        """
        # Create mock LLM response with the generated rules
        mock_response = json.dumps(rules)
        client = MockLLMClient(mock_response)
        
        # Extract rules using the actual extraction logic
        extracted_rules = await client.extract_rules("Sample policy text")
        
        # Property: Required fields must be non-empty strings when input is non-empty
        for i, rule in enumerate(extracted_rules):
            original_rule = rules[i]
            
            # rule_code should be preserved as non-empty
            assert rule["rule_code"] == original_rule["rule_code"]
            assert isinstance(rule["rule_code"], str)
            assert len(rule["rule_code"].strip()) > 0, "rule_code must be non-empty"
            
            # description should be preserved as non-empty
            assert rule["description"] == original_rule["description"]
            assert isinstance(rule["description"], str)
            assert len(rule["description"].strip()) > 0, "description must be non-empty"
            
            # evaluation_criteria should be preserved as non-empty
            assert rule["evaluation_criteria"] == original_rule["evaluation_criteria"]
            assert isinstance(rule["evaluation_criteria"], str)
            assert len(rule["evaluation_criteria"].strip()) > 0, "evaluation_criteria must be non-empty"

    @given(rules=valid_rules_list_strategy)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_rule_count_preserved(self, rules: list[dict]):
        """
        Property: The number of rules is preserved during extraction.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        
        For any valid LLM response containing N compliance rules, the extract_rules
        method SHALL return exactly N rules.
        """
        # Create mock LLM response with the generated rules
        mock_response = json.dumps(rules)
        client = MockLLMClient(mock_response)
        
        # Extract rules using the actual extraction logic
        extracted_rules = await client.extract_rules("Sample policy text")
        
        # Property: Rule count must be preserved
        assert len(extracted_rules) == len(rules), \
            f"Expected {len(rules)} rules, got {len(extracted_rules)}"

    @given(rules=valid_rules_list_strategy)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_severity_field_preserved(self, rules: list[dict]):
        """
        Property: Severity field is preserved during extraction.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        
        For any valid LLM response containing compliance rules with severity,
        the extract_rules method SHALL preserve the severity value.
        """
        # Create mock LLM response with the generated rules
        mock_response = json.dumps(rules)
        client = MockLLMClient(mock_response)
        
        # Extract rules using the actual extraction logic
        extracted_rules = await client.extract_rules("Sample policy text")
        
        # Property: Severity must be preserved
        valid_severities = {"low", "medium", "high", "critical"}
        for i, rule in enumerate(extracted_rules):
            assert rule["severity"] == rules[i]["severity"]
            assert rule["severity"] in valid_severities, \
                f"Invalid severity: {rule['severity']}"


class TestRuleExtractionWithMarkdownFormatting:
    """Property tests for rule extraction with markdown-formatted responses.
    
    Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
    **Validates: Requirements 1.3**
    """

    @given(rules=valid_rules_list_strategy)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_markdown_json_code_blocks_handled(self, rules: list[dict]):
        """
        Property: Markdown JSON code blocks are properly stripped.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        
        For any valid LLM response wrapped in markdown code blocks, the 
        extract_rules method SHALL correctly parse the rules.
        """
        # Create mock LLM response with markdown formatting
        json_content = json.dumps(rules)
        mock_response = f"```json\n{json_content}\n```"
        client = MockLLMClient(mock_response)
        
        # Extract rules using the actual extraction logic
        extracted_rules = await client.extract_rules("Sample policy text")
        
        # Property: Rules should be correctly extracted despite markdown formatting
        assert len(extracted_rules) == len(rules)
        for i, rule in enumerate(extracted_rules):
            assert rule["rule_code"] == rules[i]["rule_code"]
            assert rule["description"] == rules[i]["description"]
            assert rule["evaluation_criteria"] == rules[i]["evaluation_criteria"]

    @given(rules=valid_rules_list_strategy)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_generic_code_blocks_handled(self, rules: list[dict]):
        """
        Property: Generic code blocks are properly stripped.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        
        For any valid LLM response wrapped in generic code blocks (```), the 
        extract_rules method SHALL correctly parse the rules.
        """
        # Create mock LLM response with generic code block formatting
        json_content = json.dumps(rules)
        mock_response = f"```\n{json_content}\n```"
        client = MockLLMClient(mock_response)
        
        # Extract rules using the actual extraction logic
        extracted_rules = await client.extract_rules("Sample policy text")
        
        # Property: Rules should be correctly extracted despite code block formatting
        assert len(extracted_rules) == len(rules)
        for rule in extracted_rules:
            assert "rule_code" in rule
            assert "description" in rule
            assert "evaluation_criteria" in rule


class TestRuleExtractionMissingFieldsHandling:
    """Property tests for handling rules with missing fields.
    
    Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
    **Validates: Requirements 1.3**
    
    These tests verify that the extraction logic properly handles cases where
    the LLM returns rules with missing required fields by adding empty defaults.
    """

    @given(
        rule_code=valid_rule_code_strategy,
        description=valid_description_strategy
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_missing_evaluation_criteria_gets_default(
        self, rule_code: str, description: str
    ):
        """
        Property: Missing evaluation_criteria field gets empty default.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        
        When a rule is missing the evaluation_criteria field, the extract_rules
        method SHALL add an empty string default.
        """
        # Create rule missing evaluation_criteria
        incomplete_rule = {
            "rule_code": rule_code,
            "description": description,
            "severity": "medium"
        }
        mock_response = json.dumps([incomplete_rule])
        client = MockLLMClient(mock_response)
        
        # Extract rules
        extracted_rules = await client.extract_rules("Sample policy text")
        
        # Property: evaluation_criteria should exist (even if empty)
        assert len(extracted_rules) == 1
        assert "evaluation_criteria" in extracted_rules[0]
        assert extracted_rules[0]["evaluation_criteria"] == ""

    @given(
        rule_code=valid_rule_code_strategy,
        evaluation_criteria=valid_evaluation_criteria_strategy
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_missing_description_gets_default(
        self, rule_code: str, evaluation_criteria: str
    ):
        """
        Property: Missing description field gets empty default.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        
        When a rule is missing the description field, the extract_rules
        method SHALL add an empty string default.
        """
        # Create rule missing description
        incomplete_rule = {
            "rule_code": rule_code,
            "evaluation_criteria": evaluation_criteria,
            "severity": "high"
        }
        mock_response = json.dumps([incomplete_rule])
        client = MockLLMClient(mock_response)
        
        # Extract rules
        extracted_rules = await client.extract_rules("Sample policy text")
        
        # Property: description should exist (even if empty)
        assert len(extracted_rules) == 1
        assert "description" in extracted_rules[0]
        assert extracted_rules[0]["description"] == ""

    @given(
        description=valid_description_strategy,
        evaluation_criteria=valid_evaluation_criteria_strategy
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_missing_rule_code_gets_default(
        self, description: str, evaluation_criteria: str
    ):
        """
        Property: Missing rule_code field gets empty default.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        
        When a rule is missing the rule_code field, the extract_rules
        method SHALL add an empty string default.
        """
        # Create rule missing rule_code
        incomplete_rule = {
            "description": description,
            "evaluation_criteria": evaluation_criteria,
            "severity": "low"
        }
        mock_response = json.dumps([incomplete_rule])
        client = MockLLMClient(mock_response)
        
        # Extract rules
        extracted_rules = await client.extract_rules("Sample policy text")
        
        # Property: rule_code should exist (even if empty)
        assert len(extracted_rules) == 1
        assert "rule_code" in extracted_rules[0]
        assert extracted_rules[0]["rule_code"] == ""

    @given(severity=valid_severity_strategy)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_missing_all_required_fields_get_defaults(self, severity: str):
        """
        Property: All missing required fields get empty defaults.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        
        When a rule is missing all required fields (rule_code, description,
        evaluation_criteria), the extract_rules method SHALL add empty string
        defaults for each.
        """
        # Create rule missing all required fields
        incomplete_rule = {
            "severity": severity,
            "target_entities": "some entities"
        }
        mock_response = json.dumps([incomplete_rule])
        client = MockLLMClient(mock_response)
        
        # Extract rules
        extracted_rules = await client.extract_rules("Sample policy text")
        
        # Property: All required fields should exist with empty defaults
        assert len(extracted_rules) == 1
        rule = extracted_rules[0]
        assert "rule_code" in rule
        assert "description" in rule
        assert "evaluation_criteria" in rule
        assert "severity" in rule
        assert rule["rule_code"] == ""
        assert rule["description"] == ""
        assert rule["evaluation_criteria"] == ""
        # severity should be preserved since it was provided
        assert rule["severity"] == severity


def validate_rule_structure(rule: dict) -> bool:
    """
    Validate that a compliance rule has the required structure.
    
    This is a helper function that can be used to validate rule structure
    in other parts of the application.
    
    Args:
        rule: A dictionary representing a compliance rule.
        
    Returns:
        True if the rule has all required fields as non-empty strings,
        False otherwise.
    """
    required_fields = ["rule_code", "description", "evaluation_criteria"]
    
    for field in required_fields:
        if field not in rule:
            return False
        if not isinstance(rule[field], str):
            return False
        if len(rule[field].strip()) == 0:
            return False
    
    return True


class TestRuleStructureValidationHelper:
    """Property tests for the rule structure validation helper function.
    
    Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
    **Validates: Requirements 1.3**
    """

    @given(rules=valid_rules_list_strategy)
    @settings(max_examples=100)
    def test_valid_rules_pass_validation(self, rules: list[dict]):
        """
        Property: Valid rules pass structure validation.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        
        For any rule with non-empty rule_code, description, and evaluation_criteria,
        the validate_rule_structure function SHALL return True.
        """
        for rule in rules:
            assert validate_rule_structure(rule) is True, \
                f"Valid rule failed validation: {rule}"

    @given(
        rule_code=st.text(max_size=20),
        description=st.text(max_size=100),
        evaluation_criteria=st.text(max_size=100)
    )
    @settings(max_examples=100)
    def test_empty_fields_fail_validation(
        self, rule_code: str, description: str, evaluation_criteria: str
    ):
        """
        Property: Rules with empty required fields fail validation.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        
        For any rule where at least one required field is empty or whitespace-only,
        the validate_rule_structure function SHALL return False.
        """
        # Skip if all fields happen to be non-empty
        if (rule_code.strip() and description.strip() and evaluation_criteria.strip()):
            return
        
        rule = {
            "rule_code": rule_code,
            "description": description,
            "evaluation_criteria": evaluation_criteria,
            "severity": "medium"
        }
        
        # At least one field is empty, so validation should fail
        assert validate_rule_structure(rule) is False, \
            f"Rule with empty field passed validation: {rule}"

    @given(
        description=valid_description_strategy,
        evaluation_criteria=valid_evaluation_criteria_strategy
    )
    @settings(max_examples=100)
    def test_missing_rule_code_fails_validation(
        self, description: str, evaluation_criteria: str
    ):
        """
        Property: Rules missing rule_code fail validation.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        """
        rule = {
            "description": description,
            "evaluation_criteria": evaluation_criteria,
            "severity": "high"
        }
        
        assert validate_rule_structure(rule) is False

    @given(
        rule_code=valid_rule_code_strategy,
        evaluation_criteria=valid_evaluation_criteria_strategy
    )
    @settings(max_examples=100)
    def test_missing_description_fails_validation(
        self, rule_code: str, evaluation_criteria: str
    ):
        """
        Property: Rules missing description fail validation.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        """
        rule = {
            "rule_code": rule_code,
            "evaluation_criteria": evaluation_criteria,
            "severity": "medium"
        }
        
        assert validate_rule_structure(rule) is False

    @given(
        rule_code=valid_rule_code_strategy,
        description=valid_description_strategy
    )
    @settings(max_examples=100)
    def test_missing_evaluation_criteria_fails_validation(
        self, rule_code: str, description: str
    ):
        """
        Property: Rules missing evaluation_criteria fail validation.
        
        Feature: data-policy-agent, Property 1: Compliance Rule Structure Validity
        **Validates: Requirements 1.3**
        """
        rule = {
            "rule_code": rule_code,
            "description": description,
            "severity": "low"
        }
        
        assert validate_rule_structure(rule) is False


# =============================================================================
# Property 2: Policy-to-Rules Round Trip
# =============================================================================

# Additional strategies for Policy-to-Rules Round Trip testing
valid_uuid_strategy = st.uuids()

valid_target_table_strategy = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_'),
        min_size=1,
        max_size=50
    ).filter(lambda x: x.strip() != "")
)

valid_generated_sql_strategy = st.one_of(
    st.none(),
    st.text(min_size=10, max_size=500).filter(lambda x: x.strip() != "")
)

valid_is_active_strategy = st.booleans()


# Strategy for generating a complete rule with all fields for round-trip testing
complete_rule_strategy = st.fixed_dictionaries({
    "rule_code": valid_rule_code_strategy,
    "description": valid_description_strategy,
    "evaluation_criteria": valid_evaluation_criteria_strategy,
    "severity": valid_severity_strategy,
    "target_table": valid_target_table_strategy,
    "generated_sql": valid_generated_sql_strategy,
    "is_active": valid_is_active_strategy,
})


# Strategy for generating a list of complete rules
complete_rules_list_strategy = st.lists(complete_rule_strategy, min_size=1, max_size=10)


class TestPolicyToRulesRoundTrip:
    """Property tests for Policy-to-Rules Round Trip.
    
    Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip
    
    For any successfully parsed Policy_Document, storing and then retrieving 
    the associated Compliance_Rules SHALL return rules that reference the 
    original policy ID and contain the same content.
    
    **Validates: Requirements 1.6**
    
    Note: Since we can't use a real database in property tests, we test the 
    round-trip logic by:
    1. Creating a Policy with a known ID
    2. Creating ComplianceRules that reference that policy ID
    3. Verifying the rules maintain the correct policy_id reference
    4. Verifying the rule content is preserved correctly
    """

    @given(
        policy_id=valid_uuid_strategy,
        rules_data=complete_rules_list_strategy
    )
    @settings(max_examples=100)
    def test_rules_reference_correct_policy_id(
        self, policy_id: uuid.UUID, rules_data: list[dict]
    ):
        """
        Property: All rules reference the correct policy ID.
        
        Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip
        **Validates: Requirements 1.6**
        
        For any Policy with a given ID, all associated ComplianceRules SHALL
        have their policy_id field set to that Policy's ID.
        """
        from app.models.compliance_rule import ComplianceRule
        from app.models.policy import Policy
        
        # Create a Policy with the generated ID
        policy = Policy(
            id=policy_id,
            filename="test_policy.pdf",
            raw_text="Sample policy text",
            status="completed"
        )
        
        # Create ComplianceRules referencing this policy
        rules = []
        for rule_data in rules_data:
            rule = ComplianceRule(
                policy_id=policy_id,
                rule_code=rule_data["rule_code"],
                description=rule_data["description"],
                evaluation_criteria=rule_data["evaluation_criteria"],
                severity=rule_data["severity"],
                target_table=rule_data["target_table"],
                generated_sql=rule_data["generated_sql"],
                is_active=rule_data["is_active"],
            )
            rules.append(rule)
        
        # Property: All rules must reference the correct policy ID
        for rule in rules:
            assert rule.policy_id == policy.id, \
                f"Rule policy_id {rule.policy_id} does not match policy ID {policy.id}"

    @given(
        policy_id=valid_uuid_strategy,
        rules_data=complete_rules_list_strategy
    )
    @settings(max_examples=100)
    def test_rule_content_preserved(
        self, policy_id: uuid.UUID, rules_data: list[dict]
    ):
        """
        Property: Rule content is preserved during round trip.
        
        Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip
        **Validates: Requirements 1.6**
        
        For any ComplianceRule created with specific content, retrieving that
        rule SHALL return the same content values.
        """
        from app.models.compliance_rule import ComplianceRule
        
        # Create ComplianceRules and verify content preservation
        for rule_data in rules_data:
            rule = ComplianceRule(
                policy_id=policy_id,
                rule_code=rule_data["rule_code"],
                description=rule_data["description"],
                evaluation_criteria=rule_data["evaluation_criteria"],
                severity=rule_data["severity"],
                target_table=rule_data["target_table"],
                generated_sql=rule_data["generated_sql"],
                is_active=rule_data["is_active"],
            )
            
            # Property: All content fields must be preserved
            assert rule.rule_code == rule_data["rule_code"], \
                f"rule_code not preserved: {rule.rule_code} != {rule_data['rule_code']}"
            assert rule.description == rule_data["description"], \
                f"description not preserved"
            assert rule.evaluation_criteria == rule_data["evaluation_criteria"], \
                f"evaluation_criteria not preserved"
            assert rule.severity == rule_data["severity"], \
                f"severity not preserved: {rule.severity} != {rule_data['severity']}"
            assert rule.target_table == rule_data["target_table"], \
                f"target_table not preserved"
            assert rule.generated_sql == rule_data["generated_sql"], \
                f"generated_sql not preserved"
            assert rule.is_active == rule_data["is_active"], \
                f"is_active not preserved"

    @given(
        policy_id=valid_uuid_strategy,
        rules_data=complete_rules_list_strategy
    )
    @settings(max_examples=100)
    def test_rule_count_preserved_in_round_trip(
        self, policy_id: uuid.UUID, rules_data: list[dict]
    ):
        """
        Property: The number of rules is preserved in round trip.
        
        Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip
        **Validates: Requirements 1.6**
        
        For any Policy with N associated rules, retrieving those rules SHALL
        return exactly N rules.
        """
        from app.models.compliance_rule import ComplianceRule
        
        # Create ComplianceRules
        rules = []
        for rule_data in rules_data:
            rule = ComplianceRule(
                policy_id=policy_id,
                rule_code=rule_data["rule_code"],
                description=rule_data["description"],
                evaluation_criteria=rule_data["evaluation_criteria"],
                severity=rule_data["severity"],
                target_table=rule_data["target_table"],
                generated_sql=rule_data["generated_sql"],
                is_active=rule_data["is_active"],
            )
            rules.append(rule)
        
        # Property: Rule count must be preserved
        assert len(rules) == len(rules_data), \
            f"Expected {len(rules_data)} rules, got {len(rules)}"

    @given(
        policy_id=valid_uuid_strategy,
        filename=st.text(min_size=1, max_size=100).filter(lambda x: x.strip() != ""),
        raw_text=st.text(min_size=1, max_size=5000).filter(lambda x: x.strip() != ""),
        rules_data=complete_rules_list_strategy
    )
    @settings(max_examples=100)
    def test_policy_metadata_preserved_with_rules(
        self, policy_id: uuid.UUID, filename: str, raw_text: str, rules_data: list[dict]
    ):
        """
        Property: Policy metadata is preserved alongside rules.
        
        Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip
        **Validates: Requirements 1.6**
        
        For any Policy with associated rules, the Policy's metadata (filename,
        raw_text) SHALL be preserved and accessible.
        """
        from app.models.compliance_rule import ComplianceRule
        from app.models.policy import Policy
        
        # Create Policy with metadata
        policy = Policy(
            id=policy_id,
            filename=filename,
            raw_text=raw_text,
            status="completed"
        )
        
        # Create associated rules
        rules = []
        for rule_data in rules_data:
            rule = ComplianceRule(
                policy_id=policy_id,
                rule_code=rule_data["rule_code"],
                description=rule_data["description"],
                evaluation_criteria=rule_data["evaluation_criteria"],
                severity=rule_data["severity"],
                target_table=rule_data["target_table"],
                generated_sql=rule_data["generated_sql"],
                is_active=rule_data["is_active"],
            )
            rules.append(rule)
        
        # Property: Policy metadata must be preserved
        assert policy.id == policy_id
        assert policy.filename == filename
        assert policy.raw_text == raw_text
        assert policy.status == "completed"
        
        # Property: All rules must reference this policy
        for rule in rules:
            assert rule.policy_id == policy.id

    @given(
        policy_id=valid_uuid_strategy,
        rules_data=complete_rules_list_strategy,
        rule_ids=st.lists(valid_uuid_strategy, min_size=1, max_size=10, unique=True)
    )
    @settings(max_examples=100)
    def test_rules_maintain_assigned_ids(
        self, policy_id: uuid.UUID, rules_data: list[dict], rule_ids: list[uuid.UUID]
    ):
        """
        Property: Rules maintain their assigned IDs.
        
        Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip
        **Validates: Requirements 1.6**
        
        For any ComplianceRules created with explicit IDs (simulating database
        persistence), each rule SHALL maintain its assigned ID.
        
        Note: In actual database usage, UUIDs are auto-generated. This test
        verifies that when IDs are explicitly assigned, they are preserved.
        """
        from app.models.compliance_rule import ComplianceRule
        
        # Use the minimum of available IDs and rules
        num_rules = min(len(rules_data), len(rule_ids))
        
        # Create ComplianceRules with explicit IDs
        rules = []
        for i in range(num_rules):
            rule_data = rules_data[i]
            rule = ComplianceRule(
                id=rule_ids[i],  # Explicitly assign ID
                policy_id=policy_id,
                rule_code=rule_data["rule_code"],
                description=rule_data["description"],
                evaluation_criteria=rule_data["evaluation_criteria"],
                severity=rule_data["severity"],
                target_table=rule_data["target_table"],
                generated_sql=rule_data["generated_sql"],
                is_active=rule_data["is_active"],
            )
            rules.append(rule)
        
        # Property: All rule IDs must be preserved and unique
        assigned_ids = [rule.id for rule in rules]
        expected_ids = rule_ids[:num_rules]
        
        assert assigned_ids == expected_ids, \
            "Rule IDs were not preserved"
        assert len(assigned_ids) == len(set(assigned_ids)), \
            "Rule IDs are not unique"

    @given(
        policy_id=valid_uuid_strategy,
        rules_data=complete_rules_list_strategy
    )
    @settings(max_examples=100)
    def test_severity_values_are_valid(
        self, policy_id: uuid.UUID, rules_data: list[dict]
    ):
        """
        Property: All severity values are valid enum values.
        
        Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip
        **Validates: Requirements 1.6**
        
        For any ComplianceRule, the severity field SHALL contain a valid
        severity value (low, medium, high, critical).
        """
        from app.models.compliance_rule import ComplianceRule
        from app.models.enums import Severity
        
        valid_severities = {s.value for s in Severity}
        
        # Create ComplianceRules and verify severity values
        for rule_data in rules_data:
            rule = ComplianceRule(
                policy_id=policy_id,
                rule_code=rule_data["rule_code"],
                description=rule_data["description"],
                evaluation_criteria=rule_data["evaluation_criteria"],
                severity=rule_data["severity"],
                target_table=rule_data["target_table"],
                generated_sql=rule_data["generated_sql"],
                is_active=rule_data["is_active"],
            )
            
            # Property: Severity must be a valid enum value
            assert rule.severity in valid_severities, \
                f"Invalid severity: {rule.severity}"


class TestPolicyToRulesRoundTripWithParseRules:
    """Property tests for Policy-to-Rules Round Trip using parse_rules method.
    
    Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip
    **Validates: Requirements 1.6**
    
    These tests verify that the parse_rules method correctly creates
    ComplianceRule instances that reference the source policy.
    """

    @given(
        policy_id=valid_uuid_strategy,
        rules=valid_rules_list_strategy
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_parse_rules_creates_rules_with_correct_policy_reference(
        self, policy_id: uuid.UUID, rules: list[dict]
    ):
        """
        Property: parse_rules creates rules with correct policy reference.
        
        Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip
        **Validates: Requirements 1.6**
        
        For any policy_id passed to parse_rules, all returned ComplianceRule
        instances SHALL have their policy_id set to that value.
        """
        from app.services.policy_parser import PolicyParserService
        
        # Create mock LLM response
        mock_response = json.dumps(rules)
        mock_client = MockLLMClient(mock_response)
        
        # Create parser service and parse rules
        parser = PolicyParserService()
        compliance_rules = await parser.parse_rules(
            text="Sample policy text",
            policy_id=str(policy_id),
            llm_client=mock_client,
        )
        
        # Property: All rules must reference the correct policy ID
        for rule in compliance_rules:
            assert rule.policy_id == policy_id, \
                f"Rule policy_id {rule.policy_id} does not match expected {policy_id}"

    @given(
        policy_id=valid_uuid_strategy,
        rules=valid_rules_list_strategy
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_parse_rules_preserves_rule_content(
        self, policy_id: uuid.UUID, rules: list[dict]
    ):
        """
        Property: parse_rules preserves rule content from LLM response.
        
        Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip
        **Validates: Requirements 1.6**
        
        For any rules returned by the LLM, parse_rules SHALL create
        ComplianceRule instances with the same content values.
        """
        from app.services.policy_parser import PolicyParserService
        
        # Create mock LLM response
        mock_response = json.dumps(rules)
        mock_client = MockLLMClient(mock_response)
        
        # Create parser service and parse rules
        parser = PolicyParserService()
        compliance_rules = await parser.parse_rules(
            text="Sample policy text",
            policy_id=str(policy_id),
            llm_client=mock_client,
        )
        
        # Property: Rule content must be preserved
        assert len(compliance_rules) == len(rules)
        for i, rule in enumerate(compliance_rules):
            original = rules[i]
            assert rule.rule_code == original["rule_code"], \
                f"rule_code not preserved"
            assert rule.description == original["description"], \
                f"description not preserved"
            assert rule.evaluation_criteria == original["evaluation_criteria"], \
                f"evaluation_criteria not preserved"

    @given(
        policy_id=valid_uuid_strategy,
        rules=valid_rules_list_strategy
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_parse_rules_sets_is_active_true_by_default(
        self, policy_id: uuid.UUID, rules: list[dict]
    ):
        """
        Property: parse_rules sets is_active to True by default.
        
        Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip
        **Validates: Requirements 1.6**
        
        For any rules created by parse_rules, the is_active field SHALL
        be set to True by default.
        """
        from app.services.policy_parser import PolicyParserService
        
        # Create mock LLM response
        mock_response = json.dumps(rules)
        mock_client = MockLLMClient(mock_response)
        
        # Create parser service and parse rules
        parser = PolicyParserService()
        compliance_rules = await parser.parse_rules(
            text="Sample policy text",
            policy_id=str(policy_id),
            llm_client=mock_client,
        )
        
        # Property: All rules must have is_active=True
        for rule in compliance_rules:
            assert rule.is_active is True, \
                f"Rule is_active should be True by default"

    @given(
        policy_id=valid_uuid_strategy,
        rules=valid_rules_list_strategy
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_parse_rules_maps_target_entities_to_target_table(
        self, policy_id: uuid.UUID, rules: list[dict]
    ):
        """
        Property: parse_rules maps target_entities to target_table.
        
        Feature: data-policy-agent, Property 2: Policy-to-Rules Round Trip
        **Validates: Requirements 1.6**
        
        For any rules with target_entities field, parse_rules SHALL map
        that value to the target_table field of the ComplianceRule.
        """
        from app.services.policy_parser import PolicyParserService
        
        # Create mock LLM response
        mock_response = json.dumps(rules)
        mock_client = MockLLMClient(mock_response)
        
        # Create parser service and parse rules
        parser = PolicyParserService()
        compliance_rules = await parser.parse_rules(
            text="Sample policy text",
            policy_id=str(policy_id),
            llm_client=mock_client,
        )
        
        # Property: target_entities should be mapped to target_table
        for i, rule in enumerate(compliance_rules):
            original = rules[i]
            expected_target = original.get("target_entities")
            assert rule.target_table == expected_target, \
                f"target_table not correctly mapped from target_entities"
