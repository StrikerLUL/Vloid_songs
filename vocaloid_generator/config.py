# config.py – Zentrale Einstellungen für den gesamten Generator
import os

# ── Tempo & Takt ──────────────────────────────────────────────────────────────
BPM = 150                          # Tempo (typisch Vocaloid: 140–175)
TAKT = 4                           # 4/4-Takt

# ── Tonart & Skala ────────────────────────────────────────────────────────────
KEY   = "B"                        # Grundton: A, C, D, F, G, B, E
MODE  = "minor"                    # Skala:  minor | major | dorian | phrygian
STYLE = "Rock"                    # Genre: J-Pop | Rock | EDM | Lo-Fi
STRICT_SCALE_LOCKING = True

# ── Akkord-Stil ───────────────────────────────────────────────────────────────
# classic_minor | jpop | dramatic | happy | emotional
CHORD_STYLE = "j-rock minor"

# ── Song-Struktur ─────────────────────────────────────────────────────────────
SONG_STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]

SECTION_CONFIG = {
    "Intro":     {"bars": 8,  "has_vocals": False},
    "Build-up":  {"bars": 4,  "has_vocals": False},
    "Verse":     {"bars": 16, "has_vocals": True},
    "PreChorus": {"bars": 8,  "has_vocals": True},
    "Chorus":    {"bars": 16, "has_vocals": True},
    "Bridge":    {"bars": 8,  "has_vocals": True},
    "Drop":      {"bars": 2,  "has_vocals": False},
    "Solo":      {"bars": 8,  "has_vocals": False},   # Instrumental-Solo der Lead-Stimme über den Refrain-Akkorden
    "Outro":     {"bars": 8,  "has_vocals": False},
}

# ── Vocals / Synthesizer ──────────────────────────────────────────────────────
VOCAL_SPRACHE   = "japanese"
VOCAL_MAX_PITCH = 78               # A5  – hohe Vocaloid-Stimme
VOCAL_MIN_PITCH = 59               # F3  – verhindert zu tiefe Töne
VOCAL_MIX_LEVEL = 0.25

VOCAL_SHIMMER   = True             # Vocaloid-Chorus-Effekt (leichtes Pitch-Shimmer)
VOCAL_BREATHINESS = 0.060          # 0.0 (trocken) – 0.12 (sehr hauchig)
VOCAL_VIBRATO_RATE = 6.0           # Hz  (typisch 5–6.5 für J-Pop)
VOCAL_VIBRATO_DEPTH = 0.022        # Semitöne (etwas ausdrucksstärker)

# ── Swing ─────────────────────────────────────────────────────────────────────
SWING = 0.00                       # 0.0 = gerade | 0.5 = volles Shuffle

# ── Lyrics (Natural Japanese, grammatically correct and phonetically natural) ──
SONG_TEXT_VERSE     = "画面の隅で呟いた夜に誰にも届かない歌を書いた"
SONG_TEXT_PRECHORUS = "ボイストラック再生して溜め息ひとつだけどまだ終われない"
SONG_TEXT_CHORUS    = "響けよロックンロール叫べ今すぐ僕らの声を掻き鳴らせ"
SONG_TEXT_BRIDGE    = "例え世界がそっぽを向いてもこの熱は消せやしないから"

# Internal mapping to translate natural Kanji/Kana lyrics into space-separated kana syllables
SONG_TEXT_KANA_MAP = {
    SONG_TEXT_VERSE:     "が め ん の す み で つ ぶ や い た よ る に だ れ に も と ど か な い う た を か い た",
    SONG_TEXT_PRECHORUS: "ぼ い す と ら っ く さ い せ い し て た め い き ひ と つ だ け ど ま だ お わ れ な い",
    SONG_TEXT_CHORUS:    "ひ び け よ ろ っく ん ろ お る さ け べ い ま す ぐ ぼ く ら の こ え を か き な ら せ",
    SONG_TEXT_BRIDGE:    "た と え せ か い が そ っ ぽ を む い て も こ の ね つ は け せ や し な い か ら"
}

# ── Energy Curve ─────────────────────────────────────────────────────────────
# Maps each song section to its designated energy level
ENERGY_CURVE = {
    "Intro": "Hoch",
    "Build-up": "Normal",
    "Verse": "Normal",
    "PreChorus": "Hoch",
    "Chorus": "Maximal",
    "Bridge": "Normal",
    "Drop": "Niedrig",
    "Outro": "Hoch"
}


# ── Dateipfade ────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT       = os.path.dirname(BASE_DIR)
SOUNDFONT_PFAD  = os.path.join(BASE_DIR, "soundfont.sf2")
VST3_SYNTH_PFAD = r"C:\Program Files\Common Files\VST3\Surge XT.vst3"
VST3_DRUMS_PFAD = r"C:\Program Files\Common Files\VST3\Sitala.vst3"

# ── Deine Daten ───────────────────────────────────────────────────────────────
# Songs, Einstellungen, Vorlagen, Vorbilder, Motive und Protokolle liegen in einem eigenen Ordner, den Updates nie
# anfassen: Standard Dokumente\Vloid Songs. Steht in datenordner.txt (im Programmordner) "programmordner", bleiben sie
# wie früher in vocaloid_generator; ein anderer Ordner dort geht auch. Die Umgebungsvariable VLOID_DATEN geht vor.
DATA_ENV        = "VLOID_DATEN"
DATA_CHOICE     = os.path.join(REPO_ROOT, "datenordner.txt")
PROGRAM_FOLDER  = "programmordner"
DATA_NAME       = "Vloid Songs"


def documents_dir() -> str:
    """Der Ordner Dokumente, auch wenn Windows ihn verschoben hat (z. B. nach OneDrive)."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:   # 5 = Dokumente
                return buf.value
        except Exception:  # noqa: BLE001 – dann der übliche Ort
            pass
    home = os.path.expanduser("~")
    documents = os.path.join(home, "Documents")
    return documents if os.path.isdir(documents) else home


def default_data_dir() -> str:
    return os.path.join(documents_dir(), DATA_NAME)


def data_choice() -> str:
    """Was in datenordner.txt steht: "programmordner", ein Ordner oder "" (Standard)."""
    try:
        with open(DATA_CHOICE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def data_dir() -> str:
    if os.environ.get(DATA_ENV):
        return os.path.abspath(os.environ[DATA_ENV])
    choice = data_choice()
    if choice.lower() == PROGRAM_FOLDER:
        return BASE_DIR
    return os.path.abspath(choice) if choice else default_data_dir()


DATA_DIR        = data_dir()
OUTPUT_ORDNER   = os.path.join(DATA_DIR, "Songs")
LOG_DIR         = os.path.join(DATA_DIR, "Protokolle")

# ── VOCAL ENGINE ───────────────────────────────────────────────────────────────
# Standard: der Ordner, den setup_neutrino.py im Projektordner anlegt
NEUTRINO_PFAD       = os.path.join(REPO_ROOT, "NEUTRINO-windows-v3.1", "NEUTRINO")
NEUTRINO_MODEL      = "MERROW"
NEUTRINO_MODEL_PFAD = os.path.join(NEUTRINO_PFAD, "model", NEUTRINO_MODEL)

