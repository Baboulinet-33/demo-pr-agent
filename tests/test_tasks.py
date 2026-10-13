from fastapi.testclient import TestClient


def _create_task(client: TestClient, headers: dict, **overrides) -> dict:
    payload = {"title": "Write the report", **overrides}
    response = client.post("/tasks", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_task_returns_task(client: TestClient, auth_headers: dict) -> None:
    task = _create_task(client, auth_headers, description="Draft the quarterly report")
    assert task["id"] == 1
    assert task["status"] == "todo"
    assert task["priority"] == "medium"
    assert task["owner"] == "alice@example.com"


def test_list_tasks_returns_own_tasks(client: TestClient, auth_headers: dict) -> None:
    _create_task(client, auth_headers, title="First")
    _create_task(client, auth_headers, title="Second")
    response = client.get("/tasks", headers=auth_headers)
    assert response.status_code == 200
    assert [task["title"] for task in response.json()] == ["First", "Second"]


def test_get_task_returns_task(client: TestClient, auth_headers: dict) -> None:
    created = _create_task(client, auth_headers)
    response = client.get(f"/tasks/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Write the report"


def test_get_missing_task_returns_not_found(client: TestClient, auth_headers: dict) -> None:
    response = client.get("/tasks/9999", headers=auth_headers)
    assert response.status_code == 404


def test_update_task_changes_fields(client: TestClient, auth_headers: dict) -> None:
    created = _create_task(client, auth_headers)
    response = client.patch(
        f"/tasks/{created['id']}",
        json={"status": "done", "priority": "high"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["priority"] == "high"
    assert body["title"] == "Write the report"


def test_delete_task_removes_it(client: TestClient, auth_headers: dict) -> None:
    created = _create_task(client, auth_headers)
    delete_response = client.delete(f"/tasks/{created['id']}", headers=auth_headers)
    assert delete_response.status_code == 204
    get_response = client.get(f"/tasks/{created['id']}", headers=auth_headers)
    assert get_response.status_code == 404


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stats_counts_tasks_by_status(client: TestClient, auth_headers: dict) -> None:
    _create_task(client, auth_headers, title="First")
    _create_task(client, auth_headers, title="Second", status="done")
    response = client.get("/tasks/stats", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["by_status"] == {"todo": 1, "doing": 0, "done": 1}
    assert body["completion_rate"] == 0.5
