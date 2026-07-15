import re
from typing import Any


_PROTECTED_RE = re.compile(
    r"(<[^>]+>|https?://\S+|tg://\S+|@[A-Za-z0-9_]+)",
    flags=re.IGNORECASE,
)

_DIGRAPHS = {
    "a'": "аъ", "a‘": "аъ", "a`": "аъ", "aʻ": "аъ",
    "o'": "ў", "o‘": "ў", "o`": "ў", "oʻ": "ў",
    "g'": "ғ", "g‘": "ғ", "g`": "ғ", "gʻ": "ғ",
    "sh": "ш", "ch": "ч", "ng": "нг",
    "yo": "ё", "yu": "ю", "ya": "я", "ye": "е",
}

_LETTERS = str.maketrans({
    "a": "а", "b": "б", "c": "с", "d": "д", "e": "е", "f": "ф",
    "g": "г", "h": "ҳ", "i": "и", "j": "ж", "k": "к",
    "l": "л", "m": "м", "n": "н", "o": "о", "p": "п",
    "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у",
    "v": "в", "w": "в", "x": "х", "y": "й", "z": "з",
    "A": "А", "B": "Б", "C": "С", "D": "Д", "E": "Е", "F": "Ф",
    "G": "Г", "H": "Ҳ", "I": "И", "J": "Ж", "K": "К",
    "L": "Л", "M": "М", "N": "Н", "O": "О", "P": "П",
    "Q": "Қ", "R": "Р", "S": "С", "T": "Т", "U": "У",
    "V": "В", "W": "В", "X": "Х", "Y": "Й", "Z": "З",
})

_DISPLAY_FIELDS = {
    "text", "caption", "description", "explanation", "question",
    "message_text", "button_text",
}


def _match_case(source: str, replacement: str) -> str:
    if source.isupper():
        return replacement.upper()
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _convert_plain_text(text: str) -> str:
    for latin, cyrillic in sorted(_DIGRAPHS.items(), key=lambda item: -len(item[0])):
        text = re.sub(
            re.escape(latin),
            lambda match: _match_case(match.group(0), cyrillic),
            text,
            flags=re.IGNORECASE,
        )
    return text.translate(_LETTERS)


def latin_to_cyrillic(text: str) -> str:
    """Convert visible Uzbek Latin text while preserving HTML tags and links."""
    parts = _PROTECTED_RE.split(text)
    return "".join(
        part if _PROTECTED_RE.fullmatch(part or "") else _convert_plain_text(part)
        for part in parts
    )


def cyrillize_telegram_payload(value: Any, field_name: str | None = None) -> Any:
    """Copy an outgoing aiogram payload and convert only user-visible strings."""
    if isinstance(value, str):
        return latin_to_cyrillic(value) if field_name in _DISPLAY_FIELDS else value
    if isinstance(value, list):
        return [cyrillize_telegram_payload(item, field_name) for item in value]
    if isinstance(value, tuple):
        return tuple(cyrillize_telegram_payload(item, field_name) for item in value)
    if isinstance(value, dict):
        return {
            key: cyrillize_telegram_payload(item, key)
            for key, item in value.items()
        }

    model_fields = getattr(value.__class__, "model_fields", None)
    if model_fields and hasattr(value, "model_copy"):
        updates = {}
        for name in model_fields:
            current = getattr(value, name, None)
            converted = cyrillize_telegram_payload(current, name)
            if converted is not current:
                updates[name] = converted
        return value.model_copy(update=updates) if updates else value

    return value
