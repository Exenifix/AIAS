def contains_fonts(allowed_symbols: str, content: str) -> tuple[bool, set[str]]:
    allowed_symbols = set(allowed_symbols)
    allowed_symbols.add(" ")
    content = set(content.replace(" ", "").lower())
    return not allowed_symbols >= content, content - allowed_symbols
