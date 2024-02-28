import nonebot
from nonebot.adapters.qq import Adapter as QQAdapter
from nonebot.adapters.feishu import Adapter as FeishuAdapter
from nonebot.adapters.satori import Adapter as SatoriAdapter
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter

nonebot.init()
app = nonebot.get_asgi()

driver = nonebot.get_driver()
config = driver.config

driver.register_adapter(QQAdapter)
driver.register_adapter(SatoriAdapter)
driver.register_adapter(FeishuAdapter)
driver.register_adapter(ONEBOT_V11Adapter)

nonebot.load_all_plugins(set(config.plugins), {"src/plugins"}.union(config.plugin_dirs))

if __name__ == "__main__":
    nonebot.run(app="__mp_main__:app")
