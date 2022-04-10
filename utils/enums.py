from enum import Enum


class FetchMode(Enum):
    NONE = 0
    VAL = 1
    ROW = 2
    ALL = 3


class BlacklistMode(Enum):
    common = "common"
    wild = "wild"
    super = "super"


class ViewResponse(Enum):
    YES = 0
    NO = 1
    EXIT = 2
    TIMEOUT = 3
