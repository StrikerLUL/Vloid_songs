# test_schalter.py – Ändert jeder Schalter wirklich etwas? (v6 Nr. 9)
#
# Bis 1.1 lief ein Schalter ins Leere: die echten Grooves spielten wegen des Grund-Swings fast nie. Deshalb steht hier
# jeder Ein/Aus-Schalter aus SongSettings in genau einer Gruppe, und jede Gruppe weist nach, dass Ausschalten etwas
# ändert. Ein neuer Schalter ohne Eintrag lässt test_every_switch_has_a_proof scheitern.
import ast
import glob
import os
import re

import pytest

import config
import mixdown
import neutrino_score
import pipeline
import reference
import rendering
import singing
import style_fx
from settings import SongSettings

HERE = os.path.dirname(__file__)
LYRICS = "[Verse]\nよるのまちをあるく\n[Verse 2]\nあさのひかりがまぶしいね\n[Chorus]\nらららら るるる\n" \
         "[PreChorus]\nそらへ\n[Bridge]\nゆめのなか"

# Ändert die Noten des Songs (pipeline.compose)
NOTES = ("more_motifs", "numbered_lyrics", "harmony_variety", "sung_pads", "adlibs", "guitar_strums", "lively_bass")
# Ändert die Einstellungen des Mixes (mixdown.mix_arguments); in Klammern der Stil, in dem er wirkt
MIX = {"echo_throws": None, "vocal_chain": None, "vocal_tone": None, "vocal_unmask": None, "vocal_ride": None,
       "convolution_reverb": None, "ducked_delay": None, "mix_movement": None, "airwindows": None,
       "lofi_texture": "Lo-Fi", "true_peak": None, "resonance_tamer": None, "mix_punch": None}
# Ändert, womit eine Spur klingt (rendering._render_job)
RENDER = ("sound_library", "guitar_amp", "real_drums", "band_samples")
# Ändert, was auf der fertigen Gesangsspur passiert (singing._liven)
LIVEN = ("syllable_dynamics", "phrase_expression", "final_choir", "breaths", "recorded_breaths")
# Ändert die Stil-Effekte auf dem Gesang (style_fx.effects_for) im genannten Stil
STYLE_FX = {"telephone_fx": "Future Bass", "stutter_fx": "Future Bass", "hard_tune": "Future Bass",
            "formant_fx": "Kawaii Chiptune"}
# Ändert die Noten für NEUTRINO (neutrino_score.options)
SCORE = ("long_vowel_mark", "breath_marks", "fast_diphthongs")
# Ändert, was die Vorbilder vorschlagen (pipeline.from_references)
SUGGESTIONS = ("ref_tempo_key", "ref_style")
# Kommt bei der Stimme an (eigene Tests unten)
WIRED = ("shimmer", "own_vocal_align")
# Braucht eine Stimme, Aufnahmen oder ein Werkzeug: der Nachweis steht in diesem Test
ELSEWHERE = {
    "learned_motifs": "test_motifs.py::test_the_melody_sings_learned_rhythms",
    "singable_melody": "test_singbarkeit.py::test_composed_songs_are_singable_and_the_check_has_a_switch",
    "harmonies": "test_sektions_stil.py::test_harmony_and_choir_sing_like_the_chorus",
    "psola_reshape": "test_voice.py::test_psola_is_used_when_parselmouth_is_there_and_world_otherwise",
    "vocal_comping": "test_gesang.py::test_two_takes_are_comped_and_double_the_chorus",
    "vocal_swing": "test_gesang_swing.py::test_the_vocal_swings_only_when_the_band_swings_enough",
    "romaji": "test_gesang.py::test_romaji_can_be_switched_off",
    "smart_readings": "test_gesang_130.py::test_particles_and_number_words_are_sung_like_spoken",
    "melody_tensions": "test_melodie_130.py::test_leaning_tones_resolve_and_long_chorus_tones_take_colors",
    "melody_climax": "test_melodie_130.py::test_the_last_chorus_ends_on_the_highest_note_of_the_song",
    "melody_triplets": "test_melodie_130.py::test_triplets_and_dotted_rhythms_reach_neutrino_as_real_tuplets",
    "english_kana": "test_gesang.py::test_romaji_lyrics_reach_the_song",
    "section_style": "test_sektions_stil.py::test_section_style_can_be_switched_off",
    "even_takes": "test_sektions_stil.py::test_takes_keep_the_style_shift_unless_neutrino_sings_the_same_every_time",
    "harmony_double": "test_begleitstimmen.py::test_backing_voices_can_be_switched_off",
    "style_singer": "test_casting.py::test_the_favorite_voice_follows_the_style",
    "voicevox_dynamics": "test_voicevox_dynamik.py::test_with_voicevox_the_dynamics_are_sung_not_turned_afterwards",
    "ref_mastering": "test_reference.py::test_reference_targets_follow_the_switches",
    "ref_energy": "test_reference.py::test_reference_targets_follow_the_switches",
    "ref_vocal_level": "test_reference.py::test_reference_targets_follow_the_switches",
    "ref_stems": "test_separation.py::test_reference_targets_take_the_groups_instead_of_the_vocal_guess",
    "ref_vocal_curve": "test_gesangsklang.py::test_the_curve_can_be_switched_off",
    "samples": "test_samples.py::test_pipeline_switch_and_own_soundfont",
    "real_grooves": "test_grooves.py::test_songs_use_real_grooves_only_when_switched_on_and_straight",
    "polish": "test_polish.py::test_the_song_gets_a_second_polished_version",
    "ai_accompaniment": "test_accompaniment.py::test_switched_off_or_draft_the_model_is_not_asked",
    "draft": "test_alltag.py::test_draft_skips_the_slow_steps_and_keeps_the_real_song",
    "auto_rating": "test_rating.py::test_the_switch_turns_the_rating_off",
    "album_vary": "test_alltag.py::test_album_plan_takes_the_styles_in_turn_with_their_typical_values",
    "vocal_versions": "test_fassungen.py::test_switched_off_there_are_no_versions_and_no_tags",
    "id3_tags": "test_fassungen.py::test_switched_off_there_are_no_versions_and_no_tags",
    "keep_projects": "test_projekt.py::test_without_the_switch_nothing_is_kept_and_deleting_takes_the_project_along",
    "rap_voice": "test_rap.py::test_without_the_switch_or_without_voicevox_the_singer_sings_the_rap",
    "idol_calls": "test_idol_rufe.py::test_without_the_switch_there_are_no_calls",
    "vocal_chops": "test_vocal_chops.py::test_the_song_mixes_the_chops_only_with_the_switch",
    "ritardando": "test_ritardando.py::test_a_ballad_slows_down_and_holds_the_last_chord",
    "video_colors": "test_video.py::test_the_video_takes_the_colors_of_the_style_only_with_the_switch",
    # 1.3.0
    "best_melody": "test_melodie_130.py::test_the_best_of_many_melodies_sings",
    "melody_pickups": "test_melodie_130.py::test_phrases_start_before_the_bar_and_downbeats_are_pushed",
    "kime": "test_band_130.py::test_the_band_plays_kime_stops_and_fills",
    "intro_riff": "test_band_130.py::test_the_song_has_its_own_riff_and_an_interlude",
    "band_groove": "test_band_130.py::test_the_band_plays_in_the_pocket_of_the_drummer",
    "bass_runs": "test_band_130.py::test_the_bass_runs_fills_jumps_octaves_and_plays_funk",
    "band_runs": "test_band_130.py::test_piano_and_strings_run_glide_and_play_the_hook",
    "anison_grooves": "test_band_130.py::test_fast_anime_songs_get_anison_grooves_rolls_and_stops",
    "section_buildup": "test_band_130.py::test_the_first_verse_starts_alone_and_choruses_grow",
    "vocal_pocket": "test_gesang_130.py::test_the_voice_sits_behind_or_ahead_of_the_beat_by_style",
    "diffsinger_expression": "test_gesang_130.py::test_diffsinger_breathes_in_the_verse_and_pushes_in_the_chorus",
    "ai_melody": "test_melodie_130.py::test_the_ai_suggests_chorus_melodies_and_the_better_one_sings",
}
# Bedienung der App, ändert den Song nicht
APP = ("show_karaoke", "reuse_steps", "log_file", "update_check", "setup_wizard", "done_notice", "lyric_hints",
       "shortcuts")

GROUPS = {"NOTES": NOTES, "MIX": tuple(MIX), "RENDER": RENDER, "LIVEN": LIVEN, "STYLE_FX": tuple(STYLE_FX),
          "SCORE": SCORE, "SUGGESTIONS": SUGGESTIONS, "WIRED": WIRED, "ELSEWHERE": tuple(ELSEWHERE), "APP": APP}
SWITCHES = sorted(name for name, value in SongSettings().model_dump().items() if isinstance(value, bool))


def test_every_switch_has_a_proof():
    listed = [name for names in GROUPS.values() for name in names]
    assert sorted(set(listed)) == SWITCHES, "jeder Schalter braucht genau eine Gruppe in test_schalter.py"
    assert len(listed) == len(set(listed))


def _names_in(paths) -> set:
    """Attribute, Schlüsselwörter und Texte, die in diesen Dateien vorkommen."""
    found = set()
    for path in paths:
        for node in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
            if isinstance(node, ast.Attribute):
                found.add(node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.add(node.value)
    return found


def test_every_switch_is_read_by_the_program():
    # settings.py legt die Schalter an, main.py und gui/ setzen sie; history.py und vorlagen.py zählen sie nur auf
    skip = {"settings.py", "main.py", "history.py", "vorlagen.py"}
    program = [p for p in glob.glob(os.path.join(config.BASE_DIR, "*.py")) if os.path.basename(p) not in skip]
    read = _names_in(program)
    gui = _names_in(glob.glob(os.path.join(config.BASE_DIR, "gui", "*.py")) + [os.path.join(config.BASE_DIR, "app.py")])
    assert [name for name in SWITCHES if name not in APP and name not in read] == []
    assert [name for name in APP if name not in read | gui] == []


def test_settings_the_voice_hears_are_in_the_vocal_fingerprint():
    # Ein Gesangs-Schalter, der im Fingerabdruck fehlt, wirkt erst, wenn sich sonst etwas ändert: bis dahin kommt der
    # alte Gesang wieder (singing._vocal_key). Nur Schalter, die nicht den Klang ändern, dürfen fehlen.
    not_sound = {"reuse_steps", "channels", "swing", "style_singer", "style_singers"}   # swing: _swing_amount
    fields = set(SongSettings.model_fields)
    used = set()
    for name in singing.VOCAL_CODE + ("casting.py", "own_vocal.py", "style_fx.py"):
        source = open(os.path.join(config.BASE_DIR, name), encoding="utf-8").read()
        used |= set(re.findall(r"settings\.(\w+)", source)) | set(re.findall(r'getattr\(settings, "(\w+)"', source))
    assert sorted((used & fields) - set(singing.VOCAL_FIELDS) - not_sound) == []


def test_tests_named_as_proof_exist_and_use_the_switch():
    for name, ref in ELSEWHERE.items():
        file, test = ref.split("::")
        tree = ast.parse(open(os.path.join(HERE, file), encoding="utf-8").read())
        fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == test), None)
        assert fn is not None, ref
        mentioned = {n.arg for n in ast.walk(fn) if isinstance(n, ast.keyword)} | _names_in_node(fn)
        assert name in mentioned, f"{ref} schaltet {name} nicht"


def _names_in_node(node) -> set:
    return {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)} | \
        {n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


# ── die Nachweise ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def song(tmp_path_factory):
    out = tmp_path_factory.mktemp("schalter")
    s = SongSettings().with_updates(output_ordner=str(out), seed=3, lyrics=LYRICS)
    tracks, _ = pipeline.compose(s)
    return s, tracks, str(out)


def _notes(tracks) -> dict:
    return {key: [(round(n.start, 4), n.pitch, n.velocity, round(n.end, 4)) for n in value]
            if isinstance(value, list) and value and hasattr(value[0], "pitch") else value
            for key, value in tracks.items() if key != "plan"}


@pytest.mark.parametrize("name", NOTES)
def test_switching_off_changes_the_notes(song, name):
    s, tracks, _ = song
    off, _ = pipeline.compose(s.with_updates(**{name: False}))
    assert _notes(off) != _notes(tracks)


@pytest.mark.parametrize("name", list(MIX))
def test_switching_off_changes_the_mix(song, name):
    s, tracks, out = song
    if MIX[name]:
        s = s.with_updates(style=MIX[name])
    on = mixdown.mix_arguments(s, tracks, out, has_vocals=True)
    off = mixdown.mix_arguments(s.with_updates(**{name: False}), tracks, out, has_vocals=True)
    assert repr(on) != repr(off)


@pytest.mark.parametrize("name", RENDER)
def test_switching_off_changes_the_sound_of_the_tracks(song, name):
    s, _, out = song
    jobs = [rendering._render_job(s, out, inst) for inst in ("drums", "guitar", "piano")]
    assert [rendering._render_job(s.with_updates(**{name: False}), out, inst)
            for inst in ("drums", "guitar", "piano")] != jobs


@pytest.mark.parametrize("name", LIVEN)
def test_switching_off_changes_the_finished_vocal(song, name, monkeypatch, tmp_path):
    import voice_fx
    s, tracks, _ = song
    calls = []
    monkeypatch.setattr(voice_fx, "syllable_dynamics", lambda *a, **k: calls.append("syllable_dynamics"))
    monkeypatch.setattr(voice_fx, "express", lambda *a, **k: calls.append("phrase_expression"))
    monkeypatch.setattr(voice_fx, "choir_from_lead", lambda *a, **k: calls.append("final_choir"))
    monkeypatch.setattr(voice_fx, "add_breaths", lambda *a, recorded=False, **k: calls.append(("breaths", recorded))
                        or 0)
    singing._liven(s, tracks, str(tmp_path), str(tmp_path / "vocals.wav"))
    on, calls[:] = list(calls), []
    singing._liven(s.with_updates(**{name: False}), tracks, str(tmp_path), str(tmp_path / "vocals.wav"))
    assert calls != on


@pytest.mark.parametrize("name", list(STYLE_FX))
def test_switching_off_takes_the_style_effect_away(name, monkeypatch):
    import importlib
    monkeypatch.setattr(style_fx, "STYLES", importlib.reload(style_fx).STYLES)    # conftest schaltet sie ab
    s = SongSettings()
    assert style_fx.effects_for(STYLE_FX[name], s.with_updates(**{name: False})) != \
        style_fx.effects_for(STYLE_FX[name], s)


@pytest.mark.parametrize("name", SCORE)
def test_switching_off_changes_the_score_for_neutrino(name):
    s = SongSettings()
    assert neutrino_score.options(s.with_updates(**{name: False})) != neutrino_score.options(s)


@pytest.mark.parametrize("name", SUGGESTIONS)
def test_switching_off_keeps_the_own_choice(name, monkeypatch):
    summary = reference.Summary(bpm=172, key="D", scale="minor", style="Dark Vocaloid", contrast_db=4.0,
                                vocal_db=-3.0, names=["a.wav"])
    monkeypatch.setattr(reference, "summarize", lambda *a: summary)
    s = SongSettings(style="Rock", bpm=120, key="C", scale="major")
    taken = pipeline.from_references(s)
    kept = pipeline.from_references(s.with_updates(**{name: False}))
    assert (kept.style, kept.bpm, kept.key, kept.scale) != (taken.style, taken.bpm, taken.key, taken.scale)


def test_the_preview_voice_gets_its_shimmer_switch(monkeypatch, tmp_path):
    import vocal_synthesizer
    seen = []
    monkeypatch.setattr(vocal_synthesizer, "generiere_lokale_vocals", lambda *a, **k: seen.append(k))
    for shimmer in (True, False):
        singing._sing_preview(SongSettings(shimmer=shimmer), {"melody_data": [], "silben": []},
                              str(tmp_path / "v.wav"))
    assert [k["shimmer"] for k in seen] == [True, False]


def test_the_own_vocal_gets_its_align_switch(monkeypatch, tmp_path):
    import own_vocal
    seen = []
    monkeypatch.setattr(own_vocal, "place", lambda *a: seen.append(a[-1]))
    for align in (True, False):
        s = SongSettings(own_vocal=str(tmp_path / "eigen.wav"), own_vocal_align=align, final_choir=False)
        singing._place_own_vocal(s, {"melody_data": [], "plan": None}, str(tmp_path), str(tmp_path / "v.wav"), None)
    assert seen == [True, False]
