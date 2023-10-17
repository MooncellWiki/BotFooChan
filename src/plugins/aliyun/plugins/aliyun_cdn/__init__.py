import httpx
from nonebot import on_command
from nonebot_plugin_saa import Text, MessageFactory

from src.plugins.aliyun import config
from src.plugins.aliyun.config import CDNDomain
from src.plugins.aliyun.utils import get_signed_params

http_code = on_command(
    "http_code",
    aliases={"404", "503"},
    block=True,
)


async def get_stats_by_domain(domain: CDNDomain):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{domain.api_url}",
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


@http_code.handle()
async def handle_received_message():
    for domain in config.cdn_domains:
        stats = await get_stats_by_domain(domain)
        usage_data = stats["RealTimeHttpCodeData"]["UsageData"]

        data_list = []
        for k in usage_data:
            proportion = k["Value"]["RealTimeCodeProportionData"]
            if len(proportion) != 0:
                data_list.append(proportion)

        msg = MessageFactory(
            [
                Text(f"{domain.group_alias}统计："),
                *[
                    Text(f"\n{k['Code']}   {k['Proportion']:.2f}%")
                    for k in data_list[-1]
                ],
            ]
        )

        await msg.send()
