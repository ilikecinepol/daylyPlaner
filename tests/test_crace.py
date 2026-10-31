from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def register(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"{uuid4()}@example.com", "password": "StrongPass123", "name": "Athlete"},
    )
    assert response.status_code == 201
    assert client.post("/api/v1/modules/crace/unlock", json={"code": "test-module-code"}).status_code == 200


def test_crace_state_is_private_and_has_baseline():
    with TestClient(app) as client:
        assert client.get("/api/v1/crace").status_code == 401
        register(client)
        state = client.get("/api/v1/crace").json()
        assert state["profile"]["race_date"] == "2026-12-05"
        assert state["completed_sessions"]["baseline"] is True


def test_profile_session_and_workout_round_trip():
    with TestClient(app) as client:
        register(client)
        profile = client.put("/api/v1/crace/profile", json={"weight_kg": "80.5", "max_hr": 194})
        assert profile.status_code == 200
        assert float(profile.json()["weight_kg"]) == 80.5
        assert client.put("/api/v1/crace/sessions/w02", json={"completed": True}).status_code == 200
        workout = client.post(
            "/api/v1/crace/workouts",
            json={
                "plan_key": "w02", "title": "Лёгкий бег", "duration_sec": 120,
                "rpe": 4,
                "samples": [
                    {"t": 0, "hr": 120, "phase": "run"},
                    {"t": 60, "hr": 160, "phase": "run"},
                ],
                "laps": [{"name": "Разминка", "seconds": 120}],
            },
        )
        assert workout.status_code == 201
        assert workout.json()["avg_hr"] == 140
        state = client.get("/api/v1/crace").json()
        assert state["completed_sessions"]["w02"] is True
        assert state["workouts"][0]["max_hr"] == 160


def test_workouts_are_isolated_between_users():
    with TestClient(app) as first, TestClient(app) as second:
        register(first)
        register(second)
        workout = first.post("/api/v1/crace/workouts", json={"title": "Private", "duration_sec": 1}).json()
        assert second.delete(f"/api/v1/crace/workouts/{workout['id']}").status_code == 404
        assert second.get("/api/v1/crace").json()["workouts"] == []


def test_crace_validation_limits_sensor_payload():
    with TestClient(app) as client:
        register(client)
        assert client.put("/api/v1/crace/profile", json={"weight_kg": 20, "max_hr": 190}).status_code == 422
        assert client.post("/api/v1/crace/workouts", json={"title": "Bad", "duration_sec": 1, "samples": [{"t": 0, "hr": 999}]}).status_code == 422
