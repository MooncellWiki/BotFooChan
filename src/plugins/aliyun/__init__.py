from pathlib import Path

import nonebot

from .config import Config

# load all github plugin config from global config
config = Config.parse_obj(nonebot.get_driver().config)

# load all github subplugins
_sub_plugins = set()
_sub_plugins |= nonebot.load_plugins(str((Path(__file__).parent / "plugins").resolve()))
