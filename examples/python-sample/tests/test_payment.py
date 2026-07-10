import pytest
import time


def test_payment_timeout():
    """Intentionally times out to demonstrate timeout failure triage."""
    # Simulate a slow operation that exceeds timeout threshold
    time.sleep(12)
    assert True  # This will fail due to timeout
