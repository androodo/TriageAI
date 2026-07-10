import pytest


def test_connection_refused():
    """Simulates a database connection failure to show infrastructure triage."""
    # In a real scenario, this would try to connect to a database
    # Here we simulate connection refused
    try:
        raise ConnectionError("Connection refused to postgres:5432")
    except ConnectionError as e:
        assert False, f"Database connection failed: {e}"
