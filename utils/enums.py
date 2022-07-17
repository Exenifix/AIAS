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


class ActionType(Enum):
    SINGLE_DELETION = 0
    ANTISPAM = 1
    QUEUE_DELETION = 2
    TIMEOUT = 3
    NICK_CHANGE = 4
    ANTIRAID_BAN = 5
    ANTIRAID_KICK = 6


class AntiraidPunishment(Enum):
    BAN = 0
    KICK = 1
    TIMEOUT = 2


class Stat(Enum):
    SPAM_BLOCKED = 0
    BAD_WORDS_BLOCKED = 1
    BAD_CHARACTERS_BLOCKED = 2
    RAIDERS_PUNISHED = 3
    NICKNAMES_FILTERED = 4
    MESSAGES_PROCESSED = 5
