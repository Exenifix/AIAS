from collections import namedtuple

analysis_data = namedtuple(
    "analysis_data", ["total_chars", "unique_chars", "total_words", "unique_words"]
)


def analyse_sample(sample: str) -> tuple[int, int, int, int]:
    """Returns results of the text analysis.

    `total_chars, unique_chars, total_words, unique_words = analyse_sample(sample)`"""
    nospace = sample.replace(" ", "")
    splat = sample.split(" ")
    return analysis_data(
        len(nospace),
        len(set(nospace)),
        len(splat),
        len(set(splat)),
    )
