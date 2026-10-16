import hmac

from fastapi import HTTPException

from .config import APP_TOKEN


def require_admin(token: str | None) -> None:
    if not APP_TOKEN:
        raise HTTPException(status_code=503, detail="管理端尚未配置认证令牌")
    if not token or not hmac.compare_digest(token, APP_TOKEN):
        raise HTTPException(status_code=401, detail="需要有效的管理令牌")


def validate_admin_configuration() -> None:
    if len(APP_TOKEN) < 32 or APP_TOKEN.lower().startswith("replace-with-"):
        raise RuntimeError("APP_TOKEN must be a unique random value with at least 32 characters")
