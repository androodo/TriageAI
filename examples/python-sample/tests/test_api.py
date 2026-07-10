def test_api_mock_failure():
    """Simulates an API assertion failure to show test assertion bug triage."""
    from unittest.mock import Mock
    import requests

    # Mock the requests.post call
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "failed",  # Expected "success"
        "message": "Payment processing error",
    }

    # Simulate checking the API response
    result = mock_response.status_code == 200
    assert result, "API endpoint should return 200"

    # This asserts on the response body - will fail
    assert mock_response.json()["status"] == "success", (
        f"Expected status 'success', got '{mock_response.json()['status']}'"
    )
