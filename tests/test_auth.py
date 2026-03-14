"""OIDCトークン検証のテスト。"""

from unittest.mock import patch

from fastapi.testclient import TestClient


@patch("run_coach.api.check_connection")
def test_oidc_skip_when_not_cloud_run(_mock_conn):
    """ローカル環境ではOIDC検証をスキップし、エンドポイントにアクセスできる。"""
    with (
        patch("run_coach.auth.is_cloud_run", return_value=False),
        patch("run_coach.api.check_and_prompt_new_activity", return_value=0),
    ):
        from run_coach.api import app

        client = TestClient(app)
        response = client.post("/internal/check-new-activity")

    assert response.status_code == 200


@patch("run_coach.api.prefetch_tokens")
@patch("run_coach.api.ensure_profile")
@patch("run_coach.api._validate_env")
@patch("run_coach.api.check_connection")
def test_oidc_missing_bearer_token(
    _mock_conn, _mock_validate, _mock_profile, _mock_tokens, monkeypatch
):
    """Cloud RunでAuthorizationヘッダーがない場合は401。"""
    monkeypatch.setenv("K_SERVICE", "run-coach")
    monkeypatch.setenv("RUN_COACH_ALLOWED_SA", "any@project.iam.gserviceaccount.com")

    from run_coach.api import app

    client = TestClient(app)
    response = client.post("/internal/check-new-activity")

    assert response.status_code == 401


@patch("run_coach.api.prefetch_tokens")
@patch("run_coach.api.ensure_profile")
@patch("run_coach.api._validate_env")
@patch("run_coach.api.check_connection")
def test_oidc_invalid_token(
    _mock_conn, _mock_validate, _mock_profile, _mock_tokens, monkeypatch
):
    """Cloud Runで不正なトークンの場合は401。"""
    monkeypatch.setenv("K_SERVICE", "run-coach")
    monkeypatch.setenv("RUN_COACH_ALLOWED_SA", "any@project.iam.gserviceaccount.com")

    with patch("run_coach.auth.id_token.verify_oauth2_token", side_effect=ValueError):
        from run_coach.api import app

        client = TestClient(app)
        response = client.post(
            "/internal/check-new-activity",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401


@patch("run_coach.api.prefetch_tokens")
@patch("run_coach.api.ensure_profile")
@patch("run_coach.api._validate_env")
@patch("run_coach.api.check_connection")
def test_oidc_unauthorized_service_account(
    _mock_conn, _mock_validate, _mock_profile, _mock_tokens, monkeypatch
):
    """Cloud Runで許可されていないSAの場合は403。"""
    monkeypatch.setenv("K_SERVICE", "run-coach")
    monkeypatch.setenv(
        "RUN_COACH_ALLOWED_SA", "good-sa@project.iam.gserviceaccount.com"
    )

    claims = {"email": "bad-sa@project.iam.gserviceaccount.com"}

    with patch("run_coach.auth.id_token.verify_oauth2_token", return_value=claims):
        from run_coach.api import app

        client = TestClient(app)
        response = client.post(
            "/internal/check-new-activity",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 403


@patch("run_coach.api.prefetch_tokens")
@patch("run_coach.api.ensure_profile")
@patch("run_coach.api._validate_env")
@patch("run_coach.api.check_connection")
def test_oidc_valid_token(
    _mock_conn, _mock_validate, _mock_profile, _mock_tokens, monkeypatch
):
    """Cloud Runで正しいトークンとSAの場合は通過する。"""
    monkeypatch.setenv("K_SERVICE", "run-coach")
    monkeypatch.setenv(
        "RUN_COACH_ALLOWED_SA", "scheduler@project.iam.gserviceaccount.com"
    )

    claims = {"email": "scheduler@project.iam.gserviceaccount.com"}

    with (
        patch("run_coach.auth.id_token.verify_oauth2_token", return_value=claims),
        patch("run_coach.api.check_and_prompt_new_activity", return_value=0),
    ):
        from run_coach.api import app

        client = TestClient(app)
        response = client.post(
            "/internal/check-new-activity",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"prompted": 0}


@patch("run_coach.api.prefetch_tokens")
@patch("run_coach.api.ensure_profile")
@patch("run_coach.api._validate_env")
@patch("run_coach.api.check_connection")
def test_oidc_multiple_allowed_sa(
    _mock_conn, _mock_validate, _mock_profile, _mock_tokens, monkeypatch
):
    """複数の許可SA指定でマッチする場合は通過する。"""
    monkeypatch.setenv("K_SERVICE", "run-coach")
    monkeypatch.setenv(
        "RUN_COACH_ALLOWED_SA",
        "first@project.iam.gserviceaccount.com,second@project.iam.gserviceaccount.com",
    )

    claims = {"email": "second@project.iam.gserviceaccount.com"}

    with (
        patch("run_coach.auth.id_token.verify_oauth2_token", return_value=claims),
        patch("run_coach.api.check_and_prompt_new_activity", return_value=0),
    ):
        from run_coach.api import app

        client = TestClient(app)
        response = client.post(
            "/internal/check-new-activity",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200


def test_startup_fails_without_required_env(monkeypatch):
    """Cloud Runで必須環境変数が未設定だと起動時にエラー。"""
    monkeypatch.setenv("K_SERVICE", "run-coach")
    monkeypatch.delenv("RUN_COACH_ALLOWED_SA", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import pytest

    from run_coach.api import _validate_env

    with pytest.raises(RuntimeError, match="Missing required env vars"):
        _validate_env()


@patch("run_coach.api.check_connection")
def test_health_no_oidc_required(_mock_conn):
    """/health はOIDC認証不要。"""
    from run_coach.api import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
