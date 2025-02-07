import base64
from datetime import UTC, datetime
import hashlib
import hmac
import time
from typing import Any
from urllib.parse import quote

import httpx


def encode_uri_component(uri: str):
    return quote(uri, safe="()*!'")


def get_signature(access_key_secret: str, raw: bytes) -> str:
    key = bytes(f"{access_key_secret}&", "utf-8")

    hashed = hmac.new(key, raw, digestmod=hashlib.sha1)

    return base64.b64encode(hashed.digest()).decode()


def get_default_params(access_key_id: str) -> dict[str, str]:
    return {
        "AccessKeyId": access_key_id,
        "SignatureNonce": str(int(time.time() * 1000)),
        "Timestamp": f"{datetime.now(UTC).replace(microsecond=0).isoformat()}Z",
        "SignatureMethod": "HMAC-SHA1",
        "Format": "JSON",
        "SignatureVersion": "1.0",
    }


def get_signed_params(
    access_key_id: str, access_key_secret: str, method: str, params: dict[str, Any]
) -> dict[str, Any]:
    all_params = {**params, **get_default_params(access_key_id)}

    sorted_params = dict(sorted(all_params.items()))
    query_string = httpx.QueryParams(sorted_params)

    sign_raw = bytes(
        f"{method}&{encode_uri_component('/')}&{encode_uri_component(str(query_string))}",
        "utf-8",
    )

    return {
        "Signature": get_signature(access_key_secret, sign_raw),
        **all_params,
    }
