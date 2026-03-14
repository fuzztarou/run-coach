"""OIDCトークン検証。Cloud Scheduler等の内部呼び出しを認証する。"""

from __future__ import annotations

import logging
import os

from fastapi import HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from run_coach.cloud import is_cloud_run

logger = logging.getLogger(__name__)


def require_oidc(request: Request) -> None:
    """OIDCトークンを検証するFastAPI dependency。

    Cloud Run外（ローカル）では検証をスキップする。
    """
    if not is_cloud_run():
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = auth_header.removeprefix("Bearer ")
    try:
        claims = id_token.verify_oauth2_token(token, google_requests.Request())
    except ValueError:
        logger.warning("OIDC token verification failed")
        raise HTTPException(status_code=401, detail="Invalid token")

    allowed_sa = os.environ.get("RUN_COACH_ALLOWED_SA", "")
    if not allowed_sa:
        logger.error("RUN_COACH_ALLOWED_SA is not set")
        raise HTTPException(status_code=403, detail="Forbidden")
    if claims.get("email") not in allowed_sa.split(","):
        logger.warning("Unauthorized service account: %s", claims.get("email"))
        raise HTTPException(status_code=403, detail="Forbidden")
