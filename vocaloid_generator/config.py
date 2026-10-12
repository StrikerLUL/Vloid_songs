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
OUTPUT_ORDNER   = os.path.join(BASE_DIR, "output")

# ── VOCAL ENGINE ───────────────────────────────────────────────────────────────
# Standard: der Ordner, den setup_neutrino.py im Projektordner anlegt
NEUTRINO_PFAD       = os.path.join(REPO_ROOT, "NEUTRINO-windows-v3.1", "NEUTRINO")
NEUTRINO_MODEL      = "MERROW"
NEUTRINO_MODEL_PFAD = os.path.join(NEUTRINO_PFAD, "model", NEUTRINO_MODEL)

# Verfügbare Engines: "NEUTRINO", "LOCAL", "OPENUTAU", "DIFFSINGER"
VOCAL_ENGINE = "NEUTRINO"
