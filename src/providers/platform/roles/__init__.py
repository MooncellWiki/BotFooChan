from enum import IntEnum


class RoleLevel(IntEnum):
    """Role level"""

    OWNER = 40
    ADMIN = 30
    MEMBER = 20
    GUEST = 10
    UNKNOWN = 0
