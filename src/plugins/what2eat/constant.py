import json
from pathlib import Path

assets_path = Path(__file__).parent / "assets"


def resolve_data(name: str):
    dest = assets_path / name

    return json.loads(dest.read_text(encoding="utf-8"))


drinks = resolve_data("drinks.json")
eatings = resolve_data("eatings.json")
