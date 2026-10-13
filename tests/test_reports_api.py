import json

from fastapi.testclient import TestClient

from app.security import create_report_token


def _create_task(client: TestClient, auth_headers: dict, **overrides) -> dict:
    payload = {"title": "Write the report", **overrides}
    response = client.post("/tasks", json=payload, headers=auth_headers)
    assert response.status_code == 201
    return response.json()


def test_report_summary_requires_auth(client: TestClient) -> None:
    response = client.get("/reports/summary")
    assert response.status_code == 401


def test_report_summary_totals(client: TestClient, auth_headers: dict) -> None:
    _create_task(client, auth_headers, title="Done one", status="done")
    _create_task(client, auth_headers, title="Open one")
    response = client.get("/reports/summary", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["window"] == "day"
    assert body["totals"]["total"] == 2
    assert body["totals"]["done"] == 1


def test_report_summary_respects_filter(client: TestClient, auth_headers: dict) -> None:
    _create_task(client, auth_headers, title="Completable", status="done")
    _create_task(client, auth_headers, title="Pending")
    response = client.get("/reports/summary", params={"filter": "status:done"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["totals"]["total"] == 1


def test_report_export_rejects_garbage_token(client: TestClient, auth_headers: dict) -> None:
    _create_task(client, auth_headers)
    response = client.get("/reports/export", params={"format": "csv", "token": "not-a-token"})
    assert response.status_code == 401


def test_report_export_csv_with_signed_token(client: TestClient, auth_headers: dict) -> None:
    _create_task(client, auth_headers, title="Plan the quarter")
    token = create_report_token("alice@example.com")
    response = client.get("/reports/export", params={"format": "csv", "token": token})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Plan the quarter" in response.text


def test_export_token_endpoint_roundtrip(client: TestClient, auth_headers: dict) -> None:
    _create_task(client, auth_headers, title="Token flow")
    issued = client.get("/reports/export-token", headers=auth_headers)
    assert issued.status_code == 200
    token = issued.json()["token"]

    export = client.get("/reports/export", params={"format": "json", "token": token})
    assert export.status_code == 200
    data = json.loads(export.text)
    assert data[0]["title"] == "Token flow"


def test_report_schedule_endpoint(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/reports/schedule",
        json={"interval_seconds": 60, "format": "json"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "scheduled"
    assert body["interval_seconds"] == 60


def test_report_metrics_endpoint(client: TestClient, auth_headers: dict) -> None:
    response = client.get("/reports/metrics", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["metrics"] == []