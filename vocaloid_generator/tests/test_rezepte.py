# test_rezepte.py – Song-Rezepte mit Beispieltext (v6 Nr. 13)
import pytest

import config
import lyric_helper
import main
import rezepte
from pipeline import SongResult
from lyrics import kind_of, parse_lyrics
from settings import SongSettings
from styles import STYLES


def test_eight_to_ten_recipes_each_a_song_with_its_own_text():
    assert 8 <= len(rezepte.RECIPES) <= 10 and len(set(rezepte.names())) == len(rezepte.RECIPES)
    assert {"Idol-Pop", "Ballade", "City Pop", "Future Bass", "Dark Vocaloid"} <= \
        {r.values["style"] for r in rezepte.RECIPES}
    for recipe in rezepte.RECIPES:
        s = rezepte.apply(recipe.name, SongSettings())
        assert s.style in STYLES and s.lyrics == recipe.lyrics and recipe.about
        sung = {kind_of(k) for k in parse_lyrics(s.lyrics)}
        needed = {k for k in s.active_sections if config.SECTION_CONFIG[k]["has_vocals"]}
        assert needed <= sung, (recipe.name, needed - sung)               # jede gesungene Sektion hat Text
        for sec in lyric_helper.check(s):
            assert all(line.status != "zu viel" for line in sec.lines), (recipe.name, sec.name)
            assert not sec.longer, (recipe.name, sec.name)


def test_the_idol_recipe_raps_and_calls_and_the_waltz_is_in_three():
    idol = rezepte.apply("Hologram Star (wie Idol)", SongSettings(rap_voice=False, idol_calls=False))
    assert "Rap" in idol.active_sections and idol.rap_voice and idol.idol_calls and idol.style == "Idol-Pop"
    waltz = rezepte.apply("Walzer im Mondlicht (3/4)", SongSettings())
    assert waltz.meter == "3/4" and waltz.ritardando and waltz.active_sections[-1] == "Outro"


def test_a_recipe_starts_a_new_song_but_keeps_voice_and_folders(tmp_path):
    mine = SongSettings(seed=42, variations={"bass": 2}, melody_edits={"4.0": 60}, remix_from="Rock", remix_bpm=130,
                        singer="KIRITAN", vocal_engine="VOICEVOX", output_ordner=str(tmp_path), custom_chords={
                            "Chorus": "F G Em Am"})
    s = rezepte.apply("Sky Drop (Future Bass)", mine)
    assert (s.seed, s.variations, s.melody_edits, s.remix_from, s.custom_chords) == (None, {}, {}, "", {})
    assert (s.singer, s.vocal_engine, s.output_ordner) == ("KIRITAN", "VOICEVOX", str(tmp_path))
    with pytest.raises(ValueError):
        rezepte.apply("Gibt es nicht", mine)


def test_the_command_line_takes_a_recipe(monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        main.parse_args(["--rezept", "Gibt es nicht"])
    seen = {}

    def fake_generate(settings, progress=None, seed=None):
        seen["settings"] = settings
        return SongResult(seed=1, output_dir=str(tmp_path), mix_wav=str(tmp_path / "final_mix.wav"))

    monkeypatch.setattr(main, "generate_song", fake_generate)
    assert main.main(["--rezept", "Sky Drop (Future Bass)", "--bpm", "140"]) == 0
    s = seen["settings"]
    assert (s.style, s.bpm, s.lyrics) == ("Future Bass", 140, rezepte.get("Sky Drop (Future Bass)").lyrics)
