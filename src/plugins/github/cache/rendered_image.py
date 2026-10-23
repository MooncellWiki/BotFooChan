from datetime import timedelta

from src.providers import cache

IMAGE_CACHE_KEY = "github:image:{type}:{identifier}"
# cache identifier is the hash of the image context content
# so we can make cache expire time longer
IMAGE_CACHE_EXPIRE = timedelta(days=7)


async def save_rendered_image(type: str, identifier: str, img: bytes) -> None:
    """Save rendered image to cache."""
    await cache.set(
        IMAGE_CACHE_KEY.format(type=type, identifier=identifier),
        img,
        ex=IMAGE_CACHE_EXPIRE,
    )


async def get_rendered_image(type: str, identifier: str) -> bytes | None:
    """Get rendered image from cache."""
    return await cache.get(IMAGE_CACHE_KEY.format(type=type, identifier=identifier))
