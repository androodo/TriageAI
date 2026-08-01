# TriageAI - Sample Python Project

This is a demo project that intentionally includes failures to showcase TriageAI's CI failure triage capabilities.

## Tests

- ✅ `test_addition.py::test_add_positive` - should pass
- ✅ `test_subtraction.py::test_subtract_positive` - should pass
- ❌ `test_payment.py::test_payment_timeout` - intentionally times out (shows timeout triage)
- ❌ `test_database.py::test_connection_refused` - intentionally fails (shows infrastructure triage)
- ❌ `test_api.py::test_api_mock_failure` - assertion error (shows test assertion bug)

## Running Tests

```bash
pytest -v
```

## Local Development

```bash
# Setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run tests
pytest
```
