# labels.py – Deutsche Namen für alles, was die Oberfläche anzeigt
CHANNELS = {
    "vocals": "Gesang", "melody": "Lead", "piano": "Klavier", "bass": "Bass", "guitar": "Gitarre",
    "strings": "Streicher", "synth": "Synth", "brass": "Bläser", "bells": "Glocken", "choir": "Chor",
    "counter": "Gegenstimme", "perc": "Percussion", "drums": "Schlagzeug", "fx": "Effekte", "master": "Master",
}
# Teile zum Neu-Würfeln, in der Reihenfolge der Knöpfe
PARTS = {
    "melody": "Melodie", "chords": "Akkorde", "drums": "Schlagzeug", "bass": "Bass", "piano": "Klavier",
    "guitar": "Gitarre", "strings": "Streicher", "synth": "Synth", "brass": "Bläser", "bells": "Glocken",
    "choir": "Chor", "counter": "Gegenstimme", "perc": "Percussion",
}
PART_HINTS = {
    "melody": "Neue Gesangsmelodie; die Gegenstimme antwortet mit.",
    "chords": "Neue Akkorde und neuer Ablauf; alles, was auf den Akkorden spielt, ändert sich mit.",
}
SCALES = {"minor": "Moll", "major": "Dur", "dorian": "Dorisch", "phrygian": "Phrygisch"}
ENGINES = {"NEUTRINO": "NEUTRINO", "VOICEVOX": "VOICEVOX (kostenlos, läuft als App)",
           "DiffSinger": "DiffSinger (Versuch, Stimmen für OpenUtau)",
           "Vorschau": "Vorschau-Stimme (ohne NEUTRINO und VOICEVOX)"}
SECTIONS = {
    "Intro": "Intro", "Build-up": "Build-up", "Verse": "Strophe", "PreChorus": "Pre-Chorus", "Chorus": "Refrain",
    "Bridge": "Bridge", "Drop": "Drop", "Solo": "Solo", "Outro": "Outro",
}
STRUCTURES = {
    "Kurz": ["Intro", "Verse", "PreChorus", "Chorus", "Outro"],
    "Standard": ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"],
    "Lang": ["Intro", "Build-up", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Drop",
             "Chorus", "Chorus", "Outro"],
}
PLAYING = {
    "default": "wie der Stil", "chords": "Akkorde", "eighths": "Achtel", "stabs": "kurze Akzente",
    "arpeggio": "Arpeggio", "arpeggio16": "Arpeggio in Sechzehnteln", "ballad_arp": "Balladen-Arpeggio",
    "jazz_ch": "Jazz-Akkorde", "root": "Grundton", "driving": "treibend", "sync": "synkopiert",
    "octaves": "Oktaven", "wobble": "Wobble", "sub_pulse": "Sub-Puls", "lazy": "entspannt",
    "chill_riff": "ruhiges Riff", "strummed": "geschlagen", "palm_mute": "Palm Mute", "power_chords": "Powerchords",
    "cutting": "Funk-Cutting", "legato": "Legato", "build": "Steigerung", "pizzicato": "Pizzicato",
    "staccato": "Staccato", "pad": "Fläche", "riser": "Riser", "staccato_pluck": "Staccato-Pluck",
    "wide_saw": "breite Säge", "pluck": "Pluck", "arp": "Arpeggiator", "supersaw": "Supersaw",
    "accents": "Akzente", "sparkle": "Glitzern", "sparkle16": "Glitzern in Sechzehnteln",
    "hook_octave": "Hook in der Oktave", "music_box": "Spieluhr", "aahs": "Aahs", "oohs": "Oohs",
    "answer": "antwortet dem Gesang", "guide": "begleitet den Gesang", "solo": "Solo", "shaker": "Shaker",
    "claps": "Claps", "tambourine": "Tamburin", "congas": "Congas", "cowbell": "Kuhglocke",
    "harp": "Harfe", "timpani": "Pauken", "horns": "Hörner",
    "rolling": "rollend (Drum and Bass)", "fb_chords": "Future-Bass-Akkorde",
    "soundfont": "SoundFont-Schlagzeug", "808": "Drum-Machine 808", "909": "Drum-Machine 909",
}
# Farben der Spuren in der Piano-Roll
COLORS = {
    "vocals": "#ff4f8b", "melody": "#ffb74d", "piano": "#64b5f6", "bass": "#9575cd", "guitar": "#ef5350",
    "strings": "#4db6ac", "synth": "#ba68c8", "brass": "#ffd54f", "bells": "#81d4fa", "choir": "#a5d6a7",
    "counter": "#f06292",
}
