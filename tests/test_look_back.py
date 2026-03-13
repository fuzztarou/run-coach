"""振り返りロジック + Garmin書き戻しのテスト。"""

from unittest.mock import MagicMock, patch

from run_coach.look_back import _build_look_back_description


# --- _build_look_back_description ---


def test_build_look_back_description_all_fields():
    """全フィールド指定時の description テキスト。"""
    feedback = {"rpe": 7, "pain": "右ひざ", "comment": "調子良かった"}
    result = _build_look_back_description(feedback)
    assert result == "RPE: 7\n痛み: 右ひざ\nコメント: 調子良かった"


def test_build_look_back_description_rpe_only():
    """RPEのみの場合。"""
    feedback = {"rpe": 5, "pain": None, "comment": None}
    result = _build_look_back_description(feedback)
    assert result == "RPE: 5"


def test_build_look_back_description_comment_only():
    """コメントのみの場合。"""
    feedback = {"rpe": None, "pain": None, "comment": "気持ちよく走れた"}
    result = _build_look_back_description(feedback)
    assert result == "コメント: 気持ちよく走れた"


def test_build_look_back_description_empty():
    """全フィールド空の場合は空文字列。"""
    feedback = {"rpe": None, "pain": None, "comment": None}
    result = _build_look_back_description(feedback)
    assert result == ""


# --- write_description_to_garmin ---


def test_write_description_to_garmin():
    """garth.connectapi が正しいエンドポイント・ペイロードで呼ばれること。"""
    mock_garth = MagicMock()
    mock_client = MagicMock()
    mock_client.garth = mock_garth

    with patch("run_coach.garmin._login", return_value=mock_client):
        from run_coach.garmin import write_description_to_garmin

        write_description_to_garmin("12345", "RPE: 7")

    mock_garth.connectapi.assert_called_once_with(
        "/activity-service/activity/12345",
        method="PUT",
        json={"activityId": "12345", "description": "RPE: 7"},
    )


# --- handle_look_back_reply with Garmin writeback ---


def _make_mock_engine():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    return mock_engine, mock_conn


def test_handle_look_back_reply_with_garmin_writeback():
    """DB保存 + Garmin PUT が呼ばれること。"""
    mock_workout = {
        "id": 42,
        "garmin_activity_id": "ACT001",
        "description": "",
    }
    mock_engine, mock_conn = _make_mock_engine()

    with (
        patch("run_coach.look_back.get_engine", return_value=mock_engine),
        patch(
            "run_coach.look_back.get_pending_look_back_workout",
            return_value=mock_workout,
        ),
        patch("run_coach.look_back.update_workout_look_back") as mock_update,
        patch("run_coach.look_back.send_reply") as mock_reply,
        patch("run_coach.look_back.write_description_to_garmin") as mock_write_garmin,
    ):
        from run_coach.look_back import handle_look_back_reply

        handle_look_back_reply("RPE: 7\nコメント: 快調", "reply-token")

    mock_update.assert_called_once_with(mock_conn, 42, rpe=7, pain=None, comment="快調")
    mock_write_garmin.assert_called_once_with("ACT001", "RPE: 7\nコメント: 快調")
    mock_reply.assert_called_once_with("reply-token", "記録しました ✅")


def test_handle_look_back_reply_garmin_failure():
    """Garmin書き戻し失敗時もLINE返信は成功すること。"""
    mock_workout = {
        "id": 42,
        "garmin_activity_id": "ACT001",
        "description": "",
    }
    mock_engine, mock_conn = _make_mock_engine()

    with (
        patch("run_coach.look_back.get_engine", return_value=mock_engine),
        patch(
            "run_coach.look_back.get_pending_look_back_workout",
            return_value=mock_workout,
        ),
        patch("run_coach.look_back.update_workout_look_back"),
        patch("run_coach.look_back.send_reply") as mock_reply,
        patch(
            "run_coach.look_back.write_description_to_garmin",
            side_effect=Exception("API error"),
        ),
    ):
        from run_coach.look_back import handle_look_back_reply

        handle_look_back_reply("RPE: 5", "reply-token")

    mock_reply.assert_called_once_with("reply-token", "記録しました ✅")


def test_handle_look_back_reply_existing_description():
    """既存 description がある場合に書き戻しスキップされること。"""
    mock_workout = {
        "id": 42,
        "garmin_activity_id": "ACT001",
        "description": "既にメモあり",
    }
    mock_engine, mock_conn = _make_mock_engine()

    with (
        patch("run_coach.look_back.get_engine", return_value=mock_engine),
        patch(
            "run_coach.look_back.get_pending_look_back_workout",
            return_value=mock_workout,
        ),
        patch("run_coach.look_back.update_workout_look_back"),
        patch("run_coach.look_back.send_reply"),
        patch("run_coach.look_back.write_description_to_garmin") as mock_write_garmin,
    ):
        from run_coach.look_back import handle_look_back_reply

        handle_look_back_reply("RPE: 5", "reply-token")

    mock_write_garmin.assert_not_called()


def test_handle_look_back_reply_no_garmin_id():
    """garmin_activity_id が None の場合スキップ。"""
    mock_workout = {
        "id": 42,
        "garmin_activity_id": None,
        "description": "",
    }
    mock_engine, mock_conn = _make_mock_engine()

    with (
        patch("run_coach.look_back.get_engine", return_value=mock_engine),
        patch(
            "run_coach.look_back.get_pending_look_back_workout",
            return_value=mock_workout,
        ),
        patch("run_coach.look_back.update_workout_look_back"),
        patch("run_coach.look_back.send_reply"),
        patch("run_coach.look_back.write_description_to_garmin") as mock_write_garmin,
    ):
        from run_coach.look_back import handle_look_back_reply

        handle_look_back_reply("RPE: 5", "reply-token")

    mock_write_garmin.assert_not_called()
