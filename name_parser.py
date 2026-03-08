"""
name_parser.py
Parses raw name strings into 4-column dicts:
    last_name_1, last_name_2, first_name_1, first_name_2, include
"""

import re


def parse_lines(
    raw_text: str,
    order: str,
    separator: str,
    num_apellido_words: int,
    num_nombre_words: int,
    composite_triggers: list[str],
    capitalize: str,
) -> list[dict]:
    """
    Parse raw pasted text into a list of dicts with keys:
        last_name_1, last_name_2, first_name_1, first_name_2, include

    Parameters
    ----------
    raw_text : str
        One name per line, as pasted by the user.
    order : str
        "last_first"  → apellido block comes before nombre block
        "first_last"  → nombre block comes before apellido block
    separator : str
        Exception separator. If found in a line, it overrides word-count logic:
        everything before = apellido side, everything after = nombre side.
        If empty or not found, falls back to consuming num_apellido_words from
        one end and num_nombre_words from the other.
    num_apellido_words : int
        Default number of apellido parts to extract (used when no separator found).
    num_nombre_words : int
        Default number of nombre parts to extract (used when no separator found).
    composite_triggers : list[str]
        Uppercase prefixes that signal a composite apellido, e.g. ["DE LA", "DEL"].
        Longer triggers are tried first.
    capitalize : str
        "UPPER" | "TITLE" | "AS_IS"
    """
    triggers = sorted(
        [t.strip().upper() for t in composite_triggers if t.strip()],
        key=len,
        reverse=True,
    )

    rows = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue

        apellido_parts, nombre_parts = _split_line(
            line, order, separator, num_apellido_words, num_nombre_words, triggers
        )

        def cap(s):
            return _apply_cap(s, capitalize)

        rows.append({
            "last_name_1":  cap(apellido_parts[0]) if len(apellido_parts) > 0 else "",
            "last_name_2":  cap(apellido_parts[1]) if len(apellido_parts) > 1 else "",
            "first_name_1": cap(nombre_parts[0])   if len(nombre_parts)   > 0 else "",
            "first_name_2": cap(nombre_parts[1])   if len(nombre_parts)   > 1 else "",
            "include": True,
        })

    return rows


def _split_line(
    line: str,
    order: str,
    separator: str,
    num_apellido_words: int,
    num_nombre_words: int,
    triggers: list[str],
) -> tuple[list[str], list[str]]:
    """
    Return (apellido_parts, nombre_parts) — each a list of part strings.
    A "part" may be multi-word (e.g. "DE LA TORRE" is one apellido part).
    """
    use_separator = bool(separator) and separator in line

    if use_separator:
        left, _, right = line.partition(separator)
        left_tokens  = re.split(r"\s+", left.strip())
        right_tokens = re.split(r"\s+", right.strip())

        if order == "last_first":
            apellido_parts = _parts_from_front(left_tokens,  num_apellido_words, triggers)
            nombre_parts   = _parts_from_front(right_tokens, num_nombre_words,   [])
        else:
            nombre_parts   = _parts_from_front(left_tokens,  num_nombre_words,   [])
            apellido_parts = _parts_from_front(right_tokens, num_apellido_words, triggers)

    else:
        # Fallback: consume from both ends
        all_tokens = re.split(r"\s+", line)
        if order == "last_first":
            apellido_parts, remaining = _consume_parts_from_front(
                all_tokens, num_apellido_words, triggers
            )
            nombre_parts = _parts_from_back(remaining, num_nombre_words)
        else:
            nombre_parts, remaining = _consume_parts_from_front(
                all_tokens, num_nombre_words, []
            )
            apellido_parts = _parts_from_back(remaining, num_apellido_words)

    return apellido_parts, nombre_parts


def _parts_from_front(
    tokens: list[str], num_parts: int, triggers: list[str]
) -> list[str]:
    """Return up to num_parts part-strings from the front, respecting composite triggers."""
    parts, _ = _consume_parts_from_front(tokens, num_parts, triggers)
    return parts


def _consume_parts_from_front(
    tokens: list[str], num_parts: int, triggers: list[str]
) -> tuple[list[str], list[str]]:
    """
    Consume up to `num_parts` parts from the front of `tokens`.
    Each part is returned as a single string (may be multi-word for composites).
    Returns (list_of_part_strings, remaining_tokens).
    """
    upper_tokens = [t.upper() for t in tokens]
    parts = []
    idx = 0

    for _ in range(num_parts):
        if idx >= len(tokens):
            break
        matched = False
        for trigger in triggers:
            trigger_words = trigger.split()
            end = idx + len(trigger_words)
            if upper_tokens[idx:end] == trigger_words and end < len(tokens):
                # Composite: consume trigger words + the following word as one part
                part = " ".join(tokens[idx : end + 1])
                parts.append(part)
                idx = end + 1
                matched = True
                break
        if not matched:
            parts.append(tokens[idx])
            idx += 1

    return parts, tokens[idx:]


def _parts_from_back(tokens: list[str], num_parts: int) -> list[str]:
    """Return the last `num_parts` tokens as individual part strings."""
    if num_parts >= len(tokens):
        return list(tokens)
    return list(tokens[-num_parts:])


def _apply_cap(text: str, mode: str) -> str:
    if mode == "UPPER":
        return text.upper()
    if mode == "TITLE":
        return text.title()
    return text
