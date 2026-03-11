"""cloud.py のテスト。"""

import os
from unittest.mock import patch


def test_is_cloud_run_true():
    """K_SERVICE が設定されている場合 True を返す。"""
    with patch.dict(os.environ, {"K_SERVICE": "run-coach"}):
        from run_coach.cloud import is_cloud_run

        assert is_cloud_run() is True


def test_is_cloud_run_false():
    """K_SERVICE が未設定の場合 False を返す。"""
    env = os.environ.copy()
    env.pop("K_SERVICE", None)
    with patch.dict(os.environ, env, clear=True):
        from run_coach.cloud import is_cloud_run

        assert is_cloud_run() is False
