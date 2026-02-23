"""Basic認証デコレータ"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING

import bcrypt
from flask import Response, request

if TYPE_CHECKING:
    from .config import WebConfig


def check_auth(username: str, password: str, config: WebConfig) -> bool:
    """ユーザー名とパスワードを検証"""
    if username != config.username:
        return False
    return bcrypt.checkpw(
        password.encode("utf-8"),
        config.password_hash.encode("utf-8"),
    )


def require_auth(config: WebConfig):
    """Basic認証を要求するデコレータ"""

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth or not check_auth(auth.username, auth.password, config):
                return Response(
                    "認証が必要です",
                    401,
                    {"WWW-Authenticate": 'Basic realm="MicroCam"'},
                )
            return f(*args, **kwargs)

        return decorated

    return decorator


def hash_password(password: str) -> str:
    """パスワードをbcryptでハッシュ化"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
