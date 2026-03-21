from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
from garminconnect import GarminConnectAuthenticationError  # type: ignore[import-untyped]

from scripts.upload_garmin_tokens import main


def test_missing_env_vars_exits(monkeypatch):
    """必須環境変数が未設定の場合、エラー終了する。"""
    monkeypatch.delenv("GARMIN_EMAIL", raising=False)
    monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
    monkeypatch.delenv("RUN_COACH_GCS_BUCKET", raising=False)

    with pytest.raises(SystemExit, match="1"):
        main()


def test_partial_env_vars_exits(monkeypatch):
    """一部の環境変数のみ設定されている場合もエラー終了する。"""
    monkeypatch.setenv("GARMIN_EMAIL", "test@example.com")
    monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
    monkeypatch.delenv("RUN_COACH_GCS_BUCKET", raising=False)

    with pytest.raises(SystemExit, match="1"):
        main()


@patch("scripts.upload_garmin_tokens.storage")
@patch("scripts.upload_garmin_tokens.Garmin")
def test_token_login_success(mock_garmin_cls, mock_storage, monkeypatch, tmp_path):
    """正常系: トークンログインが成功し、GCSにアップロードされる。"""
    monkeypatch.setenv("GARMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "secret")
    monkeypatch.setenv("RUN_COACH_GCS_BUCKET", "my-bucket")

    mock_client = MagicMock()
    mock_garmin_cls.return_value = mock_client

    # garth.dump がトークンファイルを作成するのをシミュレート
    token_dir = tmp_path / ".garminconnect"
    token_dir.mkdir()
    (token_dir / "oauth1_token.json").write_text("{}")
    (token_dir / "oauth2_token.json").write_text("{}")
    monkeypatch.setattr("scripts.upload_garmin_tokens.TOKENSTORE", str(token_dir))

    main()

    mock_client.login.assert_called_once_with(tokenstore=str(token_dir))
    mock_client.garth.dump.assert_called_once_with(str(token_dir))
    mock_storage.Client.assert_called_once()
    mock_bucket = mock_storage.Client().bucket("my-bucket")
    assert mock_bucket.blob.call_count >= 1


@patch("scripts.upload_garmin_tokens.storage")
@patch("scripts.upload_garmin_tokens.Garmin")
def test_fallback_to_credential_login(
    mock_garmin_cls, mock_storage, monkeypatch, tmp_path
):
    """トークンログイン失敗時にクレデンシャルログインへフォールバックする。"""
    monkeypatch.setenv("GARMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "secret")
    monkeypatch.setenv("RUN_COACH_GCS_BUCKET", "my-bucket")

    mock_client = MagicMock()
    mock_garmin_cls.return_value = mock_client
    mock_client.login.side_effect = [
        GarminConnectAuthenticationError("token expired"),
        None,
    ]

    token_dir = tmp_path / ".garminconnect"
    token_dir.mkdir()
    (token_dir / "oauth1_token.json").write_text("{}")
    monkeypatch.setattr("scripts.upload_garmin_tokens.TOKENSTORE", str(token_dir))

    main()

    assert mock_client.login.call_count == 2
    mock_client.login.assert_has_calls([call(tokenstore=str(token_dir)), call()])
    mock_client.garth.dump.assert_called_once_with(str(token_dir))


@patch("scripts.upload_garmin_tokens.storage")
@patch("scripts.upload_garmin_tokens.Garmin")
def test_fallback_on_missing_tokenstore(
    mock_garmin_cls, mock_storage, monkeypatch, tmp_path
):
    """トークンファイルが存在しない場合もクレデンシャルでログインする。"""
    monkeypatch.setenv("GARMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "secret")
    monkeypatch.setenv("RUN_COACH_GCS_BUCKET", "my-bucket")

    mock_client = MagicMock()
    mock_garmin_cls.return_value = mock_client
    mock_client.login.side_effect = [FileNotFoundError("no tokens"), None]

    token_dir = tmp_path / ".garminconnect"
    token_dir.mkdir()
    (token_dir / "oauth1_token.json").write_text("{}")
    monkeypatch.setattr("scripts.upload_garmin_tokens.TOKENSTORE", str(token_dir))

    main()

    assert mock_client.login.call_count == 2
    mock_client.login.assert_has_calls([call(tokenstore=str(token_dir)), call()])
