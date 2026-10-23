import asyncio

import nonebot
from nonebot import logger
from nonebot.adapters.feishu import Adapter as FeishuAdapter
from nonebot.adapters.github import Adapter as BaseGitHubAdapter
from nonebot.adapters.github.config import GitHubApp, OAuthApp
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter
from nonebot.adapters.qq import Adapter as QQAdapter

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


nonebot.init()
app = nonebot.get_asgi()

driver = nonebot.get_driver()
config = driver.config

driver.register_adapter(QQAdapter)
driver.register_adapter(FeishuAdapter)
driver.register_adapter(ONEBOT_V11Adapter)
driver.register_adapter(GitHubAdapter)

nonebot.load_plugins("src/providers")
nonebot.load_all_plugins(set(config.plugins), {"src/plugins"}.union(config.plugin_dirs))

if __name__ == "__main__":
    nonebot.run(app="__mp_main__:app")
