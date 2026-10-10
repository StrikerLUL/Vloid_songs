# melody_generator.py – Vocaloid/J-Pop Melodie-Engine v3.0
# Echte Vocaloid-Typik: Sprünge, Synkopen, Chromatik, Pitch-Bends, Hooks
import pretty_midi
import random
import numpy as np
from config import VOCAL_MAX_PITCH, VOCAL_MIN_PITCH, KEY, MODE, SWING

# ── Skalenaufbau ───────────────────────────────────────────────────────────────
_SCALE_INTERVALS = {
    "major":       [0, 2, 4, 5, 7, 9, 11],
    "minor":       [0, 2, 3, 5, 7, 8, 10],
    "dorian":      [0, 2, 3, 5, 7, 9, 10],
    "phrygian":    [0, 1, 3, 5, 7, 8, 10],
    "penta_minor": [0, 3, 5, 7, 10],
    "penta_major": [0, 2, 4, 7, 9],
    "blues_minor": [0, 3, 5, 6, 7, 10],
}

_KEY_OFFSETS = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11
}

def baue_skala(key: str, mode: str, lo: int = 36, hi: int = 96) -> list:
    root = _KEY_OFFSETS.get(key, 9)
    intervals = _SCALE_INTERVALS.get(mode, _SCALE_INTERVALS["minor"])
    return [m for m in range(lo, hi + 1) if (m - root) % 12 in intervals]

def baue_pentatonik(key: str, mode: str) -> list:
    pm = "penta_minor" if mode in ("minor", "dorian", "phrygian") else "penta_major"
    return baue_skala(key, pm, 36, 96)

_SKALA      = baue_skala(KEY, MODE)
_PENTATONIK = baue_pentatonik(KEY, MODE)

def get_skala(section_type: str, key: str = KEY, mode: str = MODE) -> list:
    if section_type in ("Chorus", "Bridge"):
        return baue_pentatonik(key, mode)
    return baue_skala(key, mode)

def naechster_idx(skala, pitch):
    return min(range(len(skala)), key=lambda i: abs(skala[i] - pitch))

def clamp_idx(skala, idx):
    lo = naechster_idx(skala, VOCAL_MIN_PITCH)
    hi = naechster_idx(skala, VOCAL_MAX_PITCH)
    return max(lo, min(hi, idx))

# ── Echte Vocaloid-Rhythmus-Phrasen ────────────────────────────────────────────
# Notenwerte in Vierteln – echt musikalisch, synkopiert, mit punktierten Werten
RHYTHMEN = {
    # Klassisches Vocaloid: kurze+lange Mischung, typische Synkopen
    "vocaloid_hook":   [0.5, 0.5, 1.0, 0.5, 0.5, 0.5, 0.5, 0.25, 0.25, 1.0],
    "vocaloid_rapid":  [0.25, 0.25, 0.5, 0.25, 0.25, 0.5, 0.5, 0.25, 0.25, 0.25, 0.25, 0.5],
    # Kawaii Chiptune: extrem schnelles, treibendes Silben-Muster
    "chiptune_rapid":  [0.25, 0.25, 0.25, 0.25, 0.5, 0.25, 0.25, 0.5, 0.5, 0.25, 0.25, 0.5],
    # J-Pop Verse: größere Notenwerte, erzählend
    "jpop_verse":      [0.75, 0.5, 0.75, 1.0, 0.5, 0.75, 0.5, 1.5],
    # Pre-Chorus: aufbauend, immer enger werdend
    "prechorus":       [0.5, 0.5, 0.5, 1.0, 0.25, 0.25, 0.5, 0.5, 0.5, 1.0],
    # Chorus: ENERGIE – viele kurze, treibende Noten
    "chorus_drive":    [0.25, 0.25, 0.5, 0.5, 0.25, 0.25, 0.25, 0.25, 0.5, 0.25, 0.25, 0.5],
    "chorus_epic":     [0.5, 0.25, 0.25, 0.5, 0.5, 0.5, 0.25, 0.25, 0.25, 0.25, 1.0],
    # Bridge: breite lange Noten, emotional
    "bridge_lyric":    [1.5, 0.5, 1.0, 1.5, 0.5, 1.0, 1.5],
    # Outro: ruhig, ausklangend
    "outro_ballad":    [1.0, 1.0, 0.5, 0.5, 2.0, 0.5, 0.5, 1.5],
    # Intro: fließend
    "intro_flow":      [0.75, 0.5, 0.5, 0.75, 1.0, 0.5, 0.5, 0.5, 0.5],
}

# ── Echte Vocaloid-Melodiemuster (Skalenschritte) ─────────────────────────────
# Diese basieren auf echten Vocaloid-Songs wie Senbonzakura, Tell Your World, etc.
MOTIVE = {
    # Kleine Sprünge nach oben, dann sanft zurück – Vocaloid-Klassiker
    "vocaloid_rise":    [0, 2, 4, 3, 5, 4, 6, 5, 7, 5, 4, 3],
    # Chromatischer Schleifer aufwärts (emotionaler Aufstieg)
    "chromatic_climb":  [0, 1, 2, 3, 2, 4, 3, 5, 4, 6, 5, 4],
    # Oktavsprung – sehr typisch für Vocaloid Hooks
    "oktav_hook":       [0, 7, 6, 5, 7, 6, 4, 5, 3, 4, 2, 0],
    # Bittersüße, extrem emotionale J-Pop Hook (Love Chase Feeling!)
    "bittersweet_hook": [0, 7, 5, 4, 2, 4, 5, 7, 9, 7, 5, 4, 2, 0],
    # Sextsprung abwärts dann aufwärts (dramatisch)
    "sext_drama":       [6, 0, 2, 4, 3, 5, 4, 6, 5, 4, 3, 2],
    # Pentatonische Bewegung (eingängig, poppig)
    "penta_pop":        [0, 2, 4, 2, 4, 5, 4, 2, 4, 2, 0],
    # Frage-Motiv (endet hoch, schwebend)
    "frage":            [0, 2, 1, 3, 2, 4, 3, 2, 4, 5],
    # Antwort-Motiv (endet mit Auflösung nach unten)
    "antwort":          [5, 4, 6, 5, 4, 3, 5, 3, 2, 1, 0],
    # Schnelle Riffs (typical fast Vocaloid passages)
    "riff_schnell":     [0, 1, 2, 1, 2, 3, 2, 3, 4, 3, 4, 5, 4, 3, 2],
    # Breiter Bogen – Chorus-würdig
    "bogen_gross":      [0, 3, 5, 7, 6, 5, 7, 5, 4, 3, 2, 4, 2, 1, 0],
    # Abstieg mit kleinen Aufwärts-Gegenakzenten
    "wellen_abstieg":   [7, 6, 7, 5, 6, 4, 5, 3, 4, 2, 3, 1, 0],
    # Jetzt mit Sextsprung – starkes Hook-Feeling
    "hook_sext":        [0, 5, 4, 6, 5, 4, 3, 5, 3, 2, 4, 2, 1, 0],
    # Triller-ähnliche Bewegung
    "trill_vocaloid":   [0, 1, 0, 2, 1, 0, 3, 2, 1, 0, 2, 1, 3, 2, 4, 3],
}

# Sektion → Haupt-Motiv + Rhythmus
SEKTION_PARAM = {
    "Intro":     {"motiv": "bogen_gross",     "rhythmus": "intro_flow",    "base_frac": 0.35, "pitch_bonus": 0},
    "Verse":     {"motiv": "frage",           "rhythmus": "jpop_verse",    "base_frac": 0.30, "pitch_bonus": 0},
    "PreChorus": {"motiv": "chromatic_climb", "rhythmus": "prechorus",     "base_frac": 0.42, "pitch_bonus": 2},
    "Chorus":    {"motiv": "oktav_hook",      "rhythmus": "chorus_drive",  "base_frac": 0.58, "pitch_bonus": 4},
    "Bridge":    {"motiv": "wellen_abstieg",  "rhythmus": "bridge_lyric",  "base_frac": 0.48, "pitch_bonus": 2},
    "Outro":     {"motiv": "antwort",         "rhythmus": "outro_ballad",  "base_frac": 0.28, "pitch_bonus": 0},
}

# ── Motiv-Variationstechniken ──────────────────────────────────────────────────
def variiere_motiv(motiv: list, art: str) -> list:
    if art == "sequenz+1":   return [n + 1 for n in motiv]
    if art == "sequenz+2":   return [n + 2 for n in motiv]
    if art == "sequenz-1":   return [n - 1 for n in motiv]
    if art == "sequenz-2":   return [n - 2 for n in motiv]
    if art == "inversion":   m0 = motiv[0]; return [m0 - (n - m0) for n in motiv]
    if art == "retrograd":   return list(reversed(motiv))
    if art == "oktave_hoch": return [n + 7 for n in motiv]  # 7 Skalenschr. ≈ Oktave
    if art == "verkuerzt":   return motiv[:max(4, len(motiv)//2)]
    if art == "erweitert":   return motiv + [motiv[-1], motiv[-1]-1, motiv[-1]-2]
    return motiv

# ── Chromatic Passing Note ─────────────────────────────────────────────────────
def chromatic_passing(skala, from_idx, to_idx):
    """Fügt einen chromatischen Übergang zwischen 2 Skalentönen ein."""
    from_p = skala[clamp_idx(skala, from_idx)]
    to_p   = skala[clamp_idx(skala, to_idx)]
    diff = to_p - from_p
    if abs(diff) == 2:  # Ganztonschritt → chromatischer Passing-Tone
        return (from_p + to_p) // 2  # Halbton dazwischen
    return None

# ── Pitch-Bend Simulation ──────────────────────────────────────────────────────
def erzeuge_note_mit_bend(skala, idx, dauer_viertel, velocity, aktuell, viertel, note_end_factor=0.92):
    """Erzeugt eine Note. Bei langen Noten: leicht nach oben biegend (Vocaloid-Feeling)."""
    pitch = skala[clamp_idx(skala, idx)]
    dur_sek = dauer_viertel * viertel
    n = pretty_midi.Note(
        velocity=velocity,
        pitch=pitch,
        start=aktuell,
        end=aktuell + dur_sek * note_end_factor
    )
    return n, pitch, dur_sek


def adjust_contour(section_type: str, phrase_notes: list, skala: list, p_idx: int, previous_question_last_pitch: int) -> int:
    """
    Enforces specific melodic contours (arch, fall, rise) on phrase notes in-place,
    and returns the final pitch if this is an even (question) phrase.
    """
    if not phrase_notes or len(phrase_notes) < 2:
        return phrase_notes[-1].pitch if (phrase_notes and p_idx % 2 == 0) else None

    pitches = [n.pitch for n in phrase_notes]
    n_notes = len(pitches)

    def get_shifted_pitch(reference_pitch, shift_steps):
        # Find nearest scale pitch to ensure scale locking
        ref_in_scale = min(skala, key=lambda p: abs(p - reference_pitch))
        idx = skala.index(ref_in_scale)
        new_idx = max(0, min(len(skala) - 1, idx + shift_steps))
        return skala[new_idx]

    # 1. Enforce section-specific contours
    if section_type == "Chorus":
        # Chorus (Arch contour): Peak pitch in second half, final pitch < first pitch
        if pitches[-1] >= pitches[0]:
            pitches[-1] = get_shifted_pitch(pitches[0], -1)
            
        peak_idx = pitches.index(max(pitches))
        target_min_peak_idx = n_notes // 2
        if peak_idx < target_min_peak_idx:
            # Shift the peak to the second half, avoiding the very last note
            target_idx = random.randint(target_min_peak_idx, n_notes - 2) if target_min_peak_idx < n_notes - 1 else target_min_peak_idx
            current_max = max(pitches)
            pitches[target_idx] = get_shifted_pitch(current_max, 1)

    elif section_type in ("Bridge", "Outro"):
        # Bridge & Outro (Fall contour): Ends lower than it starts
        if pitches[-1] >= pitches[0]:
            pitches[-1] = get_shifted_pitch(pitches[0], -1)

    elif section_type == "PreChorus":
        # PreChorus (Rise contour): Ends higher than it starts
        if pitches[-1] <= pitches[0]:
            pitches[-1] = get_shifted_pitch(pitches[0], 1)

    # 2. Enforce Question-Answer pairs (even = Q, odd = A)
    if p_idx % 2 == 1 and previous_question_last_pitch is not None:
        if pitches[-1] >= previous_question_last_pitch:
            pitches[-1] = get_shifted_pitch(previous_question_last_pitch, -1)

    next_question_pitch = pitches[-1] if p_idx % 2 == 0 else None

    # Write back adjusted pitches
    for i, note in enumerate(phrase_notes):
        note.pitch = pitches[i]

    return next_question_pitch


# ── Haupt-Generator ────────────────────────────────────────────────────────────
def generiere_melodie_sektion(
    bpm: float,
    silben: list,
    section_type: str,
    start_zeit: float,
    energy: str = "Hoch",
    key: str = KEY,
    mode: str = MODE,
    swing: float = SWING,
    style: str = "J-Pop Energy",
) -> tuple:
    """
    Generiert eine vollständige Vocaloid-Melodie-Sektion.
    Returns: (notes, melodie_daten, naechste_startzeit)
    """
    from chord_generator import get_progression, baue_akkord_pitches
    progression = get_progression(section_type, key, mode, style)

    viertel  = 60.0 / bpm
    sechzehntel = viertel / 4
    aktuell  = start_zeit
    notes    = []
    mel_data = []

    if not silben:
        return notes, mel_data, aktuell

    skala     = get_skala(section_type, key, mode)
    
    is_chiptune = (style in ("Kawaii Chiptune", "Chiptune J-Pop"))
    if is_chiptune:
        # Eigene Motive und Rhythmen für den bittersüßen, hyperaktiven Chiptune J-Pop Vibe
        chiptune_params = {
            "Intro":     {"motiv": "bogen_gross",     "rhythmus": "intro_flow",     "base_frac": 0.40, "pitch_bonus": 2},
            "Verse":     {"motiv": "vocaloid_rise",   "rhythmus": "vocaloid_rapid", "base_frac": 0.38, "pitch_bonus": 1},
            "PreChorus": {"motiv": "chromatic_climb", "rhythmus": "prechorus",      "base_frac": 0.44, "pitch_bonus": 3},
            "Chorus":    {"motiv": "bittersweet_hook","rhythmus": "chiptune_rapid", "base_frac": 0.60, "pitch_bonus": 5}, # Sehr hoch & emotional!
            "Bridge":    {"motiv": "wellen_abstieg",  "rhythmus": "bridge_lyric",   "base_frac": 0.46, "pitch_bonus": 2},
            "Outro":     {"motiv": "antwort",         "rhythmus": "outro_ballad",   "base_frac": 0.34, "pitch_bonus": 1},
        }
        param = chiptune_params.get(section_type, SEKTION_PARAM["Verse"])
    else:
        param = SEKTION_PARAM.get(section_type, SEKTION_PARAM["Verse"])

    rhythmus  = RHYTHMEN[param["rhythmus"]]

    # Energie-abhängige Rhythmus-Wahl
    if energy == "Maximal" and section_type == "Chorus" and not is_chiptune:
        rhythmus = RHYTHMEN["chorus_epic"]
    elif energy == "Niedrig":
        rhythmus = RHYTHMEN["jpop_verse"]

    # Basis-Tonhöhe berechnen
    basis_frac  = param["base_frac"]
    base_pitch  = VOCAL_MIN_PITCH + (VOCAL_MAX_PITCH - VOCAL_MIN_PITCH) * basis_frac
    base_pitch += param["pitch_bonus"]
    base_idx    = clamp_idx(skala, naechster_idx(skala, int(base_pitch)))

    # Haupt-Motiv
    haupt_motiv = MOTIVE[param["motiv"]]

    # Phrasen-Größe je nach Sektion (Vocaloid hat oft 6-8 Silben pro Phrase)
    phrase_sz = {
        "Chorus": 8, "PreChorus": 7, "Verse": 8,
        "Bridge": 6, "Intro": 8, "Outro": 8
    }.get(section_type, 8)

    phrasen = [silben[i:i+phrase_sz] for i in range(0, len(silben), phrase_sz)]

    # Variationen für Phrasen (Frage-Antwort-Prinzip)
    variationen_seq = [
        "original", "sequenz+1", "inversion", "sequenz+2",
        "retrograd", "oktave_hoch", "sequenz-1", "erweitert"
    ]

    # Energie → Velocity-Bereiche
    vel_map = {
        "Maximal": {"base": 118, "var": 8},
        "Hoch":    {"base": 108, "var": 10},
        "Normal":  {"base":  96, "var": 10},
        "Niedrig": {"base":  82, "var": 8},
    }
    section_vel = {
        "Chorus": 10, "PreChorus": 2, "Bridge": -8, "Intro": -4, "Outro": -12, "Verse": 0
    }
    vel_base  = vel_map.get(energy, vel_map["Hoch"])["base"] + section_vel.get(section_type, 0)
    vel_var   = vel_map.get(energy, vel_map["Hoch"])["var"]

    previous_question_last_pitch = None
    for p_idx, phrase in enumerate(phrasen):
        if not phrase:
            continue

        # Motiv für diese Phrase wählen
        if p_idx == 0:
            motiv   = haupt_motiv
            s_idx_b = base_idx
        elif p_idx % 2 == 1:
            # Antwort-Phrase: Variation + leicht höher (typischer J-Pop Frage/Antwort)
            var   = variationen_seq[p_idx % len(variationen_seq)]
            motiv = variiere_motiv(haupt_motiv, var)
            s_idx_b = clamp_idx(skala, base_idx + 2)
        else:
            # Wiederholung mit kleiner Variation
            var   = variationen_seq[(p_idx + 1) % len(variationen_seq)]
            motiv = variiere_motiv(haupt_motiv, var)
            s_idx_b = base_idx

        # Letzte Phrase: Kadenz-Abschluss
        if p_idx == len(phrasen) - 1:
            motiv   = MOTIVE["antwort"]
            s_idx_b = clamp_idx(skala, base_idx + 4)

        # Vocaloid-Pickup-Note (typisches "cha-" davor, Synkope)
        if p_idx == 0 and section_type in ("Chorus", "PreChorus"):
            p_idx_b = clamp_idx(skala, s_idx_b - 2)
            pickup_pitch = skala[p_idx_b]
            pickup_dur   = 0.25 * viertel
            n = pretty_midi.Note(
                velocity=max(70, vel_base - 15),
                pitch=pickup_pitch,
                start=max(0, aktuell - pickup_dur * 1.5),
                end=max(0.001, aktuell - 0.01)
            )
            notes.append(n)
            mel_data.append((pickup_pitch, 0.25))

        # Noten innerhalb der Phrase generieren
        prev_idx = s_idx_b
        phrase_notes = []
        mel_data_indices = []
        for n_idx, silbe in enumerate(phrase):
            k_idx    = n_idx % len(motiv)
            sprung   = motiv[k_idx]
            cur_idx  = clamp_idx(skala, s_idx_b + sprung)

            # Chromatischer Passing Tone (5% Chance bei Halbtonschritt)
            import config
            passing_pitch = None
            if getattr(config, "STRICT_SCALE_LOCKING", False):
                passing_pitch = None
            else:
                if n_idx > 0 and random.random() < 0.08 and abs(cur_idx - prev_idx) == 2:
                    pp = chromatic_passing(skala, prev_idx, cur_idx)
                    if pp is not None:
                        passing_pitch = pp

            pitch   = skala[cur_idx]

            # ── Harmonisierung: Vocal Melody an Akkordtöne anpassen! ──────────
            t_relative = aktuell - start_zeit
            bar_idx = int(t_relative / (4 * viertel))
            if progression:
                root_name, chord_type = progression[bar_idx % len(progression)]
                
                # Akkordtöne in 3 Gesangs-Oktaven (4, 5, 6)
                ct4 = baue_akkord_pitches(root_name, chord_type, base_octave=4)
                ct5 = baue_akkord_pitches(root_name, chord_type, base_octave=5)
                ct6 = baue_akkord_pitches(root_name, chord_type, base_octave=6)
                ch_pitches = ct4 + ct5 + ct6
                
                # Zählzeit prüfen (Taktanfang oder Schlag)
                is_strong = (t_relative % viertel < 0.05) or (t_relative % (4 * viertel) < 0.05)
                
                # 80% Chance auf Akkordton, auf starken Beats 100%
                if ch_pitches and (is_strong or random.random() < 0.80):
                    # Finde den am nächsten liegenden Akkordton
                    nearest_p = min(ch_pitches, key=lambda p: abs(p - pitch))
                    if VOCAL_MIN_PITCH <= nearest_p <= VOCAL_MAX_PITCH:
                        pitch = nearest_p

            if getattr(config, "STRICT_SCALE_LOCKING", False):
                if pitch not in skala:
                    pitch = min(skala, key=lambda p: abs(p - pitch))

            # Rhythmus
            r_idx       = n_idx % len(rhythmus)
            dur_viertel = rhythmus[r_idx]

            # Swing auf Achtel-Upbeats
            swing_add = 0.0
            if swing > 0.01 and dur_viertel in (0.5, 0.25):
                swing_add = swing * viertel * 0.14

            # Dynamik – mit echten Phrasen-Bögen
            # Phrasenanfang etwas sanfter, Mitte betont, Ende leiser (Atem)
            vel = vel_base
            if n_idx == 0:
                vel = max(vel_base - 12, 60)
            elif n_idx == len(phrase) // 2:
                vel = min(vel_base + 10, 127)  # Phrasenhöhepunkt
            elif n_idx >= len(phrase) - 2:
                vel = max(vel_base - 20, 55)   # Ausklingen

            velocity = max(50, min(127, vel + random.randint(-vel_var, vel_var)))

            dur_sek = dur_viertel * viertel + swing_add

            # Legato-Faktor: kurze Noten etwas abgesetzt, lange gebunden
            if dur_viertel <= 0.25:
                legato = 0.75
            elif dur_viertel <= 0.5:
                legato = 0.88
            elif dur_viertel <= 1.0:
                legato = 0.93
            else:
                legato = 0.97

            # Optionaler Chromatischer Passing-Ton (sehr kurz davor)
            if passing_pitch is not None and dur_sek > sechzehntel * 2:
                pass_dur = sechzehntel * 0.5
                n_pass = pretty_midi.Note(
                    velocity=max(50, velocity - 20),
                    pitch=passing_pitch,
                    start=aktuell,
                    end=aktuell + pass_dur
                )
                notes.append(n_pass)
                mel_data.append((passing_pitch, 0.125))
                aktuell += pass_dur
                dur_sek -= pass_dur

            n = pretty_midi.Note(
                velocity=velocity,
                pitch=pitch,
                start=aktuell,
                end=aktuell + dur_sek * legato
            )
            notes.append(n)
            phrase_notes.append(n)
            mel_data_indices.append(len(mel_data))
            mel_data.append((pitch, dur_viertel))
            aktuell += dur_sek
            prev_idx = cur_idx

        # Apply contour adjustments
        previous_question_last_pitch = adjust_contour(
            section_type, phrase_notes, skala, p_idx, previous_question_last_pitch
        )

        # Sync the adjusted note pitches back into mel_data for synthesizer synthesis
        for idx, note in enumerate(phrase_notes):
            mel_idx = mel_data_indices[idx]
            dur_val = mel_data[mel_idx][1]
            mel_data[mel_idx] = (note.pitch, dur_val)

        # Atem-Pause nach jeder Phrase
        if p_idx < len(phrasen) - 1:
            if section_type in ("Chorus", "PreChorus"):
                atem_sek = random.uniform(0.15, 0.25)
            elif section_type == "Bridge":
                atem_sek = random.uniform(0.30, 0.50)
            else:
                atem_sek = random.uniform(0.20, 0.35)

            # Clamp strictly to [0.15, 0.5]
            atem_sek = max(0.15, min(0.5, atem_sek))
            atem_beats = atem_sek / viertel

            aktuell += atem_sek
            mel_data.append((None, atem_beats))

    # Abschluss-Pause
    aktuell += 0.4 * viertel
    mel_data.append((None, 0.4))

    return notes, mel_data, aktuell
