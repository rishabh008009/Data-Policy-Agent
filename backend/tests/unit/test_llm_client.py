"""Unit tests for the LLM client abstraction."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_client import (
    BaseLLMClient,
    OpenAIClient,
    GeminiClient,
    LLMClient,
    RULE_EXTRACTION_PROMPT,
    SQL_GENERATION_PROMPT,
    JUSTIFICATION_PROMPT,
    REMEDIATION_PROMPT,
)


class TestBaseLLMClient:
    """Tests for the BaseLLMClient abstract class methods."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock LLM client for testing."""
        class MockLLMClient(BaseLLMClient):
            async def _generate(self, prompt: str) -> str:
                return ""
        
        client = MockLLMClient()
        client._generate = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_extract_rules_parses_valid_json(self, mock_client):
        """Test that extract_rules correctly parses valid JSON response."""
        mock_response = json.dumps([
            {
                "rule_code": "DATA-001",
                "description": "Test rule",
                "evaluation_criteria": "Test criteria",
                "severity": "high",
                "target_entities": "users"
            }
        ])
        mock_client._generate.return_value = mock_response
        
        rules = await mock_client.extract_rules("Sample policy text")
        
        assert len(rules) == 1
        assert rules[0]["rule_code"] == "DATA-001"
        assert rules[0]["description"] == "Test rule"
        assert rules[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_extract_rules_handles_markdown_code_blocks(self, mock_client):
        """Test that extract_rules strips markdown code blocks from response."""
        mock_response = """```json
[
    {
        "rule_code": "DATA-001",
        "description": "Test rule",
        "evaluation_criteria": "Test criteria",
        "severity": "medium"
    }
]
```"""
        mock_client._generate.return_value = mock_response
        
        rules = await mock_client.extract_rules("Sample policy text")
        
        assert len(rules) == 1
        assert rules[0]["rule_code"] == "DATA-001"

    @pytest.mark.asyncio
    async def test_extract_rules_adds_missing_fields(self, mock_client):
        """Test that extract_rules adds empty values for missing required fields."""
        mock_response = json.dumps([
            {
                "rule_code": "DATA-001",
                "description": "Test rule"
                # Missing evaluation_criteria and severity
            }
        ])
        mock_client._generate.return_value = mock_response
        
        rules = await mock_client.extract_rules("Sample policy text")
        
        assert len(rules) == 1
        assert rules[0]["evaluation_criteria"] == ""
        assert rules[0]["severity"] == ""

    @pytest.mark.asyncio
    async def test_extract_rules_raises_on_invalid_json(self, mock_client):
        """Test that extract_rules raises ValueError on invalid JSON."""
        mock_client._generate.return_value = "This is not valid JSON"
        
        with pytest.raises(ValueError, match="Invalid JSON response"):
            await mock_client.extract_rules("Sample policy text")

    @pytest.mark.asyncio
    async def test_extract_rules_raises_on_non_array(self, mock_client):
        """Test that extract_rules raises ValueError when response is not an array."""
        mock_client._generate.return_value = json.dumps({"rule": "not an array"})
        
        with pytest.raises(ValueError, match="Expected a JSON array"):
            await mock_client.extract_rules("Sample policy text")

    @pytest.mark.asyncio
    async def test_generate_sql_returns_cleaned_query(self, mock_client):
        """Test that generate_sql returns cleaned SQL query."""
        mock_client._generate.return_value = """```sql
SELECT * FROM users WHERE is_active = false;
```"""
        
        rule = {"description": "Test rule", "evaluation_criteria": "Test criteria"}
        schema = {"tables": [{"name": "users", "columns": ["id", "is_active"]}]}
        
        sql = await mock_client.generate_sql(rule, schema)
        
        assert sql == "SELECT * FROM users WHERE is_active = false;"
        assert "```" not in sql

    @pytest.mark.asyncio
    async def test_explain_violation_returns_explanation(self, mock_client):
        """Test that explain_violation returns the explanation text."""
        mock_client._generate.return_value = "The record violates the rule because..."
        
        rule = {"description": "Test rule", "evaluation_criteria": "Test criteria"}
        record = {"id": 1, "field": "value"}
        
        explanation = await mock_client.explain_violation(rule, record)
        
        assert explanation == "The record violates the rule because..."

    @pytest.mark.asyncio
    async def test_suggest_remediation_returns_steps(self, mock_client):
        """Test that suggest_remediation returns remediation steps."""
        mock_client._generate.return_value = "1. Update the field\n2. Verify the change"
        
        violation = {
            "rule_description": "Test rule",
            "justification": "Field is invalid",
            "record_data": {"id": 1}
        }
        
        remediation = await mock_client.suggest_remediation(violation)
        
        assert "Update the field" in remediation


class TestOpenAIClient:
    """Tests for the OpenAI client implementation."""

    @pytest.mark.asyncio
    async def test_openai_client_initialization(self):
        """Test that OpenAI client initializes correctly."""
        with patch("openai.AsyncOpenAI") as mock_openai:
            client = OpenAIClient(api_key="test-key", model="gpt-4o")
            
            mock_openai.assert_called_once_with(api_key="test-key")
            assert client.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_openai_client_generate(self):
        """Test that OpenAI client generates responses correctly."""
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Generated response"
            
            mock_client_instance = MagicMock()
            mock_client_instance.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client_instance
            
            client = OpenAIClient(api_key="test-key", model="gpt-4o")
            result = await client._generate("Test prompt")
            
            assert result == "Generated response"
            mock_client_instance.chat.completions.create.assert_called_once()


class TestGeminiClient:
    """Tests for the Gemini client implementation."""

    def test_gemini_client_initialization(self):
        """Test that Gemini client initializes correctly."""
        with patch("google.generativeai.configure") as mock_configure, \
             patch("google.generativeai.GenerativeModel") as mock_model_class:
            mock_model = MagicMock()
            mock_model_class.return_value = mock_model
            
            client = GeminiClient(api_key="test-key", model="gemini-1.5-flash")
            
            mock_configure.assert_called_once_with(api_key="test-key")
            mock_model_class.assert_called_once_with("gemini-1.5-flash")

    @pytest.mark.asyncio
    async def test_gemini_client_generate(self):
        """Test that Gemini client generates responses correctly."""
        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel") as mock_model_class:
            mock_response = MagicMock()
            mock_response.text = "Generated response"
            
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            client = GeminiClient(api_key="test-key", model="gemini-1.5-flash")
            result = await client._generate("Test prompt")
            
            assert result == "Generated response"


class TestLLMClientFactory:
    """Tests for the LLMClient factory class."""

    def test_creates_openai_client_when_configured(self):
        """Test that LLMClient creates OpenAI client when provider is openai."""
        with patch("app.services.llm_client.get_settings") as mock_settings, \
             patch("openai.AsyncOpenAI"):
            mock_settings.return_value.llm_provider = "openai"
            mock_settings.return_value.openai_api_key = "test-key"
            mock_settings.return_value.llm_model = "gpt-4o"
            
            client = LLMClient()
            
            assert isinstance(client._client, OpenAIClient)

    def test_creates_gemini_client_when_configured(self):
        """Test that LLMClient creates Gemini client when provider is gemini."""
        with patch("app.services.llm_client.get_settings") as mock_settings, \
             patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel"):
            mock_settings.return_value.llm_provider = "gemini"
            mock_settings.return_value.gemini_api_key = "test-key"
            mock_settings.return_value.llm_model = "gemini-1.5-flash"
            
            client = LLMClient()
            
            assert isinstance(client._client, GeminiClient)

    def test_raises_error_for_missing_openai_key(self):
        """Test that LLMClient raises error when OpenAI key is missing."""
        with patch("app.services.llm_client.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "openai"
            mock_settings.return_value.openai_api_key = ""
            
            with pytest.raises(ValueError, match="OpenAI API key is required"):
                LLMClient()

    def test_raises_error_for_missing_gemini_key(self):
        """Test that LLMClient raises error when Gemini key is missing."""
        with patch("app.services.llm_client.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "gemini"
            mock_settings.return_value.gemini_api_key = ""
            
            with pytest.raises(ValueError, match="Gemini API key is required"):
                LLMClient()

    def test_raises_error_for_unsupported_provider(self):
        """Test that LLMClient raises error for unsupported provider."""
        with patch("app.services.llm_client.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "unsupported"
            
            with pytest.raises(ValueError, match="Unsupported LLM provider"):
                LLMClient()

    def test_maps_gpt_model_to_gemini_default(self):
        """Test that GPT model names are mapped to Gemini default when using Gemini."""
        with patch("app.services.llm_client.get_settings") as mock_settings, \
             patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel") as mock_model_class:
            mock_settings.return_value.llm_provider = "gemini"
            mock_settings.return_value.gemini_api_key = "test-key"
            mock_settings.return_value.llm_model = "gpt-4o"
            
            LLMClient()
            
            # Should use gemini-1.5-flash instead of gpt-4o
            mock_model_class.assert_called_once_with("gemini-1.5-flash")


class TestPromptTemplates:
    """Tests for prompt template formatting."""

    def test_rule_extraction_prompt_contains_placeholders(self):
        """Test that rule extraction prompt has required placeholder."""
        assert "{policy_text}" in RULE_EXTRACTION_PROMPT

    def test_sql_generation_prompt_contains_placeholders(self):
        """Test that SQL generation prompt has required placeholders."""
        assert "{rule_description}" in SQL_GENERATION_PROMPT
        assert "{evaluation_criteria}" in SQL_GENERATION_PROMPT
        assert "{schema_json}" in SQL_GENERATION_PROMPT

    def test_justification_prompt_contains_placeholders(self):
        """Test that justification prompt has required placeholders."""
        assert "{rule_description}" in JUSTIFICATION_PROMPT
        assert "{evaluation_criteria}" in JUSTIFICATION_PROMPT
        assert "{record_json}" in JUSTIFICATION_PROMPT

    def test_remediation_prompt_contains_placeholders(self):
        """Test that remediation prompt has required placeholders."""
        assert "{rule_description}" in REMEDIATION_PROMPT
        assert "{justification}" in REMEDIATION_PROMPT
        assert "{record_json}" in REMEDIATION_PROMPT
