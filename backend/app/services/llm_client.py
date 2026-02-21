"""LLM Client abstraction for OpenAI and Gemini APIs.

This module provides a unified interface for interacting with LLM providers
to extract compliance rules, generate SQL queries, explain violations,
and suggest remediations.
"""

import asyncio
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

RULE_VALIDATION_PROMPT = """
You are a senior compliance expert. You have been given a set of rules extracted from a policy document by another AI model.
Your job is to VALIDATE and REFINE these rules by comparing them against the original policy text.

Original Policy Document:
{policy_text}

Extracted Rules (JSON):
{extracted_rules}

For each rule, you must:
1. VERIFY it is actually stated or clearly implied in the policy document. Remove any hallucinated rules.
2. REFINE the evaluation_criteria to be more specific and actionable for database queries.
3. CORRECT any inaccuracies in the description or severity.
4. KEEP the same rule_code format.

Return ONLY a JSON array of validated rules. Use the same format:
[
  {{
    "rule_code": "DATA-001",
    "description": "...",
    "evaluation_criteria": "...",
    "severity": "low|medium|high|critical",
    "target_entities": "..."
  }}
]

If a rule is hallucinated (not supported by the policy text), REMOVE it entirely.
If a rule is valid but imprecise, REFINE it.
Return ONLY the JSON array, no additional text.
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
        """Extract compliance rules from policy text using the LLM.

        Sends the policy text to the model and parses the JSON response
        into a list of rule dictionaries.
        """
        prompt = RULE_EXTRACTION_PROMPT.format(policy_text=policy_text)
        response = await self._generate(prompt)

        # Parse JSON from response
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            rules = json.loads(cleaned)
            if isinstance(rules, list):
                return rules
            logger.warning(f"LLM returned non-list type: {type(rules)}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return []

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

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """Initialize the Gemini client.
        
        Args:
            api_key: Google Gemini API key.
            model: Model name to use (default: gemini-2.5-flash).
        """
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)

    def _generate_sync(self, prompt: str) -> str:
        """Synchronous Gemini generation (runs in thread)."""
        response = self.model.generate_content(
            prompt,
            generation_config={"temperature": 0.1},
        )
        return response.text or ""

    async def _generate(self, prompt: str) -> str:
        """Generate a response using Gemini API.
        
        Runs the synchronous Gemini call in a separate thread
        to avoid blocking the async event loop and breaking
        SQLAlchemy's greenlet context.
        """
        return await asyncio.to_thread(self._generate_sync, prompt)


class LLMClient:
    """Factory class that implements a dual-model AI pipeline.
    
    For rule extraction, uses a two-step pipeline:
      Step 1: Gemini 2.5 Flash (fast extraction)
      Step 2: Gemini 2.5 Pro (validation & refinement)
    
    This reduces hallucination and improves rule quality.
    For other operations (SQL, explanations), uses the Flash model.
    
    Usage:
        client = LLMClient()
        rules = await client.extract_rules(policy_text)  # uses pipeline
        sql = await client.generate_sql(rule, schema)
    """

    def __init__(self):
        """Initialize both Flash and Pro clients for the pipeline."""
        settings = get_settings()
        self._client = self._create_client(settings)
        self._validator = self._create_validator(settings)

    def _create_client(self, settings) -> BaseLLMClient:
        """Create the primary (Flash) LLM client for fast extraction."""
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
            return GeminiClient(
                api_key=settings.gemini_api_key,
                model="gemini-2.5-flash"
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def _create_validator(self, settings) -> BaseLLMClient | None:
        """Create the validator (Pro) client for rule refinement.
        
        Returns None if Gemini is not the provider (falls back to single-model).
        """
        provider = settings.llm_provider.lower()
        if provider in ("gemini", "google") and settings.gemini_api_key:
            try:
                return GeminiClient(
                    api_key=settings.gemini_api_key,
                    model="gemini-2.5-pro"
                )
            except Exception as e:
                logger.warning(f"Failed to create Pro validator, falling back to single-model: {e}")
                return None
        return None

    async def extract_rules(self, policy_text: str) -> list[dict[str, Any]]:
        """Extract compliance rules using the dual-model pipeline.
        
        Step 1: Gemini Flash extracts rules (fast)
        Step 2: Gemini Pro validates and refines them (accurate)
        
        Falls back to single-model if Pro is unavailable.
        """
        # Step 1: Fast extraction with Flash
        logger.info("Pipeline Step 1: Extracting rules with Gemini Flash...")
        raw_rules = await self._client.extract_rules(policy_text)
        logger.info(f"Flash extracted {len(raw_rules)} rules")

        # Step 2: Validate with Pro (if available)
        if self._validator and raw_rules:
            try:
                logger.info("Pipeline Step 2: Validating rules with Gemini Pro...")
                validation_prompt = RULE_VALIDATION_PROMPT.format(
                    policy_text=policy_text,
                    extracted_rules=json.dumps(raw_rules, indent=2)
                )
                response = await self._validator._generate(validation_prompt)

                # Parse validated rules
                cleaned = response.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

                validated_rules = json.loads(cleaned)
                if isinstance(validated_rules, list):
                    logger.info(
                        f"Pro validated: {len(validated_rules)} rules "
                        f"(removed {len(raw_rules) - len(validated_rules)} hallucinated)"
                    )
                    return validated_rules
                else:
                    logger.warning("Pro returned non-list, using Flash results")
            except Exception as e:
                logger.warning(f"Pro validation failed, using Flash results: {e}")

        return raw_rules

    async def generate_sql(self, rule: dict[str, Any], schema: dict[str, Any]) -> str:
        """Generate SQL query to detect rule violations."""
        return await self._client.generate_sql(rule, schema)

    async def explain_violation(self, rule: dict[str, Any], record: dict[str, Any]) -> str:
        """Generate explanation for why a record violates a rule."""
        return await self._client.explain_violation(rule, record)

    async def suggest_remediation(self, violation: dict[str, Any]) -> str:
        """Generate remediation suggestion for a violation."""
        return await self._client.suggest_remediation(violation)


def get_llm_client() -> LLMClient:
    """Get an LLM client instance.
    
    This is a convenience function for dependency injection in FastAPI.
    
    Returns:
        An LLMClient instance configured based on application settings.
    """
    return LLMClient()
