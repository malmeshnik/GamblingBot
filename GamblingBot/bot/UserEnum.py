from enum import Enum

class UserStatus(Enum):
    ACTIVE = 'active'
    BLOCKED = 'blocked'
    DELETED = 'deleted'
    FORBIDDEN = 'forbidden'