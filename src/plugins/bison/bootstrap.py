from nonebot import get_driver
from nonebot.log import logger

from .config.db_migration import data_migrate
from .scheduler.manager import init_scheduler

# nonebot 的 startup 钩子按注册顺序依次执行，插件入口里先 require 了
# nonebot_plugin_orm，所以这里跑的时候数据库已经初始化完毕
_driver = get_driver()


@_driver.on_startup
async def startup():
    await data_migrate()
    await init_scheduler()
    logger.info("bison bootstrap done")
