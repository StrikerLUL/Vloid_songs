# lyrics.py – Liedtext aus der App in Silben pro Sektion zerlegen
import re

# Schreibweisen der Sektions-Überschriften, die auf den internen Namen zeigen
_SECTION_ALIASES = {
    "verse": "Verse",
    "prechorus": "PreChorus",
    "pre-chorus": "PreChorus",
    "pre chorus": "PreChorus",
    "chorus": "Chorus",
    "bridge": "Bridge",
    "intro": "Intro",
    "outro": "Outro",
    "build-up": "Build-up",
    "buildup": "Build-up",
    "drop": "Drop",
}

_HEADER = re.compile(r"^\[(.+)\]$")


def normalize_section(name: str) -> str:
    """'[Pre-Chorus]' und 'prechorus' werden beide zu 'PreChorus'."""
    key = name.strip().lower()
    return _SECTION_ALIASES.get(key, name.strip())


def parse_lyrics(text: str) -> dict:
    """
    Zerlegt den Lyrics-Text der App in {Sektion: [Silben]}.
    Format: eine Überschrift wie [Verse] pro Sektion, darunter Silben mit Leerzeichen getrennt.
    Text vor der ersten Überschrift wird ignoriert.
    """
    sections = {}
    current = None
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        header = _HEADER.match(line)
        if header:
            current = normalize_section(header.group(1))
            sections.setdefault(current, [])
        elif current and line:
            sections[current].extend(line.split())
    return {name: syllables for name, syllables in sections.items() if syllables}
