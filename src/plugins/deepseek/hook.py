from nonebot import get_driver, logger
from nonebot_plugin_alconna import command_manager
from nonebot_plugin_localstore import get_plugin_cache_dir

driver = get_driver()
cache_dir = get_plugin_cache_dir() / "shortcut.db"


@driver.on_startup
async def _() -> None:
    command_manager.load_cache(cache_dir)
    logger.debug("DeepSeek shortcuts cache loaded")


@driver.on_shutdown
async def _() -> None:
    command_manager.dump_cache(cache_dir)
    logger.debug("DeepSeek shortcuts cache dumped")
