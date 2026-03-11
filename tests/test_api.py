"""FastAPI エンドポイントのテスト。"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_health():
    """GET /health が 200 と {"ok": true} を返す。"""
    with patch("run_coach.api.check_connection"):
        from run_coach.api import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
