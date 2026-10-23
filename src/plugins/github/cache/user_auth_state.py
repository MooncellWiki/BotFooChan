from datetime import timedelta
from uuid import uuid4

from pydantic import TypeAdapter

from src.providers import cache
from src.providers.platform import UserInfo

STATE_CACHE_KEY = "github:auth:state:{state_id}"
STATE_CACHE_EXPIRE = timedelta(minutes=10)


async def create_state(user: UserInfo) -> str:
    """Create state cache

    Args:
        data: State data

    Returns:
        State id
    """
    state_id = uuid4().hex
    await cache.set(
        STATE_CACHE_KEY.format(state_id=state_id),
        user.model_dump_json(),
        ex=STATE_CACHE_EXPIRE,
    )
    return state_id


async def get_state(state_id: str) -> UserInfo | None:
    """Get state cache

    Args:
        state_id: State id

    Returns:
        Existing state data
    """
    if data := await cache.get(STATE_CACHE_KEY.format(state_id=state_id)):
        return TypeAdapter(UserInfo).validate_json(data)


async def delete_state(state_id: str) -> None:
    """Delete state cache

    Args:
        state_id: State id
    """
    await cache.delete(STATE_CACHE_KEY.format(state_id=state_id))
