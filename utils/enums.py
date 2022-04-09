from enum import Enum


class FetchMode(Enum):
    NONE = 0
    VAL = 1
    ROW = 2
    ALL = 3


class BlacklistMode(Enum):
    common = "common"
    wild = "wild"
    wildcard = "wild"
    super = "super"
