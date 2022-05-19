import re
from collections import namedtuple

CHANNEL_REGEX = re.compile(r"<#\d{18}>")
ROLE_REGEX = re.compile(r"<@&\d{18}>")
MENTION_REGEX = re.compile(r"<@!?\d{18}>")
EMOJI_REGEX = re.compile(r"<a?:\w*:\d{18}>")

analysis_data = namedtuple(
    "analysis_data",
    ["total_chars", "unique_chars", "total_words", "unique_words", "content"],
)


def extract_mentions(content: str) -> str:
    for name, regex in (
            ("c", CHANNEL_REGEX),
            ("r", ROLE_REGEX),
            ("m", MENTION_REGEX),
            ("e", EMOJI_REGEX),
    ):
        entries: set[str] = set(re.findall(regex, content))
        for i, entry in enumerate(entries):
            content = content.replace(entry, f"{name}{i}")

    return content


def analyse_sample(sample: str) -> analysis_data:
    """Returns results of the text analysis.

    `total_chars, unique_chars, total_words, unique_words, content = analyse_sample(sample)`"""
    sample = extract_mentions(sample.lower())
    nospace = sample.replace(" ", "")
    splat = sample.split(" ")
    return analysis_data(
        len(nospace), len(set(nospace)), len(splat), len(set(splat)), sample
    )
