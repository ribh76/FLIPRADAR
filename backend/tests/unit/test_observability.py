import json
import logging

from fastapi.testclient import TestClient

from flipradar.core.logging import JsonFormatter, request_id_context
from flipradar.core.settings import Settings
from flipradar.main import create_app


def test_structured_logs_include_runtime_and_request_context():
    formatter = JsonFormatter(environment="staging", release="2026.08.11")
    token = request_id_context.set("request-123")
    try:
        record = logging.LogRecord(
            name="flipradar.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="request completed",
            args=(),
            exc_info=None,
        )
        payload = json.loads(formatter.format(record))
    finally:
        request_id_context.reset(token)

    assert payload["environment"] == "staging"
    assert payload["release"] == "2026.08.11"
    assert payload["request_id"] == "request-123"
    assert payload["message"] == "request completed"


def test_request_id_is_preserved_and_returned_by_the_api():
    app = create_app(Settings(app_release="2026.08.11"))

    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"
