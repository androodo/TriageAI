"""Tests for triage service helpers and Pydantic schema validation."""

from __future__ import annotations

import pytest

from app.models.triage_result import FailureCategory
from app.services.triage import TriageService


class TestTriageService:
    """Tests for TriageService._parse_llm_response()"""

    def test_parses_valid_json_response(self) -> None:
        svc = TriageService()
        raw = """\
{
  "failure_category": "application_code_bug",
  "confidence_score": 0.85,
  "summary": "Null pointer in payment processing",
  "root_cause": "Missing null check before calling .send()",
  "suggested_steps": ["Add null check", "Write regression test", "Deploy fix"],
  "owner_guess": "payments-team",
  "issue_title": "NullPointerException in checkout flow",
  "issue_body": "## Summary\\nPayment checkout fails..."
}"""
        result = svc._parse_llm_response(raw)

        assert result["failure_category"] == "application_code_bug"
        assert result["confidence_score"] == 0.85
        assert result["summary"] == "Null pointer in payment processing"
        assert result["owner_guess"] == "payments-team"
        assert len(result["suggested_steps"]) == 3

    def test_parses_json_with_markdown_fences(self) -> None:
        svc = TriageService()
        raw = """\
```json
{
  "failure_category": "flaky_test",
  "confidence_score": 0.65,
  "summary": "Race condition in concurrent test",
  "root_cause": "Test uses shared mutable state",
  "suggested_steps": ["Isolate test state", "Add mutex"],
  "owner_guess": "test-platform",
  "issue_title": "Flaky test: test_concurrent_file_access",
  "issue_body": "Test is non-deterministic"
}
```"""
        result = svc._parse_llm_response(raw)

        assert result["failure_category"] == "flaky_test"
        assert result["confidence_score"] == 0.65

    def test_handles_invalid_category_with_fallback(self) -> None:
        svc = TriageService()
        raw = '{"failure_category": "not_a_real_category", "confidence_score": 0.5, "summary": "test", "root_cause": "test", "suggested_steps": [], "issue_title": "test", "issue_body": "test"}'
        result = svc._parse_llm_response(raw)

        assert result["failure_category"] == FailureCategory.UNKNOWN.value

    def test_handles_malformed_json_with_fallback(self) -> None:
        svc = TriageService()
        raw = "This is not JSON at all, just plain text response from the model"
        result = svc._parse_llm_response(raw)

        assert result["failure_category"] == FailureCategory.UNKNOWN.value
        assert result["summary"] == "AI triage could not determine a clear summary."
        assert result["confidence_score"] == 0.5


class TestFailureCategories:
    """Verify all expected failure categories exist."""

    def test_all_categories_defined(self) -> None:
        expected = {
            "test_assertion_failure",
            "application_code_bug",
            "flaky_test",
            "dependency_configuration_issue",
            "infrastructure_environment_failure",
            "timeout_performance_issue",
            "unknown",
        }
        actual = {c.value for c in FailureCategory}
        assert expected == actual