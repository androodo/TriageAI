"""Tests for the Log Parser service."""

from __future__ import annotations

import pytest

from app.services.log_parser import LogParser, ParsedLog


class TestLogParser:
    """Tests for LogParser.parse()"""

    def test_parses_empty_log(self) -> None:
        parser = LogParser()
        result = parser.parse("")
        assert isinstance(result, ParsedLog)
        assert result.cleaned_log_text == ""
        assert result.exception_names == []
        assert result.stack_traces == []

    def test_parses_python_stack_trace(self) -> None:
        raw = """\
FAILED tests/test_payment.py::test_payment_flow
Traceback (most recent call last):
  File "tests/test_payment.py", line 42, in test_payment_flow
    response = client.post("/checkout", json={"amount": 100})
  File "app/api.py", line 88, in post
    raise ValueError("Invalid payment amount")
ValueError: Invalid payment amount
"""
        parser = LogParser()
        result = parser.parse(raw)

        assert "ValueError" in result.exception_names
        assert result.timeout_indicators is False
        assert len(result.stack_traces) == 1
        assert "Invalid payment amount" in result.cleaned_log_text
        assert "test_payment.py::test_payment_flow" in result.failed_tests

    def test_parses_timeout_indicators(self) -> None:
        raw = """\
ERROR: test_api_timeout - Request timeout after 30s
httpx.ConnectTimeout: Connection timeout
Connection timeout after 30000ms
The operation exceeded its deadline
"""
        parser = LogParser()
        result = parser.parse(raw)

        assert result.timeout_indicators is True
        assert len(result.extracted_errors) > 0
        assert "timeout" in " ".join(result.extracted_errors).lower()

    def test_parses_dependency_errors(self) -> None:
        raw = """\
ERROR: Failed to install package
ModuleNotFoundError: No module named 'stripe'
pip install failed with exit code 1
ImportError: cannot import name 'PaymentClient' from 'stripe'
"""
        parser = LogParser()
        result = parser.parse(raw)

        assert len(result.dependency_errors) > 0
        assert any("ModuleNotFoundError" in err for err in result.dependency_errors)
        assert "ModuleNotFoundError" in result.exception_names

    def test_parses_infrastructure_errors(self) -> None:
        raw = """\
ERROR: Database connection failed
connection refused to postgres:5432
ERROR 503: Service Unavailable
Out of memory: killed process
docker: network error
"""
        parser = LogParser()
        result = parser.parse(raw)

        assert len(result.infrastructure_errors) > 0
        assert any("connection refused" in err.lower() for err in result.infrastructure_errors)

    def test_parses_multiple_failed_tests(self) -> None:
        raw = """\
FAILED tests/test_auth.py::test_login_expired_token
FAILED tests/test_auth.py::test_logout
FAILED tests/test_api.py::test_create_user_duplicate_email
"""
        parser = LogParser()
        result = parser.parse(raw)

        assert len(result.failed_tests) == 3
        assert "tests/test_auth.py::test_login_expired_token" in result.failed_tests

    def test_parses_flaky_test_indicators(self) -> None:
        raw = """\
FAILED tests/test_race.py::test_concurrent_access
Error: AssertionError: assert 1 == 2 (sometimes passes, sometimes fails)
Retried 3 times, finally passed
"""
        parser = LogParser()
        result = parser.parse(raw)

        assert "AssertionError" in result.exception_names

    def test_removes_noise_lines(self) -> None:
        raw = """\
Collecting 15 items
collected 15 items
passed with 1 warning
Requirement already satisfied: pytest
Coverage.py warning
"""
        parser = LogParser()
        result = parser.parse(raw)

        # Noise lines should be filtered out, leaving empty cleaned log
        assert "Collecting" not in result.cleaned_log_text

    def test_extracts_exception_messages(self) -> None:
        raw = """\
RuntimeError: Database connection pool exhausted
KeyError: 'user_123' not found in session
TypeError: expected str, got NoneType
"""
        parser = LogParser()
        result = parser.parse(raw)

        assert "RuntimeError" in result.exception_names
        assert "KeyError" in result.exception_names
        assert "TypeError" in result.exception_names
        assert "Database connection pool exhausted" in result.extracted_errors

    def test_handles_real_pytest_output(self) -> None:
        raw = """\
============================= test session starts ==============================
platform darwin -- Python 3.11.8, pytest-8.0.0
collected 5 items

tests/test_integration.py::test_api_health FAILED                       [20%]
tests/test_integration.py::test_user_auth FAILED                       [40%]

=========================== FAILURES =======================================
___________________________ test_api_health ________________________________

tests/test_integration.py:15: in test_api_health
    assert response.status_code == 200
E   AssertionError: assert 500 == 200
E   +  where {'data': 'service unavailable'} = <TestClient response>.json()

___________________________ test_user_auth ________________________________

tests/test_integration.py:33: in test_user_auth
    db.create_user(email)
E   psycopg2.OperationalError: connection refused

___________ 2 failed, 0 passed, 3 skipped in 45.23s (1.234s) ______________
"""
        parser = LogParser()
        result = parser.parse(raw)

        assert "AssertionError" in result.exception_names
        assert "OperationalError" in result.exception_names
        assert result.timeout_indicators is False
        assert len(result.failed_tests) >= 2
        assert "connection refused" in " ".join(result.infrastructure_errors).lower()