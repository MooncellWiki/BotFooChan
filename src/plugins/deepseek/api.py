"""DeepSeek 平台接口（余额查询等非模型推理调用）"""

from dataclasses import dataclass
from typing import Literal

import httpx

from .config import ds_config


class RequestException(Exception):
    """请求错误"""


@dataclass
class BalanceInfo:
    currency: Literal["CNY", "USD"]
    """货币，人民币或美元"""
    total_balance: str
    """总的可用余额，包括赠金和充值余额"""
    granted_balance: str
    """未过期的赠金余额"""
    topped_up_balance: str
    """充值余额"""


@dataclass
class Balance:
    """用户余额详情"""

    is_available: bool
    """当前账户是否有余额可供 API 调用"""
    balance_infos: list[BalanceInfo]

    def __post_init__(self) -> None:
        self.balance_infos = [
            BalanceInfo(**info) if isinstance(info, dict) else info
            for info in self.balance_infos
        ]


async def query_balance(model_name: str) -> Balance:
    model = ds_config.get_model_config(model_name)
    endpoint = model.to_endpoint()

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{endpoint.base_url}/user/balance",
            headers={"Authorization": f"Bearer {endpoint.api_key}"},
        )
    if response.status_code == 404:
        raise RequestException("本地模型不支持查询余额，请更换默认模型")
    if response.status_code != 200:
        raise RequestException(f"查询余额失败，状态码: {response.status_code}")
    return Balance(**response.json())
