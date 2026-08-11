import json
import logging
import sys
from contextlib import AbstractContextManager
from types import SimpleNamespace

from fastapi.testclient import TestClient

from flipradar.core import observability
from flipradar.core.logging import JsonFormatter, request_id_context
from flipradar.core.observability import capture_exception, sanitize_telemetry
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
        record.metric = {"name": "database.health.check", "value": 1}
        payload = json.loads(formatter.format(record))
    finally:
        request_id_context.reset(token)

    assert payload["environment"] == "staging"
    assert payload["release"] == "2026.08.11"
    assert payload["request_id"] == "request-123"
    assert payload["message"] == "request completed"
    assert payload["metric"]["name"] == "database.health.check"


def test_request_id_is_preserved_and_returned_by_the_api():
    app = create_app(Settings(app_release="2026.08.11"))

    with TestClient(app) as client:
        response = client.get(
            "/health/live", headers={"X-Request-ID": "request-123"}
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"


def test_frontend_errors_are_accepted_without_a_database_dependency():
    app = create_app(Settings())

    with TestClient(app) as client:
        response = client.post(
            "/client-errors",
            json={
                "name": "TypeError",
                "message": "Cannot read properties of undefined",
                "stack": "TypeError: Cannot read properties of undefined",
                "url": "https://app.flipradar.test/dashboard",
            },
        )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}


def test_exception_capture_redacts_context_before_reporting(monkeypatch):
    class Scope(AbstractContextManager):
        tags: dict[str, str] = {}
        contexts: dict[str, object] = {}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def set_tag(self, key: str, value: str) -> None:
            self.tags[key] = value

        def set_context(self, key: str, value: object) -> None:
            self.contexts[key] = value

    scope = Scope()
    captured: list[BaseException] = []
    fake_sentry = SimpleNamespace(
        push_scope=lambda: scope,
        capture_exception=lambda exc: captured.append(exc),
    )
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
    monkeypatch.setattr(observability, "_monitoring_enabled", True)

    error = RuntimeError("request failed")
    capture_exception(
        error,
        request_id="request-123",
        context={"email": "demo@flipradar.com", "password": "DemoPass1!"},
    )

    assert captured == [error]
    assert scope.tags["request_id"] == "request-123"
    assert scope.contexts["request"] == {
        "email": "[REDACTED]",
        "password": "[REDACTED]",
    }
    assert sanitize_telemetry("login demo@flipradar.com / DemoPass1!") == (
        "login [REDACTED_EMAIL] / [REDACTED_DEMO_CREDENTIAL]"
    )
