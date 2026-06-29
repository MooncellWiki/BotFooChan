from clilte import CommandLine
from arclet.alconna import Argv, set_default_argv_type

from ..version import __version__
from .plugins.tts import TTSUpdate

set_default_argv_type(Argv)
deepseek = CommandLine(
    title="NB CLI plugin for nonebot-plugin-deepseek",
    version=__version__,
    rich=True,
    _name="nb deepseek",
    load_preset=True,
)
deepseek.add(TTSUpdate)
