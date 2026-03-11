"""Cloud Run 環境判定ヘルパー。"""

from __future__ import annotations

import os


def is_cloud_run() -> bool:
    """Cloud Run上で実行されているかを判定する。

    Cloud Runはコンテナ起動時に K_SERVICE 環境変数を自動設定する。
    """
    return "K_SERVICE" in os.environ
