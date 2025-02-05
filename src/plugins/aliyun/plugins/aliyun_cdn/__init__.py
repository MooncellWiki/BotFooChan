import asyncio
from io import BytesIO
from typing import Any

import httpx
import matplotlib.pyplot as plt
from nonebot import logger, on_command
from nonebot.adapters import Bot
from nonebot.plugin import PluginMetadata
from nonebot.utils import run_sync
from nonebot_plugin_alconna import Image, Text, UniMessage, on_alconna
from nonebot_plugin_filehost import FileHost
import numpy as np

from src.plugins.aliyun import config
from src.plugins.aliyun.config import CDNDomain
from src.plugins.aliyun.utils import get_signed_params

__plugin_meta__ = PluginMetadata(
    "阿里云 CDN 查询",
    "快速查看阿里云 CDN 侧统计回源实时带宽及 HTTP 状态码",
    "/http_code, /404, /503: 查询 HTTP 状态码\n"
    "/src_bandwidth, /带宽, /回源, /dk: 查询回源带宽",
)

http_code = on_command(
    "http_code",
    aliases={"404", "503"},
    block=True,
)

src_bandwidth = on_alconna(
    "src_bandwidth",
    aliases={"带宽", "回源", "dk"},
    use_cmd_start=True,
    use_cmd_sep=True,
    block=True,
)


async def get_src_bandwidth_stats(domain: CDNDomain):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            httpx.URL(str(domain.api_url)),
            params=get_signed_params(
                domain.access_key_id,
                domain.access_key_secret,
                "GET",
                {
                    "Action": "DescribeDomainRealTimeSrcBpsData",
                    "Version": "2018-05-10",
                    "DomainName": ",".join(domain.domains),
                },
            ),
        )

        return r.json()


@run_sync
def generate_src_image(data: dict[str, Any]):
    values = [
        d["Value"] / 1000000
        for d in data["RealTimeSrcBpsDataPerInterval"]["DataModule"]
    ]
    timestamps = np.arange(len(values))

    plt.figure(figsize=(15, 10))
    plt.plot(timestamps, values)
    plt.xlabel("Timestamp (minutes)")
    plt.ylabel("Value (Mbps)")
    plt.title(f"RealTime Source Bps Data Per Minute ({data['DomainName']})")

    buffer = BytesIO()
    plt.savefig(buffer, bbox_inches="tight", dpi=150)
    buffer.seek(0)

    return buffer


async def resolve_src_bandwidth(domain: CDNDomain, bot: Bot):
    stats = await get_src_bandwidth_stats(domain)

    data = stats["RealTimeSrcBpsDataPerInterval"]["DataModule"]
    data_list = []
    for k in data:
        value = k["Value"]
        if value != 0:
            data_list.append(k)

    value = data_list[-1]["Value"] / 1000000

    file_bytes = await generate_src_image(stats)
    file_url: str | None = None
    if bot.adapter.get_name() == "QQ":
        file_url = await FileHost(file_bytes).to_url()

    try:
        await src_bandwidth.send(
            UniMessage(
                [
                    Text(
                        f"{domain.group_alias}统计：\n当前CDN回源带宽数据为：{value:.2f}Mbps"
                    ),
                    Image(url=file_url, raw=file_bytes),
                ]
            )
        )

    except Exception as e:
        logger.opt(colors=True, exception=e).error("Failed to send message")
        await src_bandwidth.send(f"进行平台侧调用时出现错误：{e}")


async def get_http_code_stats(domain: CDNDomain):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            httpx.URL(str(domain.api_url)),
            params=get_signed_params(
                domain.access_key_id,
                domain.access_key_secret,
                "GET",
                {
                    "Action": "DescribeDomainRealTimeHttpCodeData",
                    "Version": "2018-05-10",
                    "DomainName": ",".join(domain.domains),
                },
            ),
        )

        return r.json()


async def resolve_http_code(domain: CDNDomain):
    stats = await get_http_code_stats(domain)
    usage_data = stats["RealTimeHttpCodeData"]["UsageData"]

    data_list = []
    for k in usage_data:
        proportion = k["Value"]["RealTimeCodeProportionData"]
        if len(proportion) != 0:
            data_list.append(proportion)

    await http_code.send(
        f"{domain.group_alias}统计：\n"
        + "\n".join([f"{k['Code']}   {k['Proportion']:.2f}%" for k in data_list[-1]])
    )


@http_code.handle()
async def handle_http_code():
    await asyncio.gather(*[resolve_http_code(domain) for domain in config.cdn_domains])


@src_bandwidth.handle()
async def handle_src_bandwidth(bot: Bot):
    await asyncio.gather(
        *[resolve_src_bandwidth(domain, bot) for domain in config.cdn_domains]
    )
