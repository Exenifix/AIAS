from random import choice
from string import ascii_lowercase
from typing import Optional

VOWELS = "aeiou"
CONSONANTS = "".join(s for s in ascii_lowercase if s not in VOWELS)
NICK_PATTERNS = [
    "bababa",
    "babes",
    "abab",
    "ababab",
    "babis",
    "abis",
    "abaab",
    "baab",
    "bababas",
    "baabaas",
    "babaab",
]


def generate_random_nick(pattern: Optional[str] = None):
    pattern = pattern or choice(NICK_PATTERNS)
    result = ""
    ignore_next = False
    for s in pattern:
        if ignore_next:
            ignore_next = False
            result += s
        elif s == "\\":
            ignore_next = True
        elif s == "a":
            result += choice(VOWELS)
        elif s == "b":
            result += choice(CONSONANTS)
        else:
            result += s

    return result.capitalize()
