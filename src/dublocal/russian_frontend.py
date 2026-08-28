from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path


_ACUTE = "\u0301"
_VOWELS_CYR = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"
_WORD_RE = re.compile(r"[а-яёА-ЯЁ\u0301]+")
_NUMBER_RE = re.compile(r"(?<![\w\u0301])([+-]?\d+(?:[.,]\d+)?)(?![\w\u0301])")
_STRESS = {"ˈ", "ˌ"}
_VOWELS_IPA = set("aɑoeiuyʌəɪɐɛɨ")
_REDUCIBLE = set("aɑoʌə")

_ONES_MASC = ("", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять")
_ONES_FEM = ("", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять")
_TEENS = (
    "десять",
    "одиннадцать",
    "двенадцать",
    "тринадцать",
    "четырнадцать",
    "пятнадцать",
    "шестнадцать",
    "семнадцать",
    "восемнадцать",
    "девятнадцать",
)
_TENS = ("", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто")
_HUNDREDS = ("", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "семьсот", "восемьсот", "девятьсот")
_DIGIT_WORDS = ("ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять")
_SCALES = (
    (1_000_000_000, ("миллиард", "миллиарда", "миллиардов"), False),
    (1_000_000, ("миллион", "миллиона", "миллионов"), False),
    (1_000, ("тысяча", "тысячи", "тысяч"), True),
)

# eSpeak symbols that are not present in the Russian Kokoro v2 vocabulary but
# have a stable equivalent there. This is deliberately a small compatibility
# map; unknown symbols are reported rather than silently discarded.
_NORMALIZE = (
    ('u"', "u"),
    ("ɭ", "l"),
    ("ɵ", "o"),
    ("ʑ", "ʒ"),
    ("ʐ", "ʒ"),
    ("ʧʲ", "ʧ"),
)

# A compact set of standard Russian pronunciation corrections that materially
# helps narration while keeping this implementation independent from any one
# upstream G2P source file.
_WORD_REPLACEMENTS = {
    "конечно": "конешно",
    "скучно": "скушно",
    "скучный": "скушный",
    "нарочно": "нарошно",
    "яичница": "яишница",
    "скворечник": "скворешник",
    "девичник": "девишник",
    "прачечная": "прашечная",
}
_CLUSTER_REPLACEMENTS = (
    ("солнц", "сонц"),
    ("чувств", "чуств"),
    ("здравств", "здраств"),
    ("счастлив", "счаслив"),
)
_OGO_EXCEPTIONS = {
    "много",
    "немного",
    "намного",
    "строго",
    "дорого",
    "недорого",
    "полого",
    "убого",
    "лего",
    "диего",
    "ого",
}


def _plural_form(value: int, forms: tuple[str, str, str]) -> str:
    tail100 = value % 100
    if 11 <= tail100 <= 14:
        return forms[2]
    tail10 = value % 10
    if tail10 == 1:
        return forms[0]
    if 2 <= tail10 <= 4:
        return forms[1]
    return forms[2]


def _triplet_to_words(value: int, *, feminine: bool = False) -> list[str]:
    value = max(0, min(999, int(value)))
    words: list[str] = []
    hundreds = value // 100
    if hundreds:
        words.append(_HUNDREDS[hundreds])
    remainder = value % 100
    if 10 <= remainder <= 19:
        words.append(_TEENS[remainder - 10])
        return words
    tens = remainder // 10
    ones = remainder % 10
    if tens:
        words.append(_TENS[tens])
    if ones:
        words.append((_ONES_FEM if feminine else _ONES_MASC)[ones])
    return words


def _integer_to_russian(value: int) -> str:
    if value == 0:
        return "ноль"
    if abs(value) >= 1_000_000_000_000:
        digits = " ".join(_DIGIT_WORDS[int(char)] for char in str(abs(value)))
        return f"минус {digits}" if value < 0 else digits

    negative = value < 0
    remainder = abs(value)
    words: list[str] = []
    for scale, forms, feminine in _SCALES:
        group = remainder // scale
        if not group:
            continue
        words.extend(_triplet_to_words(group, feminine=feminine))
        words.append(_plural_form(group, forms))
        remainder %= scale
    words.extend(_triplet_to_words(remainder))
    result = " ".join(words).strip()
    return f"минус {result}" if negative else result


def _number_to_russian(raw: str) -> str:
    value = raw.strip()
    sign = ""
    if value[:1] in {"+", "-"}:
        sign, value = value[0], value[1:]
    separator = "," if "," in value else "." if "." in value else None
    if separator is None:
        integer = int(value or "0")
        if sign == "-":
            integer = -integer
        return _integer_to_russian(integer)

    whole, fraction = value.split(separator, 1)
    integer = int(whole or "0")
    if sign == "-":
        integer = -integer
    fractional = " ".join(_DIGIT_WORDS[int(char)] for char in fraction if char.isdigit())
    if not fractional:
        return _integer_to_russian(integer)
    return f"{_integer_to_russian(integer)} запятая {fractional}"


def _normalize_input_text(text: str) -> str:
    """Make subtitle text safe and pronounceable before RUAccent/eSpeak.

    Web captions can contain invisible Unicode format controls such as ZWJ/ZWNJ,
    BOM and bidi marks. They have no spoken value and previously could leak through
    the Russian frontend into Kokoro's phoneme vocabulary. Numeric tokens are also
    expanded before G2P so raw digits never become provider OOV symbols.
    """

    value = unicodedata.normalize("NFKC", str(text or ""))
    value = _NUMBER_RE.sub(lambda match: _number_to_russian(match.group(1)), value)
    cleaned: list[str] = []
    for char in value:
        category = unicodedata.category(char)
        if category == "Cf":
            # Format controls have no spoken value. Remove them rather than
            # inserting a separator so a hidden ZWJ inside a word cannot split it.
            continue
        if category == "Zs":
            cleaned.append(" ")
        else:
            cleaned.append(char)
    value = "".join(cleaned)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    return value.strip()


def _plus_to_acute(text: str) -> str:
    return re.sub(rf"\+([{_VOWELS_CYR}])", lambda match: match.group(1) + _ACUTE, text)


def _vowel_ordinal_before_acute(word: str) -> int | None:
    index = word.find(_ACUTE)
    if index <= 0:
        return None
    return sum(1 for char in word[:index] if char in _VOWELS_CYR)


def _restore_acute_by_ordinal(word: str, ordinal: int | None) -> str:
    if not ordinal:
        return word
    out: list[str] = []
    seen = 0
    for char in word:
        out.append(char)
        if char in _VOWELS_CYR:
            seen += 1
            if seen == ordinal:
                out.append(_ACUTE)
    return "".join(out)


def _respell_word(word: str) -> str:
    lower = word.lower()
    bare = lower.replace(_ACUTE, "")
    ordinal = _vowel_ordinal_before_acute(lower)

    replacement = _WORD_REPLACEMENTS.get(bare)
    if replacement:
        return _restore_acute_by_ordinal(replacement, ordinal)

    edited = bare
    for old, new in _CLUSTER_REPLACEMENTS:
        edited = edited.replace(old, new)

    # Adjectival/pronominal final -ого/-его is pronounced -ово/-ево. Do not
    # rewrite common adverbs/loans where /g/ is retained.
    if bare not in _OGO_EXCEPTIONS and re.search(r"[ое]го$", edited):
        edited = edited[:-2] + "во"

    return _restore_acute_by_ordinal(edited, ordinal)


def _respell(text: str) -> str:
    return _WORD_RE.sub(lambda match: _respell_word(match.group(0)), text)


def _reduce_ipa_word(token: str) -> str:
    chars = list(token)
    vowel_positions = [index for index, char in enumerate(chars) if char in _VOWELS_IPA]
    if not vowel_positions:
        return token

    stressed: set[int] = set()
    primary = token.find("ˈ")
    for index, char in enumerate(chars):
        if char not in _STRESS:
            continue
        # A post-primary secondary mark on Russian reflexive endings is commonly
        # an eSpeak artefact, so do not treat it as a real stressed nucleus.
        if char == "ˌ" and primary >= 0 and index > primary:
            continue
        following = next((pos for pos in vowel_positions if pos > index), None)
        if following is not None:
            stressed.add(following)

    stressed_ordinals = sorted(vowel_positions.index(pos) for pos in stressed)
    for ordinal, index in enumerate(vowel_positions):
        if index in stressed or chars[index] not in _REDUCIBLE:
            continue
        if index > 0 and chars[index - 1] in {"ʲ", "j"}:
            chars[index] = "ɪ"
            continue
        next_stress = next((value for value in stressed_ordinals if value > ordinal), None)
        chars[index] = "ɐ" if index == 0 or next_stress == ordinal + 1 else "ə"

    if primary >= 0:
        chars = [
            char
            for index, char in enumerate(chars)
            if not (char == "ˌ" and index > primary)
        ]
    return "".join(chars)


def _normalize_ipa(ipa: str) -> str:
    value = unicodedata.normalize("NFC", ipa).replace("_", " ")
    # eSpeak (and, on some paths, upstream text processors) can preserve or emit
    # invisible Unicode format controls such as U+200D. They are not phonemes and
    # must never reach Kokoro's vocabulary guard.
    value = "".join(char for char in value if unicodedata.category(char) != "Cf")
    for old, new in _NORMALIZE:
        value = value.replace(old, new)
    value = re.sub(r"ɕ(?!ː)", "ɕː", value)
    value = " ".join(_reduce_ipa_word(token) for token in value.split())
    return re.sub(r"\s+", " ", value).strip()


class _TokenTypeIdsShim:
    """Keep RUAccent ONNX exports usable with newer Transformers tokenizers."""

    def __init__(self, tokenizer):
        self._tokenizer = tokenizer

    def __call__(self, *args, **kwargs):
        import numpy as np

        encoded = self._tokenizer(*args, **kwargs)
        if "token_type_ids" not in encoded and "input_ids" in encoded:
            encoded["token_type_ids"] = np.zeros_like(encoded["input_ids"])
        return encoded

    def __getattr__(self, name):
        return getattr(self._tokenizer, name)


def _patch_ruaccent_tokenizers(accent) -> None:
    for attribute in ("accent_model", "omograph_model", "stress_usage_predictor"):
        model = getattr(accent, attribute, None)
        session = getattr(model, "session", None)
        tokenizer = getattr(model, "tokenizer", None)
        if session is None or tokenizer is None:
            continue
        try:
            names = {item.name for item in session.get_inputs()}
        except Exception:
            continue
        if "token_type_ids" in names:
            model.tokenizer = _TokenTypeIdsShim(tokenizer)


class RussianFrontend:
    """Russian text -> Kokoro-compatible phonemes using local prepared assets.

    RUAccent is MIT-licensed. eSpeak NG is deliberately called as a separately
    installed executable; DubLocal neither imports nor bundles the GPL phonemizer
    Python package. The prepared provider supplies only the acute-aware eSpeak data.
    """

    def __init__(
        self,
        provider_root: str | Path,
        config_path: str | Path,
        *,
        accent_workdir: str | Path | None = None,
    ) -> None:
        root = Path(provider_root).expanduser().resolve()
        data = root / "espeak-data"
        if not data.is_dir():
            raise RuntimeError(f"Russian TTS provider is missing acute-aware eSpeak data: {data}")
        executable = shutil.which("espeak-ng") or shutil.which("espeak")
        if not executable:
            raise RuntimeError(
                "Russian TTS needs the separately installed eSpeak NG executable. "
                "Prepare Russian TTS from DubLocal Settings first."
            )
        self.espeak = executable
        self.espeak_data = data

        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self.vocab = set(str(config.get("vocab") or "")) if isinstance(config.get("vocab"), str) else set(config["vocab"])

        try:
            from ruaccent import RUAccent
        except ImportError as exc:
            raise RuntimeError("Russian TTS runtime is missing RUAccent.") from exc
        self.accent = RUAccent()
        kwargs = {
            "omograph_model_size": "turbo3.1",
            "use_dictionary": True,
            "tiny_mode": False,
            "device": "CPU",
        }
        if accent_workdir:
            path = Path(accent_workdir).expanduser().resolve()
            path.mkdir(parents=True, exist_ok=True)
            kwargs["workdir"] = str(path)
        self.accent.load(**kwargs)
        _patch_ruaccent_tokenizers(self.accent)

    @staticmethod
    def _brackets(text: str) -> str:
        return text.translate(str.maketrans({"[": "(", "]": ")", "{": "(", "}": ")"}))

    def accentuate(self, text: str) -> str:
        safe_text = _normalize_input_text(text)
        processed = self.accent.process_all(self._brackets(safe_text))
        # Defensive second boundary: if RUAccent itself emits a format control,
        # remove it before eSpeak sees the marked Russian text.
        processed_text = "".join(
            char for char in str(processed) if unicodedata.category(char) != "Cf"
        )
        return _plus_to_acute(processed_text)

    def _espeak_ipa(self, marked: str) -> str:
        env = os.environ.copy()
        env["ESPEAK_DATA_PATH"] = str(self.espeak_data)
        command = [self.espeak, "-q", "--ipa=3", "-v", "ru", marked]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=30,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "eSpeak NG failed").strip()
            raise RuntimeError(f"Russian phonemization failed: {detail}")
        return completed.stdout.strip()

    def phonemize(self, text: str) -> tuple[str, set[str]]:
        marked = _respell(self.accentuate(text).lower())
        phonemes = _normalize_ipa(self._espeak_ipa(marked))
        oov = {char for char in phonemes if char != " " and char not in self.vocab}
        return phonemes, oov

    __call__ = phonemize
