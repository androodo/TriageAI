"""Issue Draft Service — generates GitHub/Jira issue drafts from triage results."""

from __future__ import annotations

from app.models.issue_draft import IssueFormat
from app.services.llm import llm_provider
from app.utils.logging import get_logger

log = get_logger(__name__)


SYSTEM_PROMPT = """You are a senior developer writing a high-quality bug report issue draft. Format the output as clean GitHub/Jira markdown that a developer can copy and paste directly."""

GITHUB_ISSUE_TEMPLATE = """Based on the following CI failure triage, generate a complete GitHub issue draft.

## Triage Result
- Category: {failure_category}
- Confidence: {confidence_score:.0%}
- Summary: {summary}
- Root Cause: {root_cause}
- Suggested Steps: {suggested_steps}
- Owner Guess: {owner_guess}
- Repo: {repo_name}
- Branch: {branch}
- Commit: {commit_sha}
- Test Suite: {test_suite_name}
- Failed Tests: {failed_tests}

## Similar Past Failures
{similar_failures}

Generate a JSON object with:
{{
  "title": "GitHub issue title (max 100 chars, descriptive)",
  "body": "Full markdown issue body with sections: ## Summary, ## Root Cause, ## Steps to Reproduce, ## Expected vs Actual, ## Suggested Fix, ## Labels (array of GitHub label names)",
  "labels": ["bug", "ci-failure", "area/..."] (2-5 relevant labels),
  "assignee_guess": "team or owner username if guessable"
}}

Respond with ONLY valid JSON matching this schema."""


JIRA_ISSUE_TEMPLATE = """Based on the following CI failure triage, generate a complete Jira issue draft.

## Triage Result
- Category: {failure_category}
- Confidence: {confidence_score:.0%}
- Summary: {summary}
- Root Cause: {root_cause}
- Suggested Steps: {suggested_steps}
- Owner Guess: {owner_guess}
- Repo: {repo_name}
- Branch: {branch}
- Commit: {commit_sha}

## Similar Past Failures
{similar_failures}

Generate a JSON object with:
{{
  "title": "Jira issue title (max 100 chars)",
  "body": "Full Jira-flavored markdown body with sections for description, root cause, reproduction steps, suggested fix",
  "labels": ["bug", "ci-failure", "area/..."] (2-5 labels),
  "assignee_guess": "team or owner name if guessable"
}}

Respond with ONLY valid JSON matching this schema."""


class IssueDraftService:
    """Generates formatted issue drafts for GitHub and Jira."""

    def __init__(self) -> None:
        self._llm = llm_provider

    async def generate(
        self,
        triage_data: dict,
        *,
        repo_name: str,
        branch: str,
        commit_sha: str,
        test_suite_name: str,
        failed_tests: list[str],
        similar_failures: list[dict] | None = None,
        format: IssueFormat = IssueFormat.GITHUB,
    ) -> dict:
        """Generate an issue draft from triage data."""

        suggested_steps = triage_data.get("suggested_steps", [])
        if isinstance(suggested_steps, list):
            steps_text = "\n".join(f"- {s}" for s in suggested_steps)
        else:
            steps_text = str(suggested_steps)

        similar_text = "No similar past failures found."
        if similar_failures:
            similar_text = "\n".join(
                f"- [{s.get('commit_sha', 'unknown')[:8]}] "
                f"{s.get('summary', 'No summary')} "
                f"(confidence: {s.get('similarity_score', 0):.0%})"
                for s in similar_failures[:3]
            )

        owner_guess = triage_data.get("owner_guess") or "Unassigned"
        failed_tests_text = ", ".join(failed_tests) if failed_tests else "None"

        template = GITHUB_ISSUE_TEMPLATE if format == IssueFormat.GITHUB else JIRA_ISSUE_TEMPLATE

        user_prompt = template.format(
            failure_category=triage_data.get("failure_category", "unknown"),
            confidence_score=triage_data.get("confidence_score", 0.5),
            summary=triage_data.get("summary", "No summary available."),
            root_cause=triage_data.get("root_cause", "Unknown."),
            suggested_steps=steps_text,
            owner_guess=owner_guess,
            repo_name=repo_name,
            branch=branch,
            commit_sha=commit_sha,
            test_suite_name=test_suite_name,
            failed_tests=failed_tests_text,
            similar_failures=similar_text,
        )

        log.info("Generating issue draft", format=format.value, repo=repo_name)

        response = await self._llm.chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        return self._parse_response(response)

    def _parse_response(self, raw: str) -> dict:
        """Parse JSON issue draft from LLM response."""
        import json

        text = raw.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 3:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            return {
                "title": "CI Failure — Manual Investigation Required",
                "body": f"Automated draft generation failed. Raw output:\n\n{raw[:1000]}",
                "labels": ["bug", "ci-failure"],
                "assignee_guess": None,
            }