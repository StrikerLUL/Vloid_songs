# config.py – Zentrale Einstellungen für den gesamten Generator (Roki Style)
import os

# ── Tempo & Takt ──────────────────────────────────────────────────────────────
BPM = 150                          # Tempo (Roki: 150 BPM)
TAKT = 4                           # 4/4-Takt

# ── Tonart & Skala ────────────────────────────────────────────────────────────
KEY   = "B"                        # Grundton: B (Roki is in B minor)
MODE  = "minor"                    # Skala: minor (Natürliches Moll)
STYLE = "Rock"                     # Genre: J-Rock ("Rock" maps to rock arrangement patterns)
STRICT_SCALE_LOCKING = True        # Scale locking active for strict key compliance

# ── Akkord-Stil ───────────────────────────────────────────────────────────────
# Maps to "dramatic minor" progression in chord_generator.py (VI - VII - i - v)
CHORD_STYLE = "dramatic minor"

# ── Song-Struktur ─────────────────────────────────────────────────────────────
# Matches 'Roki' structure
SONG_STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]

SECTION_CONFIG = {
    "Intro":     {"bars": 8,  "has_vocals": False},
    "Build-up":  {"bars": 4,  "has_vocals": False},
    "Verse":     {"bars": 16, "has_vocals": True},
    "PreChorus": {"bars": 8,  "has_vocals": True},
    "Chorus":    {"bars": 16, "has_vocals": True},
    "Bridge":    {"bars": 12, "has_vocals": True},
    "Drop":      {"bars": 2,  "has_vocals": False},
    "Outro":     {"bars": 8,  "has_vocals": False},
}

# ── Vocals / Synthesizer ──────────────────────────────────────────────────────
VOCAL_SPRACHE   = "japanese"
VOCAL_MAX_PITCH = 78               # F#5 - Kagamine Rin's peak vocal range in Roki
VOCAL_MIN_PITCH = 59               # B3  - Floor of main vocal melody
VOCAL_MIX_LEVEL = 0.25             # High energy vocal presence

VOCAL_SHIMMER   = True             # Chorus shimmer active
VOCAL_BREATHINESS = 0.060          # Breathiness increased for rock sighs / shouts
VOCAL_VIBRATO_RATE = 6.0           # Hz (Faster, typical J-Rock vibrato)
VOCAL_VIBRATO_DEPTH = 0.022        # Semitones (Deeper vibrato for power notes)

# ── Swing ─────────────────────────────────────────────────────────────────────
SWING = 0.00                       # Straight 8-beat rock feel (0.0 = no shuffle)

# ── Lyrics (Natural Japanese, grammatically correct and phonetically natural) ──
SONG_TEXT_VERSE     = "画面の隅で呟いた夜に誰にも届かない歌を書いた"
SONG_TEXT_PRECHORUS = "ボイストラック再生して溜め息ひとつだけどまだ終われない"
SONG_TEXT_CHORUS    = "響けよロックンロール叫べ今すぐ僕らの声を掻き鳴らせ"
SONG_TEXT_BRIDGE    = "例え世界がそっぽを向いてもこの熱は消せやしないから"

# Internal mapping to translate natural Kanji/Kana lyrics into space-separated kana syllables
SONG_TEXT_KANA_MAP = {
    SONG_TEXT_VERSE:     "が め ん の す み で つ ぶ や い た よ る に だ れ に も と ど か な い う た を か い た",
    SONG_TEXT_PRECHORUS: "ぼ い す と ら っ く さ い せ い し て た め い き ひ と つ だ け ど ま だ お わ れ な い",
    SONG_TEXT_CHORUS:    "ひ び け よ ろ っ く ん ろ お る さ け べ い ま す ぐ ぼ く ら の こ え を か き な ら せ",
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
SOUNDFONT_PFAD  = os.path.join(BASE_DIR, "soundfont.sf2")
VST3_SYNTH_PFAD = r"C:\Program Files\Common Files\VST3\Surge XT.vst3"
VST3_DRUMS_PFAD = r"C:\Program Files\Common Files\VST3\Sitala.vst3"
OUTPUT_ORDNER   = os.path.join(BASE_DIR, "output")

# ── VOCAL ENGINE ───────────────────────────────────────────────────────────────
NEUTRINO_PFAD       = r"C:\Users\cilli\OneDrive\Desktop\vocaloid_musik\NEUTRINO-windows-v3.1\NEUTRINO"
NEUTRINO_MODEL      = "MERROW"
NEUTRINO_MODEL_PFAD = os.path.join(NEUTRINO_PFAD, "model", NEUTRINO_MODEL)

# Available Engines: "NEUTRINO", "LOCAL", "OPENUTAU", "DIFFSINGER"
VOCAL_ENGINE = "NEUTRINO"
