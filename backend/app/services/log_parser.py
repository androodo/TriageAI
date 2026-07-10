"""Log Parser Service — extracts structured failure data from raw CI log text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.utils.logging import get_logger

if TYPE_CHECKING:
    pass

log = get_logger(__name__)


# ── Regex patterns ─────────────────────────────────────────────────────────────

# Python stack trace frame
PYTHON_FRAME_RE = re.compile(
    r'^  File "(?P<file>.+?)", line (?P<line>\d+)(?:, in (?P<func>.+?))?$',
    re.MULTILINE,
)
# Exception line: "ErrorType: message" or "ErrorType: message"
EXCEPTION_RE = re.compile(r"^(?P<name>[A-Z][a-zA-Z]+Error|ConnectionRefused|Timeout|OSError|ImportError|KeyError|TypeError|ValueError|AttributeError|RuntimeError|AssertionError|NotImplementedError|MemoryError|DiskFull|OutOfMemory|DependencyError|HttpError|ValidationError|SyntaxError|TabError|IndentationError|NameError|ZeroDivisionError|FileNotFoundError|PermissionError|IsADirectoryError|NotADirectoryError|ConnectionResetError|BrokenPipeError|AlreadyExistsError|InvalidStateError|OperationError|ProtocolError): (?P<msg>.+)$", re.MULTILINE)
# Pytest failure header
PYTEST_FAIL_RE = re.compile(
    r"^FAILED\s+(?P<file>.+?::.+?)(?:\s*-\s*(?P<msg>.+))?$",
    re.MULTILINE,
)
# Pytest assertion diff
PYTEST_ASSERT_RE = re.compile(
    r"^(-{3}|\+{3}|\*{3}|\@{3})\s+(.+)$",
    re.MULTILINE,
)
# Timeout keywords
TIMEOUT_KEYWORDS = re.compile(
    r"(?i)(timeout|timed?\s*out|took\s*too\s*long|deadline\s*exceeded|"
    r"exceeded\s*\d+[smh]|operation\s*expired|gave\s*up\s*waiting|"
    r"request\s*timeout|circleci\s*timeout|github\s*actions\s*timeout)",
)
# Dependency error keywords
DEP_ERROR_KEYWORDS = re.compile(
    r"(?i)(ModuleNotFoundError|ImportError|No\s*module\s*named|"
    r"Import\s*Error|version\s*mismatch|incompatible\s*version|"
    r"dependency.*error|failed\s*to\s*install|package\s*not\s*found|"
    r"npm\s*err|yarn\s*err|pip\s*err|poetry\s*error|Could\s*not\s*find|"
    r"Could\s*not\s*resolve|peer\s*dependency|unsatisfied\s*requirement)",
)
# Infrastructure error keywords
INFRA_ERROR_KEYWORDS = re.compile(
    r"(?i)(connection\s*refused|connection\s*reset|out\s*of\s*memory|"
    r"OOM|disk\s*full|no\s*space\s*left|network\s*error|503|502|500|"
    r"Bad\s*Gateway|Gateway\s*Timeout|service\s*unavailable|"
    r"internal\s*server\s*error|memory\s*limit|docker\s*error|"
    r"kubernetes|ECS|EC2|instance|replica\s*set|postgres|redis|mysql|"
    r"dynamodb|s3\s*error|rate\s*limit|TooManyRequests|rate\s*limited)",
)
# Git commit reference
COMMIT_REF_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
# Noise lines to remove
NOISE_RE = re.compile(
    r"(?i)^(collecting|collected|passed|passed with|skipped|"
    r"warnings summary|===.*===|---.*---|/usr/local|"
    r"platform|cached|not found|Requirement already satisfied|"
    r"Downloading|Installing|Successfully|exit code|"
    r"Process finished with exit code|See.*doc|"
    r"Coverage|coverage.py|noxfile|pip version|node version)$"
)


# ── Dataclass ──────────────────────────────────────────────────────────────────

@dataclass
class ParsedLog:
    """Structured output from the log parser."""

    raw_log_text: str
    cleaned_log_text: str
    extracted_errors: list[str] = field(default_factory=list)
    stack_traces: list[str] = field(default_factory=list)
    exception_names: list[str] = field(default_factory=list)
    failed_tests: list[str] = field(default_factory=list)
    timeout_indicators: bool = False
    dependency_errors: list[str] = field(default_factory=list)
    infrastructure_errors: list[str] = field(default_factory=list)


# ── LogParser ──────────────────────────────────────────────────────────────────

class LogParser:
    """Parses raw CI log text into structured failure data."""

    def parse(self, raw_log: str) -> ParsedLog:
        """Parse raw CI log text and return structured failure data."""
        if not raw_log or not raw_log.strip():
            return ParsedLog(raw_log_text=raw_log, cleaned_log_text="")

        lines = raw_log.splitlines()
        cleaned_lines: list[str] = []
        extracted_errors: list[str] = []
        stack_traces: list[str] = []
        exception_names: list[str] = []
        failed_tests: list[str] = []
        timeout_indicators = False
        dependency_errors: list[str] = []
        infrastructure_errors: list[str] = []

        in_trace = False
        current_trace: list[str] = []
        trace_start_line = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # Skip known noise
            if NOISE_RE.match(stripped):
                continue

            # Pytest failure header
            pf_match = PYTEST_FAIL_RE.match(stripped)
            if pf_match:
                test_path = pf_match.group("file")
                if test_path not in failed_tests:
                    failed_tests.append(test_path)
                cleaned_lines.append(line)
                continue

            # Exception line
            exc_match = EXCEPTION_RE.match(stripped)
            if exc_match:
                exc_name = exc_match.group("name")
                exc_msg = exc_match.group("msg")
                full_exc = f"{exc_name}: {exc_msg}" if exc_msg else exc_name
                if exc_name not in exception_names:
                    exception_names.append(exc_name)
                if full_exc not in extracted_errors:
                    extracted_errors.append(full_exc)
                # Start or continue stack trace
                if not in_trace:
                    in_trace = True
                    trace_start_line = i
                    current_trace = [line]
                else:
                    current_trace.append(line)
                cleaned_lines.append(line)
                continue

            # Stack trace frame (Python)
            if PYTHON_FRAME_RE.match(stripped):
                if not in_trace:
                    in_trace = True
                    trace_start_line = i
                    current_trace = []
                current_trace.append(line)
                cleaned_lines.append(line)
                continue

            # Continuation of trace (indented lines)
            if in_trace and line.startswith("    "):
                current_trace.append(line)
                cleaned_lines.append(line)
                continue

            # End of stack trace
            if in_trace and current_trace:
                in_trace = False
                trace_text = "\n".join(current_trace)
                if trace_text not in stack_traces:
                    stack_traces.append(trace_text)
                current_trace = []

            # Timeout indicators
            if TIMEOUT_KEYWORDS.search(stripped):
                timeout_indicators = True
                if stripped not in extracted_errors:
                    extracted_errors.append(stripped)
                cleaned_lines.append(line)
                continue

            # Dependency errors
            dep_match = DEP_ERROR_KEYWORDS.search(stripped)
            if dep_match:
                if stripped not in dependency_errors:
                    dependency_errors.append(stripped)
                if stripped not in extracted_errors:
                    extracted_errors.append(stripped)
                cleaned_lines.append(line)
                continue

            # Infrastructure errors
            if INFRA_ERROR_KEYWORDS.search(stripped):
                if stripped not in infrastructure_errors:
                    infrastructure_errors.append(stripped)
                if stripped not in extracted_errors:
                    extracted_errors.append(stripped)
                cleaned_lines.append(line)
                continue

            # Lines with error keywords anywhere
            if re.search(r"(?i)\b(error|fail(ed|ure)?|exception|traceback|crashed?)\b", stripped):
                if stripped not in extracted_errors:
                    extracted_errors.append(stripped)
                cleaned_lines.append(line)

        # Close any open trace
        if in_trace and current_trace:
            trace_text = "\n".join(current_trace)
            if trace_text not in stack_traces:
                stack_traces.append(trace_text)

        cleaned_text = "\n".join(cleaned_lines) if cleaned_lines else raw_log[:2000]

        result = ParsedLog(
            raw_log_text=raw_log,
            cleaned_log_text=cleaned_text,
            extracted_errors=list(set(extracted_errors)),
            stack_traces=stack_traces,
            exception_names=list(set(exception_names)),
            failed_tests=failed_tests,
            timeout_indicators=timeout_indicators,
            dependency_errors=dependency_errors,
            infrastructure_errors=infrastructure_errors,
        )

        log.debug(
            "Log parsed",
            exceptions=len(exception_names),
            traces=len(stack_traces),
            failed_tests=len(failed_tests),
            has_timeout=timeout_indicators,
            dep_errors=len(dependency_errors),
            infra_errors=len(infrastructure_errors),
        )

        return result