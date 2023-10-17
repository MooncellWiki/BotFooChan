import nonebot
from nonebot.adapters.red import Adapter as REDAdapter
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter

nonebot.init()
app = nonebot.get_asgi()

driver = nonebot.get_driver()
config = driver.config

driver.register_adapter(ONEBOT_V11Adapter)
if config.use_red:
    driver.register_adapter(REDAdapter)

nonebot.load_all_plugins(set(config.plugins), {"src/plugins"}.union(config.plugin_dirs))

if __name__ == "__main__":
    nonebot.run(app="__mp_main__:app")
