"""Triage Service — AI-powered failure classification and root cause analysis."""

from __future__ import annotations

from uuid import UUID

from app.models.triage_result import FailureCategory
from app.services.llm import llm_provider
from app.utils.logging import get_logger

log = get_logger(__name__)


# ── Prompt templates ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior Site Reliability Engineer with deep expertise in CI/CD debugging, test failure analysis, and developer productivity. You analyze CI failure logs and provide precise, actionable diagnostics.

Respond ONLY with valid JSON matching the schema provided. No markdown, no commentary."""

USER_PROMPT_TEMPLATE = """Analyze the following CI failure and provide a detailed triage.

## CI Run Metadata
- Repository: {repo_name}
- Branch: {branch}
- Commit: {commit_sha}
- Environment: {environment}
- Test Suite: {test_suite_name}
- Failed Tests: {failed_tests}
- Exception Types: {exception_names}

## Failure Log (cleaned excerpt, first 3000 chars)
```
{cleaned_log_text}
```

## Stack Traces
{stack_traces}

## Return a JSON object with exactly these fields:
{{
  "failure_category": "test_assertion_failure" | "application_code_bug" | "flaky_test" | "dependency_configuration_issue" | "infrastructure_environment_failure" | "timeout_performance_issue" | "unknown",
  "confidence_score": float between 0.0 and 1.0,
  "summary": "one-sentence summary of what failed",
  "root_cause": "detailed explanation of the likely root cause",
  "suggested_steps": ["step 1", "step 2", "step 3"],
  "owner_guess": "best guess of team/owner responsible (e.g. 'backend-payments', 'infra-team', or null)",
  "issue_title": "concise issue title suitable for GitHub/Jira (max 100 chars)",
  "issue_body": "detailed markdown issue body with context, steps to reproduce, and expected vs actual behavior"
}}"""


class TriageService:
    """Generates AI-powered failure triage results."""

    CATEGORY_DESCRIPTIONS = {
        FailureCategory.TEST_ASSERTION_FAILURE: "A test assertion failed — the code under test returned an unexpected value or state.",
        FailureCategory.APPLICATION_CODE_BUG: "Production code has a bug that caused the test to fail.",
        FailureCategory.FLAKY_TEST: "The test behaves non-deterministically — passes and fails without code changes.",
        FailureCategory.DEPENDENCY_CONFIGURATION_ISSUE: "A library version mismatch, missing dependency, or misconfiguration caused the failure.",
        FailureCategory.INFRASTRUCTURE_ENVIRONMENT_FAILURE: "An infrastructure or environment issue (DB, network, disk, etc.) caused the failure.",
        FailureCategory.TIMEOUT_PERFORMANCE_ISSUE: "The operation exceeded a timeout threshold or resource limit.",
        FailureCategory.UNKNOWN: "Insufficient information to determine the root cause.",
    }

    def __init__(self) -> None:
        self._llm = llm_provider

    async def triage(
        self,
        cleaned_log_text: str,
        stack_traces: list[str],
        exception_names: list[str],
        failed_tests: list[str],
        *,
        repo_name: str,
        branch: str,
        commit_sha: str,
        environment: str,
        test_suite_name: str,
    ) -> dict:
        """Run AI triage on a parsed failure log and return structured result."""

        stack_trace_text = (
            "\n\n".join(f"--- Trace {i+1} ---\n{t}" for i, t in enumerate(stack_traces[:3]))
            or "No stack trace available"
        )

        failed_tests_text = ", ".join(failed_tests) if failed_tests else "None"
        exception_text = ", ".join(exception_names) if exception_names else "None detected"

        user_prompt = USER_PROMPT_TEMPLATE.format(
            repo_name=repo_name,
            branch=branch,
            commit_sha=commit_sha,
            environment=environment,
            test_suite_name=test_suite_name,
            failed_tests=failed_tests_text,
            exception_names=exception_text,
            cleaned_log_text=cleaned_log_text[:3000],
            stack_traces=stack_trace_text[:2000],
        )

        log.info("Sending triage request to LLM", repo=repo_name, branch=branch)

        response_text = await self._llm.chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=2500,
        )

        result = self._parse_llm_response(response_text)
        log.info(
            "Triage complete",
            category=result["failure_category"],
            confidence=result["confidence_score"],
        )
        return result

    def _parse_llm_response(self, raw: str) -> dict:
        """Parse JSON from LLM response with fallback heuristics."""
        import json

        # Try to extract JSON from the response
        text = raw.strip()

        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    data = json.loads(text[start:end])
                except json.JSONDecodeError:
                    return self._fallback_result(raw)

        # Validate required fields with defaults
        valid_categories = {c.value for c in FailureCategory}
        if data.get("failure_category") not in valid_categories:
            data["failure_category"] = FailureCategory.UNKNOWN.value

        data.setdefault("confidence_score", 0.5)
        data.setdefault("summary", "AI triage could not determine a clear summary.")
        data.setdefault("root_cause", "Unable to determine root cause from available data.")
        data.setdefault("suggested_steps", ["Review the failure log manually.", "Check recent commits on this branch."])
        data.setdefault("owner_guess", None)
        data.setdefault("issue_title", "CI failure requires investigation")
        data.setdefault("issue_body", f"Triage analysis unavailable. Raw LLM output:\n\n{raw[:1000]}")

        return data

    def _fallback_result(self, raw: str) -> dict:
        """Return a safe fallback triage result when JSON parsing fails."""
        return {
            "failure_category": FailureCategory.UNKNOWN.value,
            "confidence_score": 0.5,
            "summary": "AI triage could not determine a clear summary.",
            "root_cause": "Unable to determine root cause from available data.",
            "suggested_steps": [
                "Review the failure log manually.",
                "Check recent commits on this branch.",
                "Run the failing tests locally to reproduce.",
            ],
            "owner_guess": None,
            "issue_title": "CI failure requires investigation",
            "issue_body": f"Automated triage failed to parse the LLM response.\n\nRaw output:\n\n```\n{raw[:1000]}\n```",
        }