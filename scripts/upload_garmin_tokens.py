"""ローカルPCでGarminトークンをリフレッシュしGCSにアップロードする。

クラウドIP（AWS/GCP等）からのOAuthトークン交換が429で拒否される問題の暫定対策。
住宅IPからトークンを更新し、Cloud Runがそれを利用することでexchangeを回避する。

使い方:
    make upload-garmin-tokens

必要な環境変数:
    GARMIN_EMAIL, GARMIN_PASSWORD, RUN_COACH_GCS_BUCKET
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
)  # type: ignore[import-untyped]
from google.cloud import storage  # type: ignore[import-untyped]

TOKENSTORE = str(Path.home() / ".garminconnect")
GCS_TOKEN_PREFIX = "garmin-tokens"
REQUIRED_ENV_VARS = ("GARMIN_EMAIL", "GARMIN_PASSWORD", "RUN_COACH_GCS_BUCKET")


def main() -> None:
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        print(f"エラー: 環境変数が未設定です: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    bucket = os.environ["RUN_COACH_GCS_BUCKET"]

    client = Garmin(
        email=os.environ["GARMIN_EMAIL"],
        password=os.environ["GARMIN_PASSWORD"],
    )

    # トークンでログイン → 失敗時はクレデンシャルでフォールバック
    try:
        client.login(tokenstore=TOKENSTORE)
    except (FileNotFoundError, GarminConnectAuthenticationError):
        print("トークンが無効または未保存のため、クレデンシャルでログインします")
        client.login()
    print("ログイン成功")

    # リフレッシュ済みトークンを保存
    client.garth.dump(TOKENSTORE)
    print(f"トークン保存完了: {TOKENSTORE}")

    # GCSにアップロード
    gcs_client = storage.Client()
    gcs_bucket = gcs_client.bucket(bucket)
    for path in Path(TOKENSTORE).rglob("*"):
        if path.is_dir():
            continue
        gcs_path = f"{GCS_TOKEN_PREFIX}/{path.relative_to(TOKENSTORE)}"
        gcs_bucket.blob(gcs_path).upload_from_filename(str(path))
        print(f"  アップロード: gs://{bucket}/{gcs_path}")
    print("GCSアップロード完了")


if __name__ == "__main__":
    main()
