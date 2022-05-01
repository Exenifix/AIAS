import re
from collections import namedtuple

CHANNEL_REGEX = re.compile(r"<#\d{18}>")
ROLE_REGEX = re.compile(r"<@&\d{18}>")
MENTION_REGEX = re.compile(r"<@!?\d{18}>")
EMOJI_REGEX = re.compile(r"<a?:[A-Za-z0-9_]*:\d{18}>")

analysis_data = namedtuple(
    "analysis_data", ["total_chars", "unique_chars", "total_words", "unique_words"]
)


def extract_mentions(content: str) -> str:
    channels: set[str] = set(re.findall(CHANNEL_REGEX, content))
    for i, channel in enumerate(channels):
        content = content.replace(channel, f"c{i}")

    roles: set[str] = set(re.findall(ROLE_REGEX, content))
    for i, role in enumerate(roles):
        content = content.replace(role, f"r{i}")

    mentions: set[str] = set(re.findall(MENTION_REGEX, content))
    for i, mention in enumerate(mentions):
        content = content.replace(mention, f"m{i}")

    emojis: set[str] = set(re.findall(EMOJI_REGEX, content))
    for i, emoji in enumerate(emojis):
        content = content.replace(emoji, f"e{i}")

    return content


def analyse_sample(sample: str) -> analysis_data:
    """Returns results of the text analysis.

    `total_chars, unique_chars, total_words, unique_words = analyse_sample(sample)`"""
    sample = extract_mentions(sample)
    nospace = sample.replace(" ", "")
    splat = sample.split(" ")
    return analysis_data(
        len(nospace),
        len(set(nospace)),
        len(splat),
        len(set(splat)),
    )
