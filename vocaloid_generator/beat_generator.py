# beat_generator.py – Vocaloid/J-Pop Drum Engine v3.0
import pretty_midi
import random
from config import SWING

KICK        = 36
SNARE       = 38
SNARE_GHOST = 40
HIHAT_CL    = 42
HIHAT_OP    = 46
HIHAT_FOOT  = 44
RIDE        = 51
CRASH       = 49
CRASH2      = 57
TOM_HI      = 48
TOM_MID     = 47
TOM_LOW     = 45
TOM_FLOOR   = 43
CLAP        = 39
SHAKER      = 70
COWBELL     = 56

def sd(idx, s16, swing=SWING):
    if swing > 0.01 and idx % 2 == 1:
        return s16 * swing * 0.38
    return 0.0


def _fill_standard(ts, s16, viertel, notes, is_chorus):
    """Klassischer 8-Noten Tom-Fill."""
    fill_map = {8: TOM_HI, 9: TOM_HI, 10: TOM_MID, 11: TOM_MID,
                12: TOM_LOW, 13: TOM_LOW, 14: TOM_FLOOR, 15: TOM_FLOOR}
    for i in range(8, 16):
        t = ts + i * s16
        tom = fill_map.get(i, TOM_MID)
        notes.append(pretty_midi.Note(velocity=112 + random.randint(-5, 5), pitch=tom, start=t, end=t + s16))
        if i in [8, 10, 12, 14]:
            notes.append(pretty_midi.Note(velocity=108, pitch=KICK, start=t, end=t + s16))
    notes.append(pretty_midi.Note(velocity=125, pitch=CRASH if is_chorus else CRASH2,
                                   start=ts + 15 * s16, end=ts + 15 * s16 + viertel))

def _fill_snare_roll(ts, s16, viertel, notes, is_chorus=False):
    """Snare-Roll Fill (treibend)."""
    for i in range(8, 16):
        t = ts + i * s16
        vel = 80 + (i - 8) * 6
        notes.append(pretty_midi.Note(velocity=min(vel, 127), pitch=SNARE, start=t, end=t + s16 * 0.9))
    notes.append(pretty_midi.Note(velocity=122, pitch=CRASH, start=ts + 15 * s16, end=ts + 15 * s16 + viertel))

def _fill_sixteenth_kicks(ts, s16, viertel, notes, is_chorus=False):
    """Rapid-Kick Fill."""
    for i in range(8, 16):
        t = ts + i * s16
        vel = 105 if i % 2 == 0 else 90
        notes.append(pretty_midi.Note(velocity=vel, pitch=KICK, start=t, end=t + s16 * 0.85))
    notes.append(pretty_midi.Note(velocity=118, pitch=CRASH2, start=ts + 15 * s16, end=ts + 15 * s16 + viertel))

# ── Markov-Chain Drum-Engine ──────────────────────────────────────────────────
class MarkovDrumGenerator:
    """Generiert intelligente Rhythmus-Patterns (1 Takt = 16 Steps) via Markov-Ketten."""
    
    # Typische J-Pop / Kawaii Kick-Patterns (16 Steps)
    # A: 4-on-the-floor
    # B: Synkopiert (Offbeat 8tel)
    # C: Kawaii Future Core (Doppel-Kicks)
    # D: Halftime/Break
    KICK_PATTERNS = {
        "A": [1,0,0,0, 1,0,0,0, 1,0,0,0, 1,0,0,0],
        "B": [1,0,0,0, 0,0,1,0, 1,0,0,0, 0,0,1,0],
        "C": [1,0,0,0, 1,0,1,0, 1,0,0,0, 1,0,1,0],
        "D": [1,0,0,0, 0,0,0,0, 1,0,0,0, 0,0,0,0],
    }
    
    # Transitions für Kick-Patterns je nach Energie-Level
    # Chorus: Treibend, wechselt zwischen 4-on-the-floor und Synkopen
    TRANS_KICK_CHORUS = {
        "A": [("A", 0.50), ("C", 0.30), ("B", 0.20)],
        "B": [("A", 0.70), ("C", 0.30)],
        "C": [("A", 0.60), ("B", 0.40)],
        "D": [("A", 1.00)]
    }
    
    # Verse: Eher Halftime oder synkopiert, weniger Four-on-the-Floor
    TRANS_KICK_VERSE = {
        "A": [("B", 0.60), ("D", 0.40)],
        "B": [("B", 0.50), ("D", 0.30), ("A", 0.20)],
        "C": [("B", 0.80), ("D", 0.20)],
        "D": [("B", 0.70), ("A", 0.30)],
    }
    
    # Hi-Hat Patterns
    # A: Geschlossene Achtel
    # B: Geschlossene 16tel (treibend)
    # C: Offbeat-Open Hats (Dance/Kawaii)
    HAT_PATTERNS = {
        "A": [(HIHAT_CL, 85), (None, 0)] * 8, # 8tel
        "B": [(HIHAT_CL, 75)] * 16,           # 16tel
        "C": [(HIHAT_CL, 60), (None, 0), (HIHAT_OP, 110), (None, 0)] * 4, # Offbeats
    }
    
    TRANS_HAT_CHORUS = {
        "A": [("C", 0.80), ("B", 0.20)],
        "B": [("C", 0.60), ("A", 0.40)],
        "C": [("C", 0.70), ("B", 0.30)],
    }
    TRANS_HAT_VERSE = {
        "A": [("A", 0.80), ("B", 0.20)],
        "B": [("A", 0.70), ("C", 0.30)],
        "C": [("A", 0.90), ("B", 0.10)],
    }

    @classmethod
    def generate_rhythm_loop(cls, takte: int, section_type: str, is_chiptune: bool):
        loop_kicks = []
        loop_hats = []
        
        # Initiale States
        is_chorus = section_type in ("Chorus", "PreChorus", "Build-up")
        curr_kick = "A" if is_chorus else "D"
        curr_hat = "C" if is_chorus else "A"
        
        kick_trans = cls.TRANS_KICK_CHORUS if is_chorus else cls.TRANS_KICK_VERSE
        hat_trans = cls.TRANS_HAT_CHORUS if is_chorus else cls.TRANS_HAT_VERSE
        
        for _ in range(takte):
            # Kick Pattern
            loop_kicks.append(cls.KICK_PATTERNS[curr_kick])
            next_kicks, w_kicks = zip(*kick_trans.get(curr_kick, [("A", 1.0)]))
            curr_kick = random.choices(next_kicks, weights=w_kicks, k=1)[0]
            
            # Hat Pattern
            loop_hats.append(cls.HAT_PATTERNS[curr_hat])
            next_hats, w_hats = zip(*hat_trans.get(curr_hat, [("A", 1.0)]))
            curr_hat = random.choices(next_hats, weights=w_hats, k=1)[0]
            
        return loop_kicks, loop_hats


def generiere_beat_sektion(bpm, takte, section_type, start_zeit, swing=SWING, style="J-Pop Energy", transition_to_chorus=False):
    s16     = 60.0 / bpm / 4
    viertel = 60.0 / bpm
    notes   = []

    is_chiptune = (style in ("Kawaii Chiptune", "Chiptune J-Pop"))
    is_chorus  = section_type in ("Chorus", "PreChorus", "Build-up")
    is_verse   = section_type in ("Verse", "Bridge")
    is_intro   = section_type == "Intro"
    is_outro   = section_type == "Outro"
    is_drop    = section_type == "Drop"

    # Markov Rhythmus generieren
    loop_kicks, loop_hats = MarkovDrumGenerator.generate_rhythm_loop(takte, section_type, is_chiptune)

    # Crash am Sektionsanfang
    if section_type in ("Chorus", "Verse", "PreChorus", "Bridge", "Build-up"):
        # Bei Chiptune-Drop im Build-up: massiver Crash!
        vel = 127 if (is_chorus or is_chiptune) else 112
        notes.append(pretty_midi.Note(velocity=vel, pitch=CRASH,
                                       start=start_zeit, end=start_zeit + viertel))

    # Spezifische Fills
    fill_styles = [_fill_standard, _fill_snare_roll, _fill_sixteenth_kicks]

    for takt in range(takte):
        ts       = start_zeit + takt * 4 * viertel
        is_last  = (takt == takte - 1)
        takt_4   = takt % 4
        
        # Lade aktuelles Takt-Pattern aus Markov-Kette
        curr_kick_pat = loop_kicks[takt]
        curr_hat_pat = loop_hats[takt]

        # ── Drop Section (Kick-only) ──
        if is_drop:
            for i in range(16):
                t   = ts + i * s16 + sd(i, s16, swing)
                end = t + s16
                if curr_kick_pat[i]:
                    notes.append(pretty_midi.Note(velocity=115 + random.randint(-5, 5), pitch=KICK, start=t, end=end))
            continue

        # ── Chiptune-spezifische Drum-Struktur ───────────────────────────────
        if is_chiptune:
            # 1. INTRO: Keine schweren Drums (nur ein Crash/Splash-Ausklingen ganz am Anfang, sonst Stille)
            if is_intro:
                if takt == 0:
                    # Leises Windchime- oder Crash-Ausklingen
                    notes.append(pretty_midi.Note(velocity=68, pitch=CRASH2, start=ts, end=ts + viertel * 2))
                if is_last:
                    # Snare-Roll am Ende des Intros zum Drop hin
                    for i in range(12, 16):
                        t = ts + i * s16
                        notes.append(pretty_midi.Note(velocity=60 + (i-12)*15, pitch=SNARE, start=t, end=t + s16 * 0.9))
                continue

            # 2. FILL im letzten Takt der antreibenden Sektionen
            if is_last and transition_to_chorus:
                # Schneller Snare Roll & Tom Fill für den Chiptune-Vibe
                _fill_snare_roll(ts, s16, viertel, notes, is_chorus=True)
                continue

            for i in range(16):
                t   = ts + i * s16 + sd(i, s16, swing)
                end = t + s16

                # ── KICK (Via Markov) ──────────────────────────────────────
                if curr_kick_pat[i]:
                    notes.append(pretty_midi.Note(velocity=115 + random.randint(-5, 5), pitch=KICK, start=t, end=end))

                # ── SNARE & CLAPS (Chiptune-Stil) ──────────────────────────────
                if section_type in ("Build-up", "Chorus", "Verse", "PreChorus"):
                    # Snares auf den Schlägen 2 und 4 (d.h. 16tel-Schritte 4 und 12)
                    if i in [4, 12]:
                        notes.append(pretty_midi.Note(velocity=124, pitch=SNARE, start=t, end=end))
                        # Layered Claps für den typischen Kawaii Future Core Sound!
                        notes.append(pretty_midi.Note(velocity=118, pitch=CLAP, start=t + 0.003, end=end))
                    # Verspielte Ghost-Snares für extra Groove
                    if i in [2, 6, 10, 14] and random.random() < 0.35:
                        notes.append(pretty_midi.Note(velocity=random.randint(20, 40), pitch=SNARE_GHOST, start=t, end=end))
                elif section_type == "Bridge":
                    # Half-Time Snare (nur auf Schlag 3, d.h. Schritt 8)
                    if i == 8:
                        notes.append(pretty_midi.Note(velocity=110, pitch=SNARE, start=t, end=end))
                        notes.append(pretty_midi.Note(velocity=95, pitch=CLAP, start=t + 0.003, end=end))
                elif is_outro:
                    # Abruptes Ende im Outro (letzter Takt endet schlagartig auf dem ersten Beat)
                    if is_last and i >= 4:
                        continue
                    if i in [4, 12]:
                        notes.append(pretty_midi.Note(velocity=115, pitch=SNARE, start=t, end=end))

                # ── HI-HAT & PERCUSSION (Via Markov) ──────────────────────────
                hat_pitch, hat_vel = curr_hat_pat[i]
                if hat_pitch:
                    # Bei Chiptune-Chorus evtl ein wenig Shaker drüber
                    notes.append(pretty_midi.Note(velocity=hat_vel, pitch=hat_pitch, start=t, end=end))
                    
                    if is_chorus and i % 4 == 2 and random.random() < 0.4:
                        notes.append(pretty_midi.Note(velocity=75, pitch=COWBELL, start=t, end=end))
                    if is_chorus and i % 2 == 1:
                        notes.append(pretty_midi.Note(velocity=70, pitch=SHAKER, start=t, end=end))

            continue

        # ── Standard J-Pop Rhythmus ───────────────────────────────
        if is_last and transition_to_chorus:
            fill_fn = random.choice(fill_styles)
            # Erste 8 16tel via Markov
            for i in range(8):
                t   = ts + i * s16 + sd(i, s16, swing)
                end = t + s16
                
                # Kick
                if curr_kick_pat[i]:
                    notes.append(pretty_midi.Note(velocity=115 + random.randint(-5, 5), pitch=KICK, start=t, end=end))
                
                # Snare
                if i == 4:
                    notes.append(pretty_midi.Note(velocity=122 if is_chorus else 115, pitch=SNARE, start=t, end=end))
                
                # Hat
                hat_pitch, hat_vel = curr_hat_pat[i]
                if hat_pitch:
                    notes.append(pretty_midi.Note(velocity=hat_vel, pitch=hat_pitch, start=t, end=end))
            
            fill_fn(ts, s16, viertel, notes, is_chorus)
            continue

        for i in range(16):
            t   = ts + i * s16 + sd(i, s16, swing)
            end = t + s16

            # Hi-Hat-Roll vor Taktgrenze im Chorus (letzten 2 16tel)
            if i in [14, 15] and is_chorus:
                notes.append(pretty_midi.Note(
                    velocity=random.randint(80, 95), pitch=HIHAT_CL, start=t, end=end))
                continue

            # ── KICK (Via Markov) ────────────────────────────────────────
            if curr_kick_pat[i]:
                # Extra Groove bei Standard-Pop
                vel = 120 + random.randint(-4, 4) if is_chorus else 110 + random.randint(-4, 4)
                notes.append(pretty_midi.Note(velocity=vel, pitch=KICK, start=t, end=end))

            # ── SNARE ───────────────────────────────────────────────────────
            if i in [4, 12]:
                vel = 124 if is_chorus else 115
                notes.append(pretty_midi.Note(velocity=vel, pitch=SNARE, start=t, end=end))
            # Ghost-Snares
            ghost_prob = 0.42 if is_chorus else 0.25
            if i in [2, 6, 10, 14] and random.random() < ghost_prob:
                notes.append(pretty_midi.Note(
                    velocity=random.randint(20, 40), pitch=SNARE_GHOST, start=t, end=end))
            # Clap auf 2+4 im Chorus
            if i in [4, 12] and is_chorus:
                if random.random() < 0.70:
                    notes.append(pretty_midi.Note(
                        velocity=random.randint(90, 105), pitch=CLAP, start=t + 0.002, end=end))

            # ── HI-HAT / RIDE (Via Markov) ───────────────────────────────
            hat_pitch, hat_vel = curr_hat_pat[i]
            if is_verse or is_intro or is_outro:
                # Ride – offener, breiter Sound in ruhigen Passagen anstelle von Hat
                if i % 2 == 0:
                    notes.append(pretty_midi.Note(
                        velocity=random.randint(72, 85), pitch=RIDE, start=t, end=end))
                elif random.random() < 0.18:
                    notes.append(pretty_midi.Note(
                        velocity=random.randint(52, 62), pitch=HIHAT_CL, start=t, end=end))
            else:
                if hat_pitch:
                    # Varianz in der Velocity hinzufügen
                    v = max(0, min(127, hat_vel + random.randint(-8, 8)))
                    # Open hat leicht verlängern
                    end_hat = t + s16 * 1.5 if hat_pitch == HIHAT_OP else end
                    notes.append(pretty_midi.Note(velocity=v, pitch=hat_pitch, start=t, end=end_hat))

            # ── FOOT Hi-Hat ─────────────────────────────────────────────────
            if i in [6, 14] and not is_last:
                notes.append(pretty_midi.Note(
                    velocity=random.randint(52, 65), pitch=HIHAT_FOOT, start=t, end=end))

            # ── SHAKER (Chorus-Extra-Groove) ────────────────────────────────
            if is_chorus and i % 4 == 2:
                notes.append(pretty_midi.Note(
                    velocity=random.randint(55, 70), pitch=SHAKER, start=t, end=end))

    # Apply crescendo for PreChorus across bars
    if section_type == "PreChorus" and takte > 1:
        for note in notes:
            takt_idx = int((note.start - start_zeit) / (4 * viertel))
            takt_idx = max(0, min(takte - 1, takt_idx))
            crescendo_factor = 0.75 + 0.25 * (takt_idx / (takte - 1))
            note.velocity = max(1, min(127, int(note.velocity * crescendo_factor)))

    return notes
