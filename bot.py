import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, override

import nonebot
from nonebot import logger
from nonebot.adapters.feishu import Adapter as FeishuAdapter
from nonebot.adapters.github import Adapter as BaseGitHubAdapter
from nonebot.adapters.github.config import GitHubApp, OAuthApp
from nonebot.adapters.milky import Adapter as BaseMilkyAdapter
from nonebot.adapters.milky.config import ClientInfo as MilkyClientInfo
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter
from nonebot.adapters.qq import Adapter as QQAdapter
from nonebot.drivers import Driver, Request, WebSocket

GITHUB_RETRY_INTERVAL = 60


class GitHubAdapter(BaseGitHubAdapter):
    """启动时连不上 GitHub 也不拖垮整个 bot。

    GitHub App 启动要先请求一次 ``/app``，原版失败就直接抛出，而 NoneBot 不会兜住
    启动钩子里的异常——GitHub 抽风或 App 密钥失效时，所有功能都跟着起不来。这里改成
    记日志、后台每分钟重试，期间只有 GitHub 相关功能不可用。
    """

    async def _startup_app(self, app: GitHubApp | OAuthApp) -> None:
        try:
            await super()._startup_app(app)
        except Exception as e:
            logger.opt(exception=e).error(
                f"GitHub App {app.id} 启动失败，{GITHUB_RETRY_INTERVAL} 秒后重试"
            )
            task = asyncio.create_task(self._retry_startup_app(app))
            task.add_done_callback(self.tasks.discard)
            self.tasks.add(task)

    async def _retry_startup_app(self, app: GitHubApp | OAuthApp) -> None:
        while True:
            await asyncio.sleep(GITHUB_RETRY_INTERVAL)
            try:
                await super()._startup_app(app)
            except Exception as e:
                logger.warning(f"GitHub App {app.id} 仍然启动失败：{e!r}")
            else:
                logger.success(f"GitHub App {app.id} 重试启动成功")
                return


class HeaderAuthMilkyClientInfo(MilkyClientInfo):
    @override
    def ws_url(self):
        return super().ws_url().with_query(None)


class MilkyAdapter(BaseMilkyAdapter):
    """事件 WebSocket 的 access token 改放在 Authorization 头里。

    原版把 token 拼进 ``/event?access_token=...``，协议端连不上时每 3 秒打一条带完整
    URL 的 ERROR 日志，token 跟着进了日志和 Sentry。Milky 协议端两种方式都认。
    """

    def __init__(self, driver: Driver, **kwargs: Any):
        super().__init__(driver, **kwargs)
        # 连接在 on_ready 时才按这份配置发起，这里换掉还来得及
        self.milky_config.milky_clients = [
            HeaderAuthMilkyClientInfo(**info.model_dump())
            for info in self.milky_config.milky_clients
        ]

    @override
    @asynccontextmanager
    async def websocket(self, setup: Request) -> AsyncGenerator[WebSocket]:
        for info in self.milky_config.milky_clients:
            if info.access_token and setup.url == info.ws_url():
                setup.headers["Authorization"] = f"Bearer {info.access_token}"
        async with super().websocket(setup) as ws:
            yield ws


nonebot.init()
app = nonebot.get_asgi()

driver = nonebot.get_driver()
config = driver.config

driver.register_adapter(QQAdapter)
driver.register_adapter(FeishuAdapter)
driver.register_adapter(ONEBOT_V11Adapter)
driver.register_adapter(MilkyAdapter)
driver.register_adapter(GitHubAdapter)

nonebot.load_plugins("src/providers")
nonebot.load_all_plugins(set(config.plugins), {"src/plugins"}.union(config.plugin_dirs))

if __name__ == "__main__":
    nonebot.run(app="__mp_main__:app")
