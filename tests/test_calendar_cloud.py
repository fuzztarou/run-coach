"""calendar.py の Cloud Run 対応テスト。"""

from unittest.mock import MagicMock, patch

from run_coach.calendar import set_calendar_id


def test_set_calendar_id():
    """set_calendar_id でカレンダーIDが変更されること。"""
    import run_coach.calendar as cal

    original = cal._calendar_id
    set_calendar_id("test@group.calendar.google.com")
    assert cal._calendar_id == "test@group.calendar.google.com"
    # 元に戻す
    set_calendar_id(original)


@patch("run_coach.calendar.build")
@patch("run_coach.calendar.is_cloud_run", return_value=True)
def test_get_calendar_service_cloud_run(mock_is_cloud, mock_build):
    """Cloud Run環境ではADC認証を使うこと。"""
    mock_creds = MagicMock()
    with patch(
        "google.auth.default", return_value=(mock_creds, "project-id")
    ) as mock_default:
        from run_coach.calendar import _get_calendar_service

        _get_calendar_service()

        mock_default.assert_called_once()
        mock_build.assert_called_once_with("calendar", "v3", credentials=mock_creds)


@patch("run_coach.calendar.build")
@patch("run_coach.calendar.is_cloud_run", return_value=False)
@patch("run_coach.calendar.TOKEN_PATH")
def test_get_calendar_service_local(mock_token_path, mock_is_cloud, mock_build):
    """ローカル環境ではOAuth認証を使うこと。"""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_token_path.exists.return_value = True

    with patch(
        "run_coach.calendar.Credentials.from_authorized_user_file",
        return_value=mock_creds,
    ):
        from run_coach.calendar import _get_calendar_service

        _get_calendar_service()

        mock_build.assert_called_once_with("calendar", "v3", credentials=mock_creds)
