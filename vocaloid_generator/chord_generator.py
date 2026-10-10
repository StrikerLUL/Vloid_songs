# chord_generator.py – Vocaloid/J-Pop Akkord-Engine v3.0
# Reichere Harmonik: 9ths, 11ths, komplexe Basslinien, Arp-Patterns
import pretty_midi
import random
from config import KEY, MODE, CHORD_STYLE

# ── Akkord-Definitionen ────────────────────────────────────────────────────────
_CHORD_INTERVALS = {
    "":      [0, 4, 7],
    "m":     [0, 3, 7],
    "7":     [0, 4, 7, 10],
    "maj7":  [0, 4, 7, 11],
    "m7":    [0, 3, 7, 10],
    "m9":    [0, 3, 7, 10, 14],
    "maj9":  [0, 4, 7, 11, 14],
    "9":     [0, 4, 7, 10, 14],
    "dim":   [0, 3, 6],
    "dim7":  [0, 3, 6, 9],
    "aug":   [0, 4, 8],
    "sus2":  [0, 2, 7],
    "sus4":  [0, 5, 7],
    "add9":  [0, 4, 7, 14],
    "madd9": [0, 3, 7, 14],
    "6":     [0, 4, 7, 9],
    "m6":    [0, 3, 7, 9],
    "11":    [0, 4, 7, 10, 14, 17],
    "m11":   [0, 3, 7, 10, 14, 17],
    "6/9":   [0, 4, 7, 9, 14],
}

_NOTE_OFFSETS = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
}
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def force_into_scale(pitch: int, key: str = KEY, mode: str = MODE) -> int:
    scale_intervals = {
        "major":       [0, 2, 4, 5, 7, 9, 11],
        "minor":       [0, 2, 3, 5, 7, 8, 10],
        "dorian":      [0, 2, 3, 5, 7, 9, 10],
        "phrygian":    [0, 1, 3, 5, 7, 8, 10],
        "penta_minor": [0, 3, 5, 7, 10],
        "penta_major": [0, 2, 4, 7, 9],
    }
    intervals = scale_intervals.get(mode, scale_intervals["minor"])
    root_offset = _NOTE_OFFSETS.get(key, 0)
    valid_classes = {(root_offset + interval) % 12 for interval in intervals}
    
    if (pitch % 12) in valid_classes:
        return pitch
        
    for diff in range(1, 12):
        if ((pitch - diff) % 12) in valid_classes:
            return pitch - diff
        if ((pitch + diff) % 12) in valid_classes:
            return pitch + diff
    return pitch

def baue_akkord_pitches(root_name: str, chord_type: str, base_octave: int = 4) -> list:
    import config
    root_offset = _NOTE_OFFSETS.get(root_name, 0)
    base_midi   = 12 * (base_octave + 1) + root_offset
    intervals   = _CHORD_INTERVALS.get(chord_type, [0, 4, 7])
    pitches     = [base_midi + i for i in intervals]
    
    if getattr(config, "STRICT_SCALE_LOCKING", False):
        pitches = [force_into_scale(p, KEY, MODE) for p in pitches]
    return pitches

# ── Markov-Chain Akkord-Engine ────────────────────────────────────────────────
class MarkovChordGenerator:
    """Generiert Akkord-Loops (4 oder 8 Takte) basierend auf Markov-Ketten-Wahrscheinlichkeiten."""
    
    # Übergangsmatrix für Moll (Minor)
    TRANSITIONS_MINOR = {
        "i_m7":      [("bVI_maj7", 0.40), ("iv_m7", 0.30), ("v_m7", 0.15), ("bVII_7", 0.15)],
        "bVI_maj7":  [("bVII_7", 0.60), ("v_m7", 0.20), ("ii_dim", 0.20)],
        "bVII_7":    [("i_m7", 0.50), ("v_m7", 0.30), ("bIII_maj7", 0.20)],
        "iv_m7":     [("v_m7", 0.50), ("bVII_7", 0.30), ("bVI_maj7", 0.20)],
        "v_m7":      [("i_m7", 0.80), ("bVI_maj7", 0.20)],
        "bIII_maj7": [("iv_m7", 0.50), ("bVI_maj7", 0.50)],
        "ii_dim":    [("v_m7", 0.90), ("bVI_maj7", 0.10)]
    }

    # Übergangsmatrix für Dur (Major)
    TRANSITIONS_MAJOR = {
        "I_maj9":    [("IV_maj9", 0.40), ("vi_m7", 0.30), ("V_7", 0.20), ("ii_m7", 0.10)],
        "IV_maj9":   [("V_7", 0.50), ("iii_m7", 0.30), ("I_maj9", 0.10), ("V_sus4", 0.10)],
        "V_7":       [("I_maj9", 0.60), ("vi_m7", 0.30), ("iii_m7", 0.10)],
        "V_sus4":    [("V_7", 0.90), ("I_maj9", 0.10)],
        "vi_m7":     [("IV_maj9", 0.40), ("ii_m7", 0.40), ("V_7", 0.20)],
        "ii_m7":     [("V_7", 0.70), ("V_sus4", 0.20), ("vii_dim", 0.10)],
        "iii_m7":    [("vi_m7", 0.80), ("IV_maj9", 0.20)],
        "vii_dim":   [("I_maj9", 0.80), ("vi_m7", 0.20)]
    }
    
    # Roman Numerals zu Halbtönen (0-11)
    ROMAN_TO_DEGREE = {
        "I": 0, "bII": 1, "ii": 2, "bIII": 3, "iii": 4, 
        "IV": 5, "v": 7, "V": 7, "bVI": 8, "vi": 9, "bVII": 10, "vii": 11,
        "i": 0, "iv": 5
    }

    @classmethod
    def generiere_loop(cls, key: str, mode: str, section_type: str, length: int = 4, style: str = "J-Pop Energy") -> list:
        # Start-Akkorde je nach Section
        if "j-pop" in style.lower() and section_type in ("Chorus", "PreChorus"):
            if mode == "minor":
                # Equivalent minor scale degrees: VI -> VII -> v -> i
                loop = ["bVI_maj7", "bVII_7", "v_m7", "i_m7"]
            else:
                loop = ["IV_maj7", "V_7", "iii_m7", "vi_m7"]
        else:
            if mode == "minor":
                transitions = cls.TRANSITIONS_MINOR
                if section_type in ("Chorus", "Build-up"):
                    current = "bVI_maj7" # Epischer Start
                elif section_type == "PreChorus":
                    current = "iv_m7"
                else:
                    current = "i_m7"
            else:
                transitions = cls.TRANSITIONS_MAJOR
                if section_type in ("Chorus", "Build-up"):
                    current = "IV_maj9" # Royal Road Start
                elif section_type == "PreChorus":
                    current = "ii_m7"
                else:
                    current = "I_maj9"

            # Markov-Generierung
            loop = [current]
            for _ in range(length - 1):
                possible_next = transitions.get(current, transitions[list(transitions.keys())[0]])
                chords, weights = zip(*possible_next)
                # Wähle nächsten Akkord probabilistisch
                current = random.choices(chords, weights=weights, k=1)[0]
                loop.append(current)
            
        # Parse Roman Numerals to (Note, ChordType)
        root_offset = _NOTE_OFFSETS.get(key, 0)
        parsed_loop = []
        for chord_str in loop:
            parts = chord_str.split("_")
            roman = parts[0]
            ctype = parts[1] if len(parts) > 1 else ""
            
            degree = cls.ROMAN_TO_DEGREE.get(roman, 0)
            note_idx = (root_offset + degree) % 12
            note_name = _NOTE_NAMES[note_idx]
            parsed_loop.append((note_name, ctype))
            
        return parsed_loop

# ── Named Chord Progressions with Functional Harmony ──────────────────────────
NAMED_PROGRESSIONS = {
    "dramatic minor": ["bVI_maj7", "bVII_7", "i_m7", "v_m7"],          # Kagerou Daze style
    "royal road j-pop": ["IV_maj7", "V_7", "iii_m7", "vi_m7"],         # Tell Your World style
    "rising pre-chorus": ["IV_maj7", "V_7", "vi_m7", "V_sus4"],       # Viva Happy style
    "emotional descend": ["vi_m7", "V_7", "IV_maj7", "iii_m7"],       # Melt style
    "bittersweet": ["IV_maj7", "V_7", "I_maj7", "vi_m7"],             # Odds & Ends style
    "wagyoku/japanese-modal": ["i_m7", "bVI_maj7", "bVII_7", "i_m7"],  # Senbonzakura style
    "j-rock minor": ["bVI_maj7", "bVII_7", "V_7", "i_m7"]
}

def resolve_roman_progression(progression_chords: list, key: str) -> list:
    """Resolves a list of Roman numeral chords to (Note, ChordType) tuples."""
    root_offset = _NOTE_OFFSETS.get(key, 0)
    parsed_loop = []
    for chord_str in progression_chords:
        parts = chord_str.split("_")
        roman = parts[0]
        ctype = parts[1] if len(parts) > 1 else ""
        
        degree = MarkovChordGenerator.ROMAN_TO_DEGREE.get(roman, 0)
        note_idx = (root_offset + degree) % 12
        note_name = _NOTE_NAMES[note_idx]
        parsed_loop.append((note_name, ctype))
    return parsed_loop

def get_progression_roots(progression: list) -> list:
    """Returns the list of root note names from a resolved progression."""
    return [root for root, _ in progression]

def get_progression_roman_roots(progression_name: str) -> list:
    """Returns the list of Roman numeral roots for a named progression."""
    prog = NAMED_PROGRESSIONS.get(progression_name.lower().strip())
    if not prog:
        return []
    return [chord.split("_")[0] for chord in prog]

def get_progression(section_type: str, key: str = KEY, mode: str = MODE, style: str = "J-Pop Energy") -> list:
    # 1. Check if style matches a named progression (case-insensitive)
    normalized_style = style.lower().strip()
    if normalized_style in NAMED_PROGRESSIONS:
        return resolve_roman_progression(NAMED_PROGRESSIONS[normalized_style], key)
        
    # 2. Fallback to Markov chain generation
    return MarkovChordGenerator.generiere_loop(key, mode, section_type, length=4, style=style)


# ── Bass-Linie Generator ───────────────────────────────────────────────────────
def generiere_basslinie(root_midi, chord_pitches, section_type, ts, viertel, achtel, takt_idx, style="J-Pop Energy"):
    """Erzeugt eine interessante, melodische Basslinie (nicht nur Root)."""
    notes = []
    bass_root  = root_midi - 12
    bass_fifth = root_midi - 12 + 7  # Quinte im Bass
    bass_oct   = root_midi          # Grundton eine Oktave höher

    if style in ("Kawaii Chiptune", "Chiptune J-Pop"):
        # Energetischer, extrem synkopierter "Donk"-Bass (Vocaloid/Bitpop typisch):
        # Spielt stark auf Off-Beats mit knackigem Stakkato (kürzere Notenlängen)
        if section_type in ("Chorus", "Build-up"):
            pattern = [
                (0,            bass_root,  122),
                (1.5 * achtel, bass_root,  105),
                (3 * achtel,   bass_oct,   116),
                (4 * achtel,   bass_root,  120),
                (5.5 * achtel, bass_fifth, 110),
                (7 * achtel,   bass_oct,   118),
            ]
        elif section_type == "Verse":
            pattern = [
                (0,            bass_root,  118),
                (2 * achtel,   bass_fifth, 105),
                (4 * achtel,   bass_root,  115),
                (6 * achtel,   bass_oct,   110),
            ]
        else: # Intro, PreChorus, Bridge, Outro
            pattern = [
                (0,            bass_root,  112),
                (2 * achtel,   bass_fifth, 100),
                (4 * achtel,   bass_root,  110),
                (6 * achtel,   bass_oct,   105),
            ]
        legato = 0.62  # Kurze Ausklingzeit für knackigen "Pluck/Donk"-Sound!
    elif section_type in ("Chorus", "PreChorus"):
        # Energetischer Lauf: Root → Quinte → Oktave → Quarte
        pattern = [
            (0,         bass_root,  118),
            (1 * achtel, bass_root,  105),
            (2 * achtel, bass_fifth, 112),
            (3 * achtel, bass_root,  100),
            (4 * achtel, bass_oct,   108),
            (5 * achtel, bass_fifth, 100),
            (6 * achtel, bass_root,  112),
            (7 * achtel, bass_root - 2, 95),  # kleiner chromatischer Passing Ton
        ]
        legato = 0.82
    elif section_type == "Bridge":
        # Lyrischer Abstieg
        pattern = [
            (0,           bass_root,  105),
            (2 * achtel,  bass_root,  98),
            (4 * achtel,  bass_fifth, 102),
            (6 * achtel,  bass_fifth, 95),
        ]
        legato = 0.90
    elif section_type == "Verse":
        # Synkopierter Groove-Bass (Vocaloid-typisch)
        pattern = [
            (0,            bass_root,  112),
            (1.5 * achtel, bass_root,  95),
            (3 * achtel,   bass_fifth, 105),
            (4.5 * achtel, bass_root,  98),
            (6 * achtel,   bass_root,  108),
            (7 * achtel,   bass_root - 1, 88),
        ]
        legato = 0.83
    else:
        pattern = [
            (0,           bass_root,  100),
            (2 * achtel,  bass_fifth, 95),
            (4 * achtel,  bass_root,  100),
            (6 * achtel,  bass_root,  90),
        ]
        legato = 0.88

    for off, p, vel in pattern:
        t = ts + off
        dur = achtel * legato
        if p < 24: p = 24  # Minimum MIDI-Bass
        if p > 55: p = p - 12
        notes.append(pretty_midi.Note(
            velocity=vel + random.randint(-5, 5),
            pitch=p, start=t, end=t + dur
        ))
    return notes


# ── Piano/Stab-Pattern Generator ──────────────────────────────────────────────
def generiere_piano_stabs(pitches, section_type, ts, viertel, achtel):
    """Rhythmische Piano-Stabs mit typischen J-Pop-Offsets."""
    notes = []

    if section_type == "Chorus":
        # Aggressive synkopierte Stabs
        stab_offsets = [0.0, 1.5, 2.5, 4.0, 5.5, 7.0, 7.5]
    elif section_type == "PreChorus":
        stab_offsets = [0.0, 1.5, 3.0, 4.5, 6.0, 7.0]
    elif section_type == "Verse":
        stab_offsets = [0.0, 2.0, 4.0, 6.0]  # einfacher, ruhiger
    elif section_type == "Bridge":
        stab_offsets = [0.0, 3.0, 6.0]  # breite Stabs
    else:
        stab_offsets = [0.0, 4.0]

    for off in stab_offsets:
        t = ts + off * achtel
        if t >= ts + 4 * viertel:
            continue
        vel = random.randint(82, 102)
        # Nur die 3 wichtigsten Töne (Root, Terz, Quinte) – nicht zu voll
        for p in pitches[:3]:
            notes.append(pretty_midi.Note(
                velocity=vel,
                pitch=p,
                start=t,
                end=t + achtel * 0.68
            ))
    return notes


# ── Synth-Arp Generator ────────────────────────────────────────────────────────
def generiere_synth_arp(pitches, section_type, ts, viertel, achtel, sechzehntel, style="J-Pop Energy"):
    """Typischer Vocaloid-Synth-Arp mit interessanten Mustern."""
    notes = []
    
    is_chiptune = (style in ("Kawaii Chiptune", "Chiptune J-Pop"))
    if section_type not in ("Chorus", "PreChorus", "Build-up"):
        return notes

    if is_chiptune:
        # Ultra-schnelles, glitzerndes Chiptune-Arpeggio über 3 Oktaven
        arp_seq = pitches + [p + 12 for p in pitches] + [p + 24 for p in pitches[:2]]
        step = sechzehntel
        # Buntes retro-aktives Pattern
        pattern_map = [0, 4, 2, 6, 1, 5, 3, 7, 2, 6, 4, 8, 3, 7, 5, 9]
        for i in range(16):
            t = ts + i * step
            if t >= ts + 4 * viertel:
                break
            idx = pattern_map[i % len(pattern_map)] % len(arp_seq)
            notes.append(pretty_midi.Note(
                velocity=random.randint(85, 105),  # Präsenter im Mix
                pitch=arp_seq[idx],
                start=t,
                end=t + step * 0.72  # Schöner knackiger 8-Bit-Sound
            ))
        return notes

    # Erweitere die Arp-Sequenz über 2 Oktaven für mehr Breite
    arp_seq = pitches + [p + 12 for p in pitches[:3]]

    if section_type == "Chorus":
        step = sechzehntel
        n_steps = 16
        # Muster: auf, Sprung, runter, Sprung (interessanter als reine Treppe)
        pattern_map = {0: 0, 1: 2, 2: 1, 3: 3, 4: 0, 5: 2, 6: 4, 7: 3,
                       8: 1, 9: 3, 10: 2, 11: 4, 12: 0, 13: 1, 14: 2, 15: 3}
    else:
        step = achtel
        n_steps = 8
        pattern_map = {i: i % len(arp_seq) for i in range(8)}

    for i in range(n_steps):
        t = ts + i * step
        if t >= ts + 4 * viertel:
            break
        seq_idx = pattern_map.get(i, i) % len(arp_seq)
        p = arp_seq[seq_idx]
        notes.append(pretty_midi.Note(
            velocity=random.randint(58, 78),
            pitch=p,
            start=t,
            end=t + step * 0.62
        ))
    return notes


# ── Counter-Melody (Glockenspiel/Lead) ────────────────────────────────────────
def generiere_counter_melody(pitches, section_type, ts, viertel, achtel):
    """Eine interessante Counter-Melodie, nicht nur Akkordtöne."""
    notes = []
    gl_pitches = [p + 24 for p in pitches[:4]]  # 2 Oktaven hoch

    # Nicht-triviales Muster: jedes mal anders
    if section_type == "Chorus":
        offsets = [0, 1.5, 3.0, 4.0, 5.0, 6.5]
        vels    = [72, 62, 68, 55, 70, 60]
    elif section_type == "PreChorus":
        offsets = [0, 2.0, 4.0, 6.0]
        vels    = [65, 58, 65, 58]
    elif section_type == "Verse":
        offsets = [0, 3.0, 5.0]
        vels    = [52, 48, 52]
    else:
        offsets = [0, 4.0]
        vels    = [50, 45]

    melody_contour = [0, 2, 1, 3, 2, 1]  # Interessante melodische Kontur

    for i, (off, vel) in enumerate(zip(offsets, vels)):
        t = ts + off * achtel
        if t >= ts + 4 * viertel:
            continue
        if random.random() < (0.80 if section_type == "Chorus" else 0.55):
            p_idx = melody_contour[i % len(melody_contour)] % len(gl_pitches)
            notes.append(pretty_midi.Note(
                velocity=vel + random.randint(-6, 6),
                pitch=gl_pitches[p_idx],
                start=t,
                end=t + achtel * 0.42
            ))
    return notes


# ── Pad Generator ──────────────────────────────────────────────────────────────
def generiere_pad(pitches, section_type, ts, viertel):
    """Langer Pad-Akkord mit leichtem Swell."""
    notes = []
    pad_vel = {
        "Chorus": 58, "PreChorus": 52, "Bridge": 48,
        "Verse": 42, "Intro": 38, "Outro": 35
    }.get(section_type, 40)

    # Pad eine Oktave höher für Helligkeit, max 3 Töne
    for i, p in enumerate(pitches[:3]):
        notes.append(pretty_midi.Note(
            velocity=pad_vel + random.randint(-4, 4),
            pitch=p + 12,
            start=ts + i * 0.015,  # leicht arpeggiert
            end=ts + 4 * viertel * 0.97
        ))
    return notes


# ── Strings / Pizzicato ────────────────────────────────────────────────────────
def generiere_strings(pitches, section_type, ts, viertel, achtel):
    notes = []
    if section_type in ("Bridge", "Outro", "Intro"):
        # Breite Legato-Strings
        for p in pitches[:3]:
            notes.append(pretty_midi.Note(
                velocity=random.randint(55, 70),
                pitch=p + 12,
                start=ts,
                end=ts + 4 * viertel * 0.94
            ))
    elif section_type == "Chorus":
        # Treibende Pizzicato-Stabs
        for beat in [0, 1, 2, 3]:
            t = ts + beat * viertel
            for p in pitches[:2]:
                notes.append(pretty_midi.Note(
                    velocity=random.randint(60, 75),
                    pitch=p + 12,
                    start=t,
                    end=t + achtel * 0.55
                ))
    return notes


# ── Arcade SFX Generator ──────────────────────────────────────────────────────
def generiere_chiptune_sfx(section_type, ts, viertel, s16):
    notes = []
    s32 = s16 / 2
    
    # 1. Power-up / Coin Sound am Sektionsanfang (Build-up / Chorus)
    if section_type in ("Build-up", "Chorus"):
        start_pitch = 84  # C6 (hohe Oktave)
        for idx in range(8):
            t = ts + idx * s32
            notes.append(pretty_midi.Note(
                velocity=100 - idx * 4,
                pitch=start_pitch + idx * 2,  # Schnell aufsteigende Ganztöne
                start=t, end=t + s32 * 0.85
            ))
            
    # 2. Retro Laser Sweep am Ende des PreChorus / Intro
    elif section_type in ("PreChorus", "Intro"):
        sweep_start = ts + 3 * viertel  # Letzter Schlag
        start_pitch = 96  # C7 (sehr hoch)
        for idx in range(12):
            t = sweep_start + idx * (s32 * 0.5)
            notes.append(pretty_midi.Note(
                velocity=95 - idx * 4,
                pitch=start_pitch - idx * 3,  # Schnell abfallende Frequenzen
                start=t, end=t + (s32 * 0.4)
            ))
            
    # 3. High Pitch Sparkle / Bubble in der Mitte des Chorus
    elif section_type == "Chorus":
        sparkle_start = ts + 2 * viertel
        pitches = [88, 91, 95, 98, 100]  # E6, G6, B6, D7, E7
        for idx, p in enumerate(pitches):
            t = sparkle_start + idx * s16
            notes.append(pretty_midi.Note(
                velocity=random.randint(70, 88),
                pitch=p,
                start=t, end=t + s16 * 0.5
            ))
            
    return notes


# ── Sub-Bass Generator ────────────────────────────────────────────────────────
def generiere_sub_bass(root_midi, section_type, ts, viertel):
    """Generiert einen tiefen, tragenden Sub-Bass (Grundton in Oktave 2)."""
    notes = []
    # Sub-Bass: Oktave 2 (MIDI 24 bis 47)
    sub_pitch = root_midi - 24
    
    # Sicherstellen, dass der Sub-Bass im richtigen Bereich ist
    while sub_pitch < 24:
        sub_pitch += 12
    while sub_pitch > 43:
        sub_pitch -= 12
        
    # Sustained Noten für Chorus, PreChorus, Build-up und Verse
    if section_type in ("Chorus", "PreChorus", "Build-up", "Verse"):
        notes.append(pretty_midi.Note(
            velocity=105 if section_type in ("Chorus", "Build-up") else 85,
            pitch=sub_pitch,
            start=ts,
            end=ts + 4 * viertel * 0.98  # Fast ganz durchgezogen
        ))
    return notes


# ── Echo Arp Delay Generator ──────────────────────────────────────────────────
def generiere_echo_arp(arp_notes, sechzehntel):
    """Erzeugt ein rhythmisches Echo (Delay) für das Arpeggio."""
    echo_notes = []
    delay_time = sechzehntel * 1.5  # Dotted 16th-Note Echo
    for n in arp_notes:
        echo_notes.append(pretty_midi.Note(
            velocity=int(n.velocity * 0.55),  # Leiser
            pitch=n.pitch,
            start=n.start + delay_time,
            end=n.end + delay_time
        ))
    return echo_notes


# ── Hauptgenerator ────────────────────────────────────────────────────────────
def generiere_akkorde_sektion(
    bpm: float,
    takte: int,
    section_type: str,
    start_zeit: float,
    key: str = KEY,
    mode: str = MODE,
    style: str = "J-Pop Energy",
) -> list:
    viertel     = 60.0 / bpm
    achtel      = viertel / 2
    sechzehntel = achtel / 2
    prog        = get_progression(section_type, key, mode, style)

    is_chiptune = (style in ("Kawaii Chiptune", "Chiptune J-Pop"))

    pad_notes   = []
    piano_notes = []
    bass_notes  = []
    sub_bass_notes = []
    glock_notes = []
    str_notes   = []
    arp_notes   = []
    echo_arp_notes = []
    tamb_notes  = []
    sfx_notes   = []

    for takt in range(takte):
        root_name, chord_type = prog[takt % len(prog)]
        pitches = baue_akkord_pitches(root_name, chord_type, base_octave=4)
        ts      = start_zeit + takt * 4 * viertel

        root_offset = _NOTE_OFFSETS.get(root_name, 0)
        root_midi   = 12 * 5 + root_offset  # Oktave 4

        # 1. Pad
        pad_notes.extend(generiere_pad(pitches, section_type, ts, viertel))

        # 2. Piano Stabs
        piano_notes.extend(generiere_piano_stabs(pitches, section_type, ts, viertel, achtel))

        # 3. Bass (melodisch / plucky donk!)
        bass_notes.extend(generiere_basslinie(
            root_midi, pitches, section_type, ts, viertel, achtel, takt, style
        ))
        
        # 3.1 Sub-Bass (tief und tragend)
        if is_chiptune:
            sub_bass_notes.extend(generiere_sub_bass(root_midi, section_type, ts, viertel))

        # 4. Counter-Melody / Glockenspiel
        glock_notes.extend(generiere_counter_melody(pitches, section_type, ts, viertel, achtel))

        # 5. Strings
        str_notes.extend(generiere_strings(pitches, section_type, ts, viertel, achtel))

        # 6. Synth-Arp
        t_arp = generiere_synth_arp(pitches, section_type, ts, viertel, achtel, sechzehntel, style)
        arp_notes.extend(t_arp)
        if is_chiptune and t_arp:
            echo_arp_notes.extend(generiere_echo_arp(t_arp, sechzehntel))

        # 7. Tambourin (Off-Beat)
        if section_type in ("Chorus", "Verse", "PreChorus", "Build-up"):
            for i in range(1, 8, 2):
                t = ts + i * achtel
                tamb_notes.append(pretty_midi.Note(
                    velocity=random.randint(62, 78),
                    pitch=54,
                    start=t, end=t + sechzehntel * 0.5
                ))

        # 8. Chiptune SFX
        if is_chiptune:
            sfx_notes.extend(generiere_chiptune_sfx(section_type, ts, viertel, sechzehntel))

    # Instrumenten-Definitionen
    # Für Chiptune/Vocaloid: Synth Bass (program 39) statt elektrischem Bass!
    bass_prog = 39 if is_chiptune else 34

    result = [
        ("Background Pad",    pad_notes,   89),    # Warm Pad
        ("Bright Piano",      piano_notes,  1),    # Bright Acoustic Piano
        ("Driving Bass",      bass_notes,  bass_prog),  # electric bass / synth bass
        ("Glockenspiel",      glock_notes,  9),    # Glockenspiel
        ("String Ensemble",   str_notes,   48),    # Strings Ensemble
        ("Tambourin",         tamb_notes,   0, True),
    ]
    
    if is_chiptune and sub_bass_notes:
        result.append(("Sub-Bass", sub_bass_notes, 38)) # Synth Bass 1 (Sine/Square Sub)
    
    # Synthesizer-Arpeggiator
    if section_type in ("Chorus", "PreChorus", "Build-up"):
        result.append(("Synth Arp", arp_notes, 80))  # Synth Lead (Square wave)
        if is_chiptune and echo_arp_notes:
            result.append(("Synth Arp Echo", echo_arp_notes, 81)) # Lead 2 (Sawtooth wave) for echo layering!
        
    # Chiptune SFX Layer hinzufügen
    if is_chiptune and sfx_notes:
        result.append(("Retro SFX", sfx_notes, 80))  # Gameboy Lead als SFX Layer

    return result
