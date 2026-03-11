"""GCS操作ユーティリティ。Garminトークンとprofile.yamlの永続化に使用。"""

from __future__ import annotations

import logging
from pathlib import Path

from google.cloud import storage  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def download_file(bucket_name: str, gcs_path: str, local_path: str) -> None:
    """GCSから単一ファイルをダウンロードする。"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    if not blob.exists():
        logger.warning("GCSにファイルが存在しません: gs://%s/%s", bucket_name, gcs_path)
        return
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(local_path)
    logger.info(
        "GCSからダウンロード: gs://%s/%s -> %s", bucket_name, gcs_path, local_path
    )


def upload_file(bucket_name: str, local_path: str, gcs_path: str) -> None:
    """ローカルファイルをGCSにアップロードする。"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)
    logger.info(
        "GCSにアップロード: %s -> gs://%s/%s", local_path, bucket_name, gcs_path
    )


def download_directory(bucket_name: str, gcs_prefix: str, local_dir: str) -> None:
    """GCSプレフィックス配下のファイルをローカルディレクトリにダウンロードする。"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blobs = list(bucket.list_blobs(prefix=gcs_prefix))
    if not blobs:
        logger.warning(
            "GCSにファイルが存在しません: gs://%s/%s", bucket_name, gcs_prefix
        )
        return
    local_base = Path(local_dir)
    for blob in blobs:
        # プレフィックス末尾のスラッシュ除去して相対パスを算出
        relative = blob.name[len(gcs_prefix) :].lstrip("/")
        if not relative:
            continue
        dest = local_base / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(dest))
        logger.info(
            "GCSからダウンロード: gs://%s/%s -> %s", bucket_name, blob.name, dest
        )


def upload_directory(bucket_name: str, local_dir: str, gcs_prefix: str) -> None:
    """ローカルディレクトリ配下のファイルをGCSにアップロードする。"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    local_base = Path(local_dir)
    if not local_base.exists():
        logger.warning("ローカルディレクトリが存在しません: %s", local_dir)
        return
    for path in local_base.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(local_base)
        gcs_path = f"{gcs_prefix.rstrip('/')}/{relative}"
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(str(path))
        logger.info("GCSにアップロード: %s -> gs://%s/%s", path, bucket_name, gcs_path)
