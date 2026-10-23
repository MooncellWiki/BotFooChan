from pathlib import Path

import jinja2

env = jinja2.Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
    enable_async=True,
)

from . import auth as auth
