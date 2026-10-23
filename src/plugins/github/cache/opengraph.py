from datetime import timedelta

from src.providers import cache

OPENGRAPH_CACHE_KEY = "github:opengraph:{type}:{identifier}"
OPENGRAPH_CACHE_EXPIRE = timedelta(days=1)


async def save_opengraph(type: str, identifier: str, img: bytes) -> None:
    """Save opengraph image to cache."""
    await cache.set(
        OPENGRAPH_CACHE_KEY.format(type=type, identifier=identifier),
        img,
        ex=OPENGRAPH_CACHE_EXPIRE,
    )


async def get_opengraph(type: str, identifier: str) -> bytes | None:
    """Get opengraph image from cache."""
    return await cache.get(OPENGRAPH_CACHE_KEY.format(type=type, identifier=identifier))
