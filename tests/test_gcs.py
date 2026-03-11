"""gcs.py のモックテスト。"""

from pathlib import Path
from unittest.mock import MagicMock, patch


@patch("run_coach.gcs.storage")
def test_download_file(mock_storage, tmp_path):
    """GCSから単一ファイルをダウンロードできること。"""
    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage.Client.return_value = mock_client

    dest = str(tmp_path / "subdir" / "file.yaml")

    from run_coach.gcs import download_file

    download_file("my-bucket", "config/profile.yaml", dest)

    mock_client.bucket.assert_called_once_with("my-bucket")
    mock_bucket.blob.assert_called_once_with("config/profile.yaml")
    mock_blob.download_to_filename.assert_called_once_with(dest)
    assert Path(dest).parent.exists()


@patch("run_coach.gcs.storage")
def test_download_file_not_exists(mock_storage, tmp_path):
    """GCSにファイルが存在しない場合、ダウンロードしないこと。"""
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage.Client.return_value = mock_client

    from run_coach.gcs import download_file

    download_file("my-bucket", "missing.yaml", str(tmp_path / "out.yaml"))

    mock_blob.download_to_filename.assert_not_called()


@patch("run_coach.gcs.storage")
def test_upload_file(mock_storage, tmp_path):
    """ローカルファイルをGCSにアップロードできること。"""
    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage.Client.return_value = mock_client

    src = tmp_path / "test.yaml"
    src.write_text("key: value")

    from run_coach.gcs import upload_file

    upload_file("my-bucket", str(src), "config/test.yaml")

    mock_bucket.blob.assert_called_once_with("config/test.yaml")
    mock_blob.upload_from_filename.assert_called_once_with(str(src))


@patch("run_coach.gcs.storage")
def test_download_directory(mock_storage, tmp_path):
    """GCSプレフィックス配下のファイルをダウンロードできること。"""
    blob1 = MagicMock()
    blob1.name = "garmin-tokens/oauth1_token.json"
    blob2 = MagicMock()
    blob2.name = "garmin-tokens/oauth2_token.json"
    mock_bucket = MagicMock()
    mock_bucket.list_blobs.return_value = [blob1, blob2]
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage.Client.return_value = mock_client

    dest = str(tmp_path / "tokens")

    from run_coach.gcs import download_directory

    download_directory("my-bucket", "garmin-tokens", dest)

    assert blob1.download_to_filename.call_count == 1
    assert blob2.download_to_filename.call_count == 1


@patch("run_coach.gcs.storage")
def test_upload_directory(mock_storage, tmp_path):
    """ローカルディレクトリ配下のファイルをGCSにアップロードできること。"""
    (tmp_path / "a.json").write_text("{}")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.json").write_text("{}")

    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage.Client.return_value = mock_client

    from run_coach.gcs import upload_directory

    upload_directory("my-bucket", str(tmp_path), "prefix")

    assert mock_blob.upload_from_filename.call_count == 2
