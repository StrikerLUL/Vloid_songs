# test_charakter_150.py – Charakter 1.5.0: J-Pop Energy und Idol-Pop getrennt (C1), Produzenten-Profil (C2),
# Geschmack aus den Daumen im Verlauf (C3), zwei Stile gemischt (C4)
import random

import config
import pipeline
import song_character
import style_dna
from settings import SongSettings
from song_plan import build_plan
from styles import get_style

STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Outro"]
ROYAL_ROAD = ("IV", "V", "iii", "vi")


def _plan(style: str, seed: int, split: bool, mode: str = "major", own_chords: bool = True):
    return build_plan(get_style(style), 140, STRUCTURE, "C", mode, config.SECTION_CONFIG, random.Random(seed), {},
                      own_chords=own_chords, split=split)


def _royal(progression: str) -> bool:
    chords = [c.rstrip("7").replace("maj", "") for c in progression.replace("|", " ").split()]
    return any(tuple(chords[i:i + 4]) == ROYAL_ROAD for i in range(len(chords) - 3))


# ── C1 J-Pop Energy und Idol-Pop getrennt ────────────────────────────────────────
def test_jpop_and_idol_go_separate_ways(new_150, tmp_path):
    # J-Pop: keine Royal Road mehr, weder in Dur noch in Moll; vor dem Refrain der Anlauf bVI–bVII
    for seed in range(12):
        for mode in ("major", "minor"):
            plan = _plan("J-Pop Energy", seed, True, mode)
            bank = style_dna.SPLIT_PROGRESSIONS["J-Pop Energy"][mode]
            assert plan.progressions["Chorus"] in bank["Chorus"] and not _royal(plan.progressions["Chorus"])
            assert plan.progressions["Verse"] in bank["Verse"]
        assert _plan("J-Pop Energy", seed, True, own_chords=False).progressions == _plan(
            "J-Pop Energy", seed, True).progressions, "auch ohne „Akkorde je Stil“"
    pre = next(sec for sec in _plan("J-Pop Energy", 3, True).sections if sec.kind == "PreChorus")
    assert [slot.chord.root for slot in pre.chords[-2:]] == [8, 10]
    assert any(_royal(p) for p in style_dna.progressions("J-Pop Energy", "major", "Chorus")), "ohne Schalter wie 1.4"
    # Idol-Pop behält seine Akkorde
    assert _plan("Idol-Pop", 4, True).progressions == _plan("Idol-Pop", 4, False).progressions
    # Band: J-Pop mit Riff, Powerchords und Rock-Grooves, Idol mit Rufen und Synth-Bläsern, andere Stile wie bisher
    jpop, idol = style_dna.split(get_style("J-Pop Energy")), style_dna.split(get_style("Idol-Pop"))
    assert jpop.part("Verse", "guitar") == "riff" and jpop.part("Chorus", "guitar") == "power_chords"
    assert jpop.part("Chorus", "bells") is None and jpop.groove("Chorus") == "rock_chorus"
    assert idol.part("PreChorus", "choir") == "calls" and idol.program("brass") == 62
    assert style_dna.split(get_style("Rock")) is get_style("Rock")
    assert song_character.choose("J-Pop Energy", "abc") == song_character.choose("J-Pop Energy", "abc", split=False)
    for seed in "abcdefgh":
        c = song_character.choose("J-Pop Energy", seed, split=True)
        assert c.grooves["Chorus"] in ("rock_chorus", "two_beat") and c.patterns["Chorus"]["guitar"] == "power_chords"
        assert song_character.choose("Idol-Pop", seed, split=True).programs["brass"] in (62, 63)
    # im Song: J-Pop spielt das Riff (Grundton-Achtel und ein Lauf im vierten Schlag), Idol ruft vor dem Refrain
    s = SongSettings(output_ordner=str(tmp_path), seed=7, style="J-Pop Energy", bpm=150)
    on, _ = pipeline.compose(s)
    off, _ = pipeline.compose(s.with_updates(jpop_idol_split=False))
    assert on["plan"].style.part("Verse", "guitar") == "riff" and off["plan"].style.part("Verse", "guitar") != "riff"
    assert not _royal(on["plan"].progressions["Chorus"])
    verse = next(sec for sec in on["plan"].sections if sec.kind == "Verse")
    spb = 60 / 150
    lick = [n for n in on["guitar"] if verse.start * spb + 3 * spb - 0.05 <= n.start < verse.start * spb + 4 * spb - 0.05]
    assert len(lick) >= 4
    s = s.with_updates(style="Idol-Pop")
    on, _ = pipeline.compose(s)
    off, _ = pipeline.compose(s.with_updates(jpop_idol_split=False))
    pre = next(sec for sec in on["plan"].sections if sec.kind == "PreChorus")
    calls = [n for n in on["choir"] if pre.start * spb <= n.start < pre.end * spb and n.end - n.start < 0.2]
    assert len(calls) >= 8 and not [n for n in off["choir"] if pre.start * spb <= n.start < pre.end * spb]
    assert SongSettings().jpop_idol_split


# ── C2 Produzenten-Profil ────────────────────────────────────────────────────────
def test_the_producer_profile_signs_every_song(new_150, tmp_path):
    import casting
    import produzent
    import tags
    import youtube
    s = SongSettings(output_ordner=str(tmp_path), seed=7, style="Rock", producer_name="StrikerP")
    found = produzent.profile(s)
    assert found.tag and found.sound in produzent.SOUNDS.values() and not found.turn
    assert produzent.profile(SongSettings()) is None, "ohne Namen und Auswahl ändert sich nichts"
    assert produzent.profile(s.with_updates(producer_profile=False)) is None
    assert not produzent.profile(s.with_updates(producer_tag=False)).tag
    # der Tag: für denselben Namen immer dieselben vier Töne, in der Tonart des Songs
    assert produzent.motif("StrikerP") == produzent.motif(" strikerp")
    assert len({tuple(produzent.motif(n)) for n in ("StrikerP", "Mika", "Nanashi", "Yuki", "Kaito")}) >= 4
    in_c, in_d = produzent.tag_notes(found, 0, "major"), produzent.tag_notes(found, 2, "major")
    assert len(in_c) == 4 and all((d[1] - c[1]) % 12 == 2 for c, d in zip(in_c, in_d))
    assert all(p % 12 in (0, 2, 4, 5, 7, 9, 11) for _, p, _, _ in in_c)
    # im Song: die Glocken spielen den Tag am Anfang im Erkennungsklang
    spb = 60 / s.bpm
    on, _ = pipeline.compose(s)
    off, _ = pipeline.compose(s.with_updates(producer_profile=False))
    early = lambda tracks: sorted((round(n.start / spb, 2), n.pitch) for n in tracks["bells"] if n.start < 2.1 * spb)
    tag = [(round(at, 2), p) for at, p, _, _ in produzent.tag_notes(found, on["plan"].tonic, on["plan"].mode)]
    added = sorted(set(early(on)) - set(early(off)))           # die Band spielt ihn mit ihrem Timing
    assert [p for _, p in added] == [p for _, p in tag] and all(abs(a - b) < 0.06 for (a, _), (b, _) in zip(added, tag))
    assert on["plan"].style.program("bells") == found.sound and off["plan"].style.program("bells") != found.sound
    assert early(pipeline.compose(s.with_updates(producer_tag=False))[0]) == early(off)
    # die Akkordwendung: der Refrain spielt sie in etwa zwei von drei Songs
    turned = s.with_updates(producer_turn="Komuro (vi–IV–V–I)")
    profile = produzent.profile(turned)
    hits = sum(bool(produzent.turn(profile, "major", f"song{k}")) for k in range(90))
    assert 45 <= hits <= 75
    assert produzent.turn(profile, "minor", next(f"song{k}" for k in range(90)
                                                 if produzent.turn(profile, "major", f"song{k}"))) == "i | bVI | bVII | bIII"
    plan = build_plan(get_style("Rock"), 140, STRUCTURE, "C", "major", config.SECTION_CONFIG, random.Random(1), {},
                      own_chords=True, turn="vi | IV | V | I")
    assert plan.progressions["Chorus"] == "vi | IV | V | I"
    chorus = next(sec for sec in plan.sections if sec.kind == "Chorus")
    assert [slot.chord.root for slot in chorus.chords[:4]] == [9, 5, 7, 0]
    # Name im Abspann, in der Beschreibung und als Künstler der MP3
    result = pipeline.SongResult(seed=1, output_dir=str(tmp_path), settings=s)
    assert "Produziert von StrikerP" in youtube.credits(result)
    assert "Produziert von StrikerP" in youtube.description(result, "Titel")
    assert tags.artist(s) == "StrikerP feat. MERROW"
    assert tags.artist(s.with_updates(producer_profile=False)) == "Vloid Songs feat. MERROW"
    assert "Produziert" not in youtube.description(pipeline.SongResult(seed=1, output_dir=str(tmp_path),
                                                                      settings=SongSettings()), "Titel")
    # Lieblingsstimme für alle Stile, wenn der Stil keine eigene hat
    root = tmp_path / "NEUTRINO"
    for singer in ("MERROW", "REINA", "SOMA"):
        (root / "model" / singer).mkdir(parents=True)
    v = SongSettings(neutrino_pfad=str(root), style="Rock", singer="MERROW", producer_singer="SOMA")
    assert casting.favorite(v).singer == "SOMA"
    assert casting.favorite(v.with_updates(style_singers={"Rock": "REINA"})).singer == "REINA"
    assert casting.favorite(v.with_updates(producer_profile=False)).singer == "MERROW"


# ── C3 Geschmack lernen ──────────────────────────────────────────────────────────
def test_thumbs_in_the_history_teach_the_dice(new_150, tmp_path):
    import casting
    import geschmack
    import history
    out = tmp_path / "songs"
    out.mkdir()
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"x")
    root = tmp_path / "NEUTRINO"
    for singer in ("MERROW", "SOMA"):
        (root / "model" / singer).mkdir(parents=True)
    s = SongSettings(output_ordner=str(out), style="City Pop", seed=1, singer="SOMA", neutrino_pfad=str(root))
    liked = song_character.choose("City Pop", "a")
    plan = _plan("City Pop", 2, False)
    character = pipeline.song_character({"character": liked, "plan": plan})
    assert character["chords"]["Chorus"] == plan.progressions["Chorus"] and character["programs"] == liked.programs
    entry = history.record(str(audio), s, str(out), character=character)
    assert geschmack.load(s) is None, "ohne Daumen würfelt alles wie bisher"
    history.set_thumb(entry, "klang", 1)
    history.set_thumb(entry, "groove", -1)
    history.set_thumb(entry, "melodie", 1)
    history.set_thumb(entry, "stimme", 1)
    entry = history.entries(str(out))[0]
    assert entry.thumbs == {"klang": 1, "groove": -1, "melodie": 1, "stimme": 1} and entry.character == character
    taste = geschmack.load(s)
    piano, verse = liked.programs["piano"], liked.grooves["Verse"]
    assert taste.weight(("program", "piano", piano)) > 1 > taste.weight(("groove", "Verse", verse))
    # die Würfel: der gemochte Klang kommt öfter, der Groove mit Daumen runter seltener
    seeds = [f"song{k}" for k in range(150)]
    plain = [song_character.choose("City Pop", k) for k in seeds]
    tasted = [song_character.choose("City Pop", k, taste=taste) for k in seeds]
    assert sum(c.programs["piano"] == piano for c in tasted) > 1.3 * sum(c.programs["piano"] == piano for c in plain)
    assert sum(c.grooves["Verse"] == verse for c in tasted) < 0.8 * sum(c.grooves["Verse"] == verse for c in plain)
    assert song_character.choose("City Pop", "q", taste=geschmack.Taste()) == song_character.choose("City Pop", "q")
    # Melodie: die Akkordfolge des Refrains kommt öfter
    chorus = plan.progressions["Chorus"]
    count = lambda t: sum(build_plan(get_style("City Pop"), 120, STRUCTURE, "C", "major", config.SECTION_CONFIG,
                                     random.Random(k), {}, own_chords=True, taste=t).progressions["Chorus"] == chorus
                          for k in range(200))
    assert count(taste) > 1.25 * count(None)
    # Stimme: ist für den Stil keine gemerkt, singt die mit den meisten Daumen hoch
    assert taste.singer("City Pop") == "SOMA" and taste.singer("Rock") == "SOMA"
    assert casting.favorite(s.with_updates(singer="MERROW")).singer == "SOMA"
    assert casting.favorite(s.with_updates(singer="MERROW", taste_learning=False)).singer == "MERROW"
    # ein neuer Song merkt sich den Geschmack, mit dem er entsteht; derselbe Seed bleibt derselbe Song
    fresh = pipeline.with_taste(s.with_updates(seed=None))
    assert geschmack.from_snapshot(fresh.taste_snapshot).scores == taste.scores
    assert pipeline.with_taste(s) is s and pipeline.with_taste(s.with_updates(seed=None), seed=5).taste_snapshot == []
    assert pipeline.with_taste(s.with_updates(seed=None, taste_learning=False)).taste_snapshot == []
    assert pipeline.composition_extras(fresh)["taste"].scores == taste.scores
    assert "taste" not in pipeline.composition_extras(s)
    assert "taste" not in pipeline.composition_extras(fresh.with_updates(taste_learning=False))
    restored = SongSettings.model_validate_json(fresh.model_dump_json())
    assert pipeline.composition_extras(restored)["taste"].scores == taste.scores
    # fällt der Song aus dem Verlauf, bleibt sein Geschmack
    for k in range(2):
        history.record(str(audio), s.with_updates(seed=10 + k), str(out), keep=1)
    assert len(history.entries(str(out))) == 1 and entry.info not in [e.info for e in history.entries(str(out))]
    kept = geschmack.load(s)
    assert kept.scores == taste.scores and kept.singer("City Pop") == "SOMA"


# ── C4 Stile mischen ─────────────────────────────────────────────────────────────
def test_two_styles_blend_with_a_share(new_150, tmp_path):
    rock, kawaii = get_style("Rock"), get_style("Kawaii Chiptune")
    mixed, taken, moved = style_dna.blend(rock, kawaii, 0.3, "seed1")
    assert 1 <= len(taken) <= 4 and all(kawaii.parts["Chorus"].get(inst) for inst in taken)
    for inst in taken:
        assert mixed.part("Chorus", inst) == kawaii.part("Chorus", inst)
        assert mixed.part("Verse", inst) == kawaii.part("Verse", inst)
        if inst in kawaii.programs:
            assert mixed.program(inst) == kawaii.program(inst)
    kept = [inst for inst in style_dna.BLEND_PARTS if inst not in taken]
    assert all(mixed.part("Chorus", inst) == rock.part("Chorus", inst) for inst in kept)
    assert all(mixed.grooves[sec] == kawaii.grooves[sec] for sec in moved)
    assert style_dna.blend(rock, kawaii, 0.3, "seed1")[1] == taken, "derselbe Seed mischt gleich"
    # mehr Anteil, mehr vom zweiten Stil (über viele Songs)
    few = sum(len(style_dna.blend(rock, kawaii, 0.1, f"s{k}")[1]) for k in range(30))
    many = sum(len(style_dna.blend(rock, kawaii, 0.5, f"s{k}")[1]) for k in range(30))
    assert many > 2 * few
    # Akkorde: bei 50 % kommt etwa jede zweite Folge aus dem zweiten Stil
    city = style_dna.PROGRESSIONS["City Pop"]["major"]
    hits = 0
    for k in range(40):
        plan = build_plan(rock, 120, STRUCTURE, "C", "major", config.SECTION_CONFIG, random.Random(k), {},
                          own_chords=True, blend=("City Pop", 0.5, f"song{k}"))
        hits += sum(plan.progressions[kind] in city.get(kind, ()) for kind in ("Verse", "PreChorus", "Chorus"))
    assert 30 <= hits <= 90
    # im Song, nur mit Schalter und zweitem Stil
    s = SongSettings(output_ordner=str(tmp_path), seed=11, style="Rock", blend_style="Kawaii Chiptune",
                     blend_share=0.4)
    assert pipeline.composition_extras(s)["blend"] == ("Kawaii Chiptune", 0.4)
    assert "blend" not in pipeline.composition_extras(s.with_updates(style_blend=False))
    assert "blend" not in pipeline.composition_extras(s.with_updates(blend_style=""))
    assert "blend" not in pipeline.composition_extras(s.with_updates(blend_style="Rock"))
    on, _ = pipeline.compose(s)
    off, _ = pipeline.compose(s.with_updates(style_blend=False))
    plain, _ = pipeline.compose(s.with_updates(blend_style=""))
    assert on["plan"].style.parts != off["plan"].style.parts
    assert off["plan"].style.parts == plain["plan"].style.parts
    assert [(n.start, n.pitch) for n in off["bass"]] == [(n.start, n.pitch) for n in plain["bass"]]
