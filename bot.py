import nonebot
from nonebot.adapters.red import Adapter as REDAdapter
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11Adapter)
driver.register_adapter(REDAdapter)

config = driver.config

nonebot.load_all_plugins(set(config.plugins), {"src/plugins"}.union(config.plugin_dirs))

if __name__ == "__main__":
    nonebot.run()
