from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_index_returns_200():
    response = client.get("/")
    assert response.status_code == 200


def test_index_returns_json():
    response = client.get("/")
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert isinstance(data, dict)


def test_index_has_required_structure():
    response = client.get("/")
    data = response.json()
    assert "service" in data
    assert "system" in data
    assert "runtime" in data
    assert "request" in data
    assert "endpoints" in data


def test_index_service_fields():
    response = client.get("/")
    data = response.json()
    svc = data["service"]
    assert svc["name"] == "devops-info-service"
    assert svc["version"] == "1.0.0"
    assert "description" in svc
    assert svc["framework"] == "FastAPI"


def test_index_system_fields():
    response = client.get("/")
    data = response.json()
    sys_info = data["system"]
    assert "hostname" in sys_info
    assert "platform" in sys_info
    assert "platform_version" in sys_info
    assert "architecture" in sys_info
    assert "cpu_count" in sys_info
    assert isinstance(sys_info["cpu_count"], int)
    assert "python_version" in sys_info


def test_index_runtime_fields():
    response = client.get("/")
    data = response.json()
    rt = data["runtime"]
    assert "uptime_seconds" in rt
    assert "uptime_human" in rt
    assert "current_time" in rt
    assert rt["timezone"] == "UTC"
    assert isinstance(rt["uptime_seconds"], int)


def test_index_request_fields():
    response = client.get("/")
    data = response.json()
    req = data["request"]
    assert "client_ip" in req
    assert "user_agent" in req
    assert req["method"] == "GET"
    assert req["path"] == "/"


def test_index_endpoints_list():
    response = client.get("/")
    data = response.json()
    endpoints = data["endpoints"]
    assert isinstance(endpoints, list)
    paths = [e["path"] for e in endpoints]
    assert "/" in paths
    assert "/health" in paths


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_json():
    response = client.get("/health")
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert isinstance(data, dict)


def test_health_required_fields():
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], int)


def test_health_uptime_non_negative():
    response = client.get("/health")
    data = response.json()
    assert data["uptime_seconds"] >= 0


def test_nonexistent_path_returns_404():
    response = client.get("/nonexistent")
    assert response.status_code == 404


def test_nonexistent_returns_error_structure():
    response = client.get("/nonexistent")
    data = response.json()
    assert "detail" in data or "error" in data
