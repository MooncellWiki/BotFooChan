"""存库的密钥用 WEBUI__SECRET_KEY 派生的密钥加密。

和管理后台的登录 cookie 共用一个主密钥，按用途派生出不同的子密钥。主密钥丢了，
库里加密的 API Key 就解不开，只能重新录入，所以要和 data/ 一起备份。
"""

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from nonebot import get_plugin_config
from pydantic import BaseModel, Field


class _WebUIConfig(BaseModel):
    secret_key: str | None = None


class _Config(BaseModel):
    webui: _WebUIConfig = Field(default_factory=_WebUIConfig)


def _derive(secret: str, purpose: str) -> bytes:
    return hmac.new(
        secret.encode(), f"botfoochan:{purpose}".encode(), hashlib.sha256
    ).digest()


_secret = get_plugin_config(_Config).webui.secret_key or None
_cipher = (
    Fernet(base64.urlsafe_b64encode(_derive(_secret, "settings"))) if _secret else None
)
_fingerprint_key = _derive(_secret, "fingerprint") if _secret else None


class DecryptError(Exception):
    """解不开：多半是 WEBUI__SECRET_KEY 换了"""


def available() -> bool:
    """配了主密钥，能加解密"""
    return _cipher is not None


def encrypt(text: str) -> str:
    if _cipher is None:
        raise RuntimeError("没配 WEBUI__SECRET_KEY，没法加密")
    return _cipher.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    if _cipher is None:
        raise RuntimeError("没配 WEBUI__SECRET_KEY，没法解密")
    try:
        return _cipher.decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise DecryptError("解不开库里的密钥，WEBUI__SECRET_KEY 是不是换了？") from e


def fingerprint(text: str) -> str:
    """密钥的指纹：接口里只给指纹，提交回来时据此认出「没改」的那个原值"""
    if _fingerprint_key is None:
        return ""
    return hmac.new(_fingerprint_key, text.encode(), hashlib.sha256).hexdigest()[:12]
