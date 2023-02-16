import re

from disnake.utils import remove_markdown

from utils.enums import BlacklistMode

BANNED_SYMBOLS = "!@#$%^&*(){}[]<>-_=+?~`:;'\"/\\|<>.,\n"
SYMBOL_MASK = {
    "!": "i",
    "1": "i",
    "0": "o",
    "$": "s",
    "(": "c",
    "[": "c",
    "{": "c",
    "3": "e",
    "@": "a",
    "🅰️": "a",
    "🅱️": "b",
    "🆎": "ab",
}

REG_INDICATOR_PATTERN = re.compile(r":regional_indicator_[a-z]:\s*")


def _extract_regional_indicator(s: str) -> str:
    s = s.replace("regional_indicator_", "")
    return re.search(r"[a-z]", s).group()


def _find_all_characters(s: str, char: str):
    positions = []
    for i, s in enumerate(s):
        if s == char:
            positions.append(i)

    return positions


def _format_expression(expr: str) -> str:
    expr = remove_markdown(expr.strip().lower().replace("\n", ""))
    reg_indicators = set(re.findall(REG_INDICATOR_PATTERN, expr))
    for ind in reg_indicators:
        ind: str
        expr = expr.replace(ind, _extract_regional_indicator(ind))

    new_expr = ""
    for s in expr:
        if s in SYMBOL_MASK:
            new_expr += SYMBOL_MASK[s]
        elif s in BANNED_SYMBOLS:
            continue
        else:
            new_expr += s

    return new_expr


def _apply_common_blacklist_detection(banned_words: list[str], expr: str) -> tuple[bool, str]:
    curse_words = set(banned_words) & set(expr.split(" "))
    for word in curse_words:
        expr = expr.replace(word, "#" * len(word))

    return len(curse_words) > 0, expr


def _apply_wildcard_blacklist_detection(banned_words: list[str], expr: str, break_immediately: bool) -> tuple[bool, str]:
    is_curse = False
    for word in banned_words:
        if word in expr:
            expr = expr.replace(word, "#" * len(word))
            is_curse = True
            if break_immediately:
                break

    return is_curse, expr


def _apply_super_blacklist_detection(banned_words: list[str], expr: str, break_immediately: bool) -> tuple[bool, str]:
    spaces_pos = _find_all_characters(expr, " ")
    is_curse, expr = _apply_wildcard_blacklist_detection(banned_words, expr.replace(" ", ""), break_immediately)
    if break_immediately:
        return is_curse, None

    expr_list = list(expr)
    for i in spaces_pos:
        expr_list.insert(i, " ")

    return is_curse, "".join(expr_list)


def is_blacklisted(bl, expr: str):
    expr = _format_expression(expr)
    common_is_curse, expr = _apply_common_blacklist_detection(bl.common, expr)
    if common_is_curse and not bl.filter_enabled:
        return True, None

    wild_is_curse, expr = _apply_wildcard_blacklist_detection(bl.wild, expr, not bl.filter_enabled)
    if wild_is_curse and not bl.filter_enabled:
        return True, None

    super_is_curse, expr = _apply_super_blacklist_detection(bl.super, expr, not bl.filter_enabled)

    return (
        any([common_is_curse, wild_is_curse, super_is_curse]),
        expr if bl.filter_enabled else None,
    )


def preformat(expr: str, mode: BlacklistMode):
    expr = _format_expression(expr)
    if mode == BlacklistMode.super:
        expr = expr.replace(" ", "")

    return expr
