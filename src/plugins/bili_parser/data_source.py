import httpx

from .utils import bv2av
from .models import ShareClickResponse
from .consts import SHARE_CLICK_ENDPOINT


async def get_av_data(oid: str, is_bv: bool = False) -> ShareClickResponse:
    if is_bv:
        oid = str(bv2av(oid))

    data = {
        "build": 7620400,
        "buvid": "0",
        "oid": oid,
        "platform": "android",
        "share_channel": "QQ",
        "share_id": "main.ugc-video-detail.0.0.pv",
        "share_mode": "7",
    }

    async with httpx.AsyncClient(
        timeout=10,
        headers={
            "User-Agent": (
                "Mozilla/5.0 BiliDroid/7.62.0 (bbcallen@gmail.com) os/android model/ONE"
                " A2001 mobi_app/android build/7620400 channel/bilih5 innerVer/7620410"
                " osVer/9 network/2"
            )
        },
    ) as client:
        r = await client.post(SHARE_CLICK_ENDPOINT, data=data)
        data = ShareClickResponse.model_validate_json(r.json())

    return data
