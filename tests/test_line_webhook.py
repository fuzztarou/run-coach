"""LINE Webhook関連のテスト。"""

from datetime import date
from unittest.mock import MagicMock, patch

from run_coach.line import (
    format_look_back_prompt,
    parse_look_back_message,
    verify_signature,
)


# --- verify_signature ---


def test_verify_signature_valid(monkeypatch):
    """正しい署名で True を返すこと。"""
    monkeypatch.setenv("RUN_COACH_LINE_CHANNEL_SECRET", "test-secret")

    import hashlib
    import hmac
    from base64 import b64encode

    body = b'{"events":[]}'
    digest = hmac.new(b"test-secret", body, hashlib.sha256).digest()
    signature = b64encode(digest).decode("utf-8")

    assert verify_signature(body, signature) is True


def test_verify_signature_invalid(monkeypatch):
    """不正な署名で False を返すこと。"""
    monkeypatch.setenv("RUN_COACH_LINE_CHANNEL_SECRET", "test-secret")
    assert verify_signature(b'{"events":[]}', "invalid-sig") is False


def test_verify_signature_no_secret(monkeypatch):
    """CHANNEL_SECRET 未設定で False を返すこと。"""
    monkeypatch.delenv("RUN_COACH_LINE_CHANNEL_SECRET", raising=False)
    assert verify_signature(b"test", "sig") is False


# --- parse_look_back_message ---


def test_parse_look_back_all_fields():
    """RPE・痛み・コメントが全てパースされること。"""
    text = "RPE: 7\n痛み: 右ひざ\nコメント: 調子良かった"
    result = parse_look_back_message(text)
    assert result["rpe"] == 7
    assert result["pain"] == "右ひざ"
    assert result["comment"] == "調子良かった"


def test_parse_look_back_rpe_only():
    """RPEのみの入力。"""
    text = "RPE: 5"
    result = parse_look_back_message(text)
    assert result["rpe"] == 5
    assert result["pain"] is None
    assert result["comment"] is None


def test_parse_look_back_free_text():
    """構造化されていないテキストはcommentとして扱われること。"""
    text = "今日は気持ちよく走れた"
    result = parse_look_back_message(text)
    assert result["rpe"] is None
    assert result["pain"] is None
    assert result["comment"] == "今日は気持ちよく走れた"


def test_parse_look_back_fullwidth_colon():
    """全角コロンでもパースできること。"""
    text = "RPE：8\n痛み：なし\nコメント：いい感じ"
    result = parse_look_back_message(text)
    assert result["rpe"] == 8
    assert result["pain"] == "なし"
    assert result["comment"] == "いい感じ"


# --- format_look_back_prompt ---


def test_format_look_back_prompt():
    """振り返りPromptメッセージが正しくフォーマットされること。"""
    workout = {
        "id": 1,
        "date": date(2026, 3, 12),
        "workout_type": "easy_run",
        "distance_km": 5.2,
        "duration_min": 30.25,
    }
    result = format_look_back_prompt(workout)
    assert "🏃 ランお疲れさまでした！" in result
    assert "3/12 イージーラン" in result
    assert "5.2km" in result
    assert "30:15" in result
    assert "RPE:" in result
    assert "痛み:" in result
    assert "コメント:" in result


def test_format_look_back_prompt_unknown_type():
    """未知のワークアウトタイプはそのまま表示されること。"""
    workout = {
        "id": 1,
        "date": date(2026, 3, 12),
        "workout_type": "trail_running",
        "distance_km": 10.0,
        "duration_min": 60.0,
    }
    result = format_look_back_prompt(workout)
    assert "trail_running" in result


# --- webhook endpoint ---


def test_webhook_line_invalid_signature(monkeypatch):
    """不正な署名で400を返すこと。"""
    monkeypatch.setenv("RUN_COACH_LINE_CHANNEL_SECRET", "test-secret")

    with patch("run_coach.api.check_connection"):
        from run_coach.api import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post(
            "/webhook/line",
            content=b'{"events":[]}',
            headers={"X-Line-Signature": "invalid"},
        )
    assert response.status_code == 400


def test_webhook_line_saves_look_back(monkeypatch):
    """正しい署名のテキストメッセージでDB更新されること。"""
    monkeypatch.setenv("RUN_COACH_LINE_CHANNEL_SECRET", "test-secret")
    monkeypatch.setenv("RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN", "test-token")

    import hashlib
    import hmac
    import json
    from base64 import b64encode

    payload = json.dumps(
        {
            "events": [
                {
                    "type": "message",
                    "replyToken": "test-reply-token",
                    "message": {
                        "type": "text",
                        "text": "RPE: 7\n痛み: なし\nコメント: 快調",
                    },
                }
            ]
        }
    ).encode()
    digest = hmac.new(b"test-secret", payload, hashlib.sha256).digest()
    signature = b64encode(digest).decode("utf-8")

    mock_workout = {
        "id": 42,
        "garmin_activity_id": "ACT001",
        "date": date(2026, 3, 12),
    }

    with (
        patch("run_coach.api.check_connection"),
        patch("run_coach.look_back.get_engine") as mock_engine,
        patch(
            "run_coach.look_back.get_pending_look_back_workout",
            return_value=mock_workout,
        ),
        patch("run_coach.look_back.update_workout_look_back") as mock_update,
        patch("run_coach.look_back.send_reply") as mock_reply,
    ):
        mock_conn = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
            return_value=mock_conn
        )
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(
            return_value=False
        )

        from run_coach.api import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post(
            "/webhook/line",
            content=payload,
            headers={"X-Line-Signature": signature},
        )

    assert response.status_code == 200
    mock_update.assert_called_once_with(
        mock_conn, 42, rpe=7, pain="なし", comment="快調"
    )
    mock_reply.assert_called_once_with("test-reply-token", "記録しました ✅")


def test_webhook_line_no_pending_workout(monkeypatch):
    """紐付け可能なワークアウトがない場合のメッセージ。"""
    monkeypatch.setenv("RUN_COACH_LINE_CHANNEL_SECRET", "test-secret")
    monkeypatch.setenv("RUN_COACH_LINE_CHANNEL_ACCESS_TOKEN", "test-token")

    import hashlib
    import hmac
    import json
    from base64 import b64encode

    payload = json.dumps(
        {
            "events": [
                {
                    "type": "message",
                    "replyToken": "test-reply-token",
                    "message": {"type": "text", "text": "RPE: 5"},
                }
            ]
        }
    ).encode()
    digest = hmac.new(b"test-secret", payload, hashlib.sha256).digest()
    signature = b64encode(digest).decode("utf-8")

    with (
        patch("run_coach.api.check_connection"),
        patch("run_coach.look_back.get_engine") as mock_engine,
        patch("run_coach.look_back.get_pending_look_back_workout", return_value=None),
        patch("run_coach.look_back.send_reply") as mock_reply,
    ):
        mock_conn = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
            return_value=mock_conn
        )
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(
            return_value=False
        )

        from run_coach.api import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post(
            "/webhook/line",
            content=payload,
            headers={"X-Line-Signature": signature},
        )

    assert response.status_code == 200
    mock_reply.assert_called_once_with(
        "test-reply-token", "紐付けるワークアウトが見つかりませんでした。"
    )
