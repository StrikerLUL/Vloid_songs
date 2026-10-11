# preset_manager.py - Preset Manager for Vocaloid Generator Pro

PRESETS = {
    "J-Pop Energy": {
        "bpm": 165,
        "key": "A",
        "scale": "minor",
        "active_sections": ["Intro", "Build-up", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"],
        "volumes": {
            "piano": 0.8, "bass": 0.9, "guitar": 0.8, "strings": 0.7,
            "synth": 0.7, "brass": 0.7, "drums": 1.0, "melody": 0.8, "vocals": 1.0, "master": 1.0
        },
        "panning": {
            "piano": -0.25, "bass": 0.0, "guitar": 0.30, "strings": -0.40,
            "synth": 0.0, "brass": 0.20, "drums": 0.0, "melody": -0.15, "vocals": 0.0, "master": 0.0
        },
        "enabled": {
            "piano": True, "bass": True, "guitar": True, "strings": True,
            "synth": True, "brass": True, "drums": True, "melody": True, "vocals": True
        }
    },
    "Kawaii Chiptune": {
        "bpm": 175,
        "key": "C",
        "scale": "major",
        "active_sections": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
        "volumes": {
            "piano": 0.4, "bass": 0.8, "guitar": 0.0, "strings": 0.3,
            "synth": 1.0, "brass": 0.0, "drums": 0.9, "melody": 0.9, "vocals": 1.0, "master": 1.0
        },
        "panning": {
            "piano": -0.3, "bass": 0.0, "guitar": 0.0, "strings": 0.4,
            "synth": 0.2, "brass": 0.0, "drums": 0.0, "melody": -0.1, "vocals": 0.0, "master": 0.0
        },
        "enabled": {
            "piano": True, "bass": True, "guitar": False, "strings": True,
            "synth": True, "brass": False, "drums": True, "melody": True, "vocals": True
        }
    },
    "Ballade": {
        "bpm": 80,
        "key": "G",
        "scale": "major",
        "active_sections": ["Intro", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
        "volumes": {
            "piano": 0.9, "bass": 0.6, "guitar": 0.4, "strings": 0.8,
            "synth": 0.0, "brass": 0.0, "drums": 0.4, "melody": 0.7, "vocals": 1.0, "master": 1.0
        },
        "panning": {
            "piano": -0.2, "bass": 0.0, "guitar": 0.3, "strings": -0.1,
            "synth": 0.0, "brass": 0.0, "drums": 0.0, "melody": -0.15, "vocals": 0.0, "master": 0.0
        },
        "enabled": {
            "piano": True, "bass": True, "guitar": True, "strings": True,
            "synth": False, "brass": False, "drums": True, "melody": True, "vocals": True
        }
    },
    "Rock": {
        "bpm": 130,
        "key": "E",
        "scale": "minor",
        "active_sections": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
        "volumes": {
            "piano": 0.0, "bass": 0.9, "guitar": 1.0, "strings": 0.0,
            "synth": 0.0, "brass": 0.0, "drums": 0.9, "melody": 0.8, "vocals": 1.0, "master": 1.0
        },
        "panning": {
            "piano": 0.0, "bass": -0.05, "guitar": 0.4, "strings": 0.0,
            "synth": 0.0, "brass": 0.0, "drums": 0.0, "melody": -0.1, "vocals": 0.0, "master": 0.0
        },
        "enabled": {
            "piano": False, "bass": True, "guitar": True, "strings": False,
            "synth": False, "brass": False, "drums": True, "melody": True, "vocals": True
        }
    },
    "City Pop": {
        "bpm": 115,
        "key": "D",
        "scale": "major",
        "active_sections": ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Outro"],
        "volumes": {
            "piano": 0.8, "bass": 0.9, "guitar": 0.7, "strings": 0.6,
            "synth": 0.8, "brass": 0.8, "drums": 0.8, "melody": 0.7, "vocals": 1.0, "master": 1.0
        },
        "panning": {
            "piano": -0.2, "bass": 0.0, "guitar": 0.3, "strings": -0.3,
            "synth": 0.2, "brass": 0.15, "drums": 0.0, "melody": -0.1, "vocals": 0.0, "master": 0.0
        },
        "enabled": {
            "piano": True, "bass": True, "guitar": True, "strings": True,
            "synth": True, "brass": True, "drums": True, "melody": True, "vocals": True
        }
    },
    "Dark Vocaloid": {
        "bpm": 150,
        "key": "F#",
        "scale": "minor",
        "active_sections": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
        "volumes": {
            "piano": 0.7, "bass": 0.9, "guitar": 0.5, "strings": 0.8,
            "synth": 0.9, "brass": 0.0, "drums": 0.8, "melody": 0.8, "vocals": 1.0, "master": 1.0
        },
        "panning": {
            "piano": -0.25, "bass": 0.0, "guitar": 0.3, "strings": -0.4,
            "synth": 0.3, "brass": 0.0, "drums": 0.0, "melody": -0.15, "vocals": 0.0, "master": 0.0
        },
        "enabled": {
            "piano": True, "bass": True, "guitar": True, "strings": True,
            "synth": True, "brass": False, "drums": True, "melody": True, "vocals": True
        }
    }
}

def apply_preset(model, preset_name):
    """Applies preset settings to the model."""
    if preset_name not in PRESETS:
        return False
    preset = PRESETS[preset_name]
    model.bpm = preset["bpm"]
    model.key = preset["key"]
    model.scale = preset["scale"]
    model.active_sections = list(preset["active_sections"])
    
    # Set volumes, panning, enabled
    for inst, vol in preset["volumes"].items():
        setattr(model, f"volume_{inst}", vol)
    for inst, pan in preset["panning"].items():
        setattr(model, f"pan_{inst}", pan)
    for inst, enabled in preset["enabled"].items():
        setattr(model, f"enabled_{inst}", enabled)
    
    model.style = preset_name
    model.log_text = f"Preset angewendet: {preset_name}"
    return True


def preset_settings(preset_name, settings):
    """Die Einstellungen mit den typischen Werten eines Stils (Tempo, Tonart, Ablauf, Lautstärken).
    Gibt None zurück, wenn es für den Stil keine Vorgabe gibt."""
    preset = PRESETS.get(preset_name)
    if preset is None:
        return None
    channels = {ch: data.model_dump() for ch, data in settings.channels.items()}
    for key, field in (("volumes", "volume"), ("panning", "pan"), ("enabled", "enabled")):
        for ch, value in preset[key].items():
            if ch in channels:
                channels[ch][field] = value
    return settings.with_updates(
        style=preset_name, bpm=preset["bpm"], key=preset["key"], scale=preset["scale"],
        active_sections=list(preset["active_sections"]), channels=channels,
    )
