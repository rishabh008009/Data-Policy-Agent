"""LLM Client abstraction for OpenAI and Gemini APIs.

This module provides a unified interface for interacting with LLM providers
to extract compliance rules, generate SQL queries, explain violations,
and suggest remediations.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


# Prompt Templates
RULE_EXTRACTION_PROMPT = """
Analyze the following policy document and extract all compliance rules.
For each rule, provide:
1. rule_code: A short identifier (e.g., "DATA-001")
2. description: Human-readable description of the rule
3. evaluation_criteria: Specific conditions that constitute a violation
4. severity: low, medium, high, or critical
5. target_entities: What type of data this rule applies to

Policy Document:
{policy_text}

Return as JSON array of rules. Example format:
[
  {{
    "rule_code": "DATA-001",
    "description": "Personal data must be encrypted at rest",
    "evaluation_criteria": "Any record containing PII fields (email, ssn, phone) must have is_encrypted=true",
    "severity": "high",
    "target_entities": "user data, customer records"
  }}
]

Return ONLY the JSON array, no additional text.
"""

SQL_GENERATION_PROMPT = """
Given the following compliance rule and database schema, generate a SQL query
that identifies records violating this rule.

Rule: {rule_description}
Evaluation Criteria: {evaluation_criteria}

Database Schema:
{schema_json}

Return only the SQL query that selects violating records.
Include the primary key and relevant columns in the SELECT.
The query should return records that VIOLATE the rule (non-compliant records).

Return ONLY the SQL query, no additional text or explanation.
"""

JUSTIFICATION_PROMPT = """
Explain why the following database record violates the compliance rule.
Be specific and reference the actual field values.

Rule: {rule_description}
Evaluation Criteria: {evaluation_criteria}

Record Data:
{record_json}

Provide a clear, concise explanation suitable for a compliance review.
The explanation should:
1. State which specific field(s) are non-compliant
2. Explain what the expected value or condition should be
3. Reference the actual values found in the record

Return ONLY the explanation text, no additional formatting.
"""

REMEDIATION_PROMPT = """
Suggest remediation steps for the following compliance violation.

Rule: {rule_description}
Violation: {justification}
Record Data: {record_json}

Provide specific, actionable steps to resolve this violation.
The remediation should:
1. Be specific to the actual data values
2. Provide clear steps that can be followed
3. Consider any dependencies or side effects

Return ONLY the remediation steps, no additional formatting.
"""


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def _generate(self, prompt: str) -> str:
        """Generate a response from the LLM.
        
        Args:
            prompt: The prompt to send to the LLM.
            
        Returns:
            The generated response text.
        """
        pass

    async def extract_rules(self, policy_text: str) -> list[dict[str, Any]]:
        """Extract compliance rules from policy text.
        
        Args:
            policy_text: The raw text extracted from a policy document.
            
        Returns:
            A list of dictionaries containing extracted rules with fields:
            - rule_code: Short identifier for the rule
            - description: Human-readable description
            - evaluation_criteria: Conditions that constitute a violation
            - severity: low, medium, high, or critical
            - target_entities: What type of data the rule applies to
            
        Raises:
            ValueError: If the LLM response cannot be parsed as valid JSON.
        """
        prompt = RULE_EXTRACTION_PROMPT.format(policy_text=policy_text)
        response = await self._generate(prompt)
        
        try:
            # Clean up response - remove markdown code blocks if present
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            elif cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            rules = json.loads(cleaned_response)
            
            if not isinstance(rules, list):
                raise ValueError("Expected a JSON array of rules")
            
            # Validate required fields
            required_fields = {"rule_code", "description", "evaluation_criteria", "severity"}
            for rule in rules:
                missing_fields = required_fields - set(rule.keys())
                if missing_fields:
                    logger.warning(f"Rule missing fields {missing_fields}: {rule}")
                    # Add empty values for missing fields
                    for field in missing_fields:
                        rule[field] = ""
            
            return rules
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {response}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")

    async def generate_sql(self, rule: dict[str, Any], schema: dict[str, Any]) -> str:
        """Generate SQL query to detect rule violations.
        
        Args:
            rule: Dictionary containing rule details with 'description' and 
                  'evaluation_criteria' fields.
            schema: Dictionary containing database schema information.
            
        Returns:
            A SQL query string that selects violating records.
        """
        prompt = SQL_GENERATION_PROMPT.format(
            rule_description=rule.get("description", ""),
            evaluation_criteria=rule.get("evaluation_criteria", ""),
            schema_json=json.dumps(schema, indent=2)
        )
        response = await self._generate(prompt)
        
        # Clean up response - remove markdown code blocks if present
        cleaned_response = response.strip()
        if cleaned_response.startswith("```sql"):
            cleaned_response = cleaned_response[6:]
        elif cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        
        return cleaned_response.strip()

    async def explain_violation(self, rule: dict[str, Any], record: dict[str, Any]) -> str:
        """Generate explanation for why a record violates a rule.
        
        Args:
            rule: Dictionary containing rule details with 'description' and
                  'evaluation_criteria' fields.
            record: Dictionary containing the violating record's data.
            
        Returns:
            A human-readable explanation of the violation.
        """
        prompt = JUSTIFICATION_PROMPT.format(
            rule_description=rule.get("description", ""),
            evaluation_criteria=rule.get("evaluation_criteria", ""),
            record_json=json.dumps(record, indent=2, default=str)
        )
        response = await self._generate(prompt)
        return response.strip()

    async def suggest_remediation(self, violation: dict[str, Any]) -> str:
        """Generate remediation suggestion for a violation.
        
        Args:
            violation: Dictionary containing violation details including:
                - rule_description: Description of the violated rule
                - justification: Explanation of why the record violates the rule
                - record_data: The violating record's data
                
        Returns:
            Actionable remediation steps to resolve the violation.
        """
        prompt = REMEDIATION_PROMPT.format(
            rule_description=violation.get("rule_description", ""),
            justification=violation.get("justification", ""),
            record_json=json.dumps(violation.get("record_data", {}), indent=2, default=str)
        )
        response = await self._generate(prompt)
        return response.strip()


class OpenAIClient(BaseLLMClient):
    """LLM client implementation using OpenAI API."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        """Initialize the OpenAI client.
        
        Args:
            api_key: OpenAI API key.
            model: Model name to use (default: gpt-4o).
        """
        from openai import AsyncOpenAI
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def _generate(self, prompt: str) -> str:
        """Generate a response using OpenAI API.
        
        Args:
            prompt: The prompt to send to the model.
            
        Returns:
            The generated response text.
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a compliance analysis assistant. Provide accurate, structured responses."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Low temperature for more consistent outputs
        )
        return response.choices[0].message.content or ""


class GeminiClient(BaseLLMClient):
    """LLM client implementation using Google Gemini API."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        """Initialize the Gemini client.
        
        Args:
            api_key: Google Gemini API key.
            model: Model name to use (default: gemini-1.5-flash).
        """
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)

    async def _generate(self, prompt: str) -> str:
        """Generate a response using Gemini API.
        
        Args:
            prompt: The prompt to send to the model.
            
        Returns:
            The generated response text.
        """
        # Gemini's generate_content is synchronous, but we wrap it for consistency
        response = self.model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,  # Low temperature for more consistent outputs
            }
        )
        return response.text or ""


class LLMClient:
    """Factory class for creating LLM clients based on configuration.
    
    This class provides a unified interface for interacting with different
    LLM providers (OpenAI, Gemini) based on application configuration.
    
    Usage:
        client = LLMClient()
        rules = await client.extract_rules(policy_text)
        sql = await client.generate_sql(rule, schema)
        explanation = await client.explain_violation(rule, record)
        remediation = await client.suggest_remediation(violation)
    """

    def __init__(self):
        """Initialize the LLM client based on configuration."""
        settings = get_settings()
        self._client = self._create_client(settings)

    def _create_client(self, settings) -> BaseLLMClient:
        """Create the appropriate LLM client based on settings.
        
        Args:
            settings: Application settings containing LLM configuration.
            
        Returns:
            An instance of the appropriate LLM client.
            
        Raises:
            ValueError: If the configured provider is not supported or
                       the required API key is missing.
        """
        provider = settings.llm_provider.lower()
        
        if provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key is required when using OpenAI provider")
            return OpenAIClient(
                api_key=settings.openai_api_key,
                model=settings.llm_model
            )
        elif provider in ("gemini", "google"):
            if not settings.gemini_api_key:
                raise ValueError("Gemini API key is required when using Gemini provider")
            # Map common model names to Gemini equivalents
            model = settings.llm_model
            if model.startswith("gpt"):
                model = "gemini-2.0-flash"  # Default Gemini model
            elif model in ("gemini", "gemini-1.5-flash", "gemini-1.5-pro"):
                model = "gemini-2.0-flash"  # Use current model
            return GeminiClient(
                api_key=settings.gemini_api_key,
                model=model
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    async def extract_rules(self, policy_text: str) -> list[dict[str, Any]]:
        """Extract compliance rules from policy text.
        
        Args:
            policy_text: The raw text extracted from a policy document.
            
        Returns:
            A list of dictionaries containing extracted rules.
        """
        return await self._client.extract_rules(policy_text)

    async def generate_sql(self, rule: dict[str, Any], schema: dict[str, Any]) -> str:
        """Generate SQL query to detect rule violations.
        
        Args:
            rule: Dictionary containing rule details.
            schema: Dictionary containing database schema information.
            
        Returns:
            A SQL query string that selects violating records.
        """
        return await self._client.generate_sql(rule, schema)

    async def explain_violation(self, rule: dict[str, Any], record: dict[str, Any]) -> str:
        """Generate explanation for why a record violates a rule.
        
        Args:
            rule: Dictionary containing rule details.
            record: Dictionary containing the violating record's data.
            
        Returns:
            A human-readable explanation of the violation.
        """
        return await self._client.explain_violation(rule, record)

    async def suggest_remediation(self, violation: dict[str, Any]) -> str:
        """Generate remediation suggestion for a violation.
        
        Args:
            violation: Dictionary containing violation details.
            
        Returns:
            Actionable remediation steps to resolve the violation.
        """
        return await self._client.suggest_remediation(violation)


def get_llm_client() -> LLMClient:
    """Get an LLM client instance.
    
    This is a convenience function for dependency injection in FastAPI.
    
    Returns:
        An LLMClient instance configured based on application settings.
    """
    return LLMClient()
