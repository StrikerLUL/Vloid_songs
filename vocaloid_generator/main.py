# main.py – Erzeugt einen kompletten Song ohne Oberfläche.
# Nutzt dieselben Einstellungen wie die App; einzelne Werte lassen sich per Option überschreiben.
import argparse
import logging
import os
import sys

import applog
import history
import userdata
from pipeline import (best, draft_settings, from_references, generate_song, generate_variants, hook_choices,
                      hook_kind, lyric_video)
from settings import KEYS, REROLLABLE, ReferenceTrack, SongSettings, is_rerollable
from styles import STYLES

log = logging.getLogger("vocaloid")


def _rerollable(text: str) -> str:
    if not is_rerollable(text):
        raise argparse.ArgumentTypeError(f"unbekannter Teil: {text}")
    return text


def _custom_chords(text: str) -> tuple:
    import config
    from song_plan import check_custom
    kind, sep, chords = text.partition("=")
    if not sep or kind not in config.SECTION_CONFIG:
        raise argparse.ArgumentTypeError(f"erwartet SEKTION=AKKORDE, z. B. 'Chorus=F G Em Am': {text}")
    error = check_custom(chords) if chords.strip() else ""
    if error:
        raise argparse.ArgumentTypeError(error)
    return kind, chords


def _section_bars(text: str) -> tuple:
    import config
    from settings import MAX_BARS, MIN_BARS
    kind, _, bars = text.partition("=")
    if kind not in config.SECTION_CONFIG or not bars.isdigit() or not MIN_BARS <= int(bars) <= MAX_BARS:
        raise argparse.ArgumentTypeError(f"erwartet SEKTION=TAKTE ({MIN_BARS} bis {MAX_BARS}), z. B. 'Chorus=8': {text}")
    return kind, int(bars)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Vocaloid Song Generator: erzeugt MIDI-Spuren, Gesang und eine fertige MP3.")
    p.add_argument("--settings", help="Einstellungsdatei (Standard: die Einstellungen der App)")
    p.add_argument("--seed", type=int, help="gleicher Seed = gleicher Song")
    p.add_argument("--bpm", type=int)
    p.add_argument("--style", help="Preset-Stil, z. B. 'J-Pop Energy', 'Rock', 'Kawaii Chiptune'")
    p.add_argument("--key", choices=KEYS)
    p.add_argument("--scale", choices=["minor", "major", "dorian", "phrygian"])
    p.add_argument("--output", help="Ausgabeordner")
    p.add_argument("--stimme", metavar="NAME", help="NEUTRINO-Stimme, z. B. MERROW")
    p.add_argument("--duett", metavar="NAME", help="zweite NEUTRINO-Stimme fürs Duett ('' = kein Duett)")
    p.add_argument("--support-stimme", metavar="NAME", help="NEUTRINO-Stimme, die als Support-Modell die Hauptstimme "
                   "färbt (Versuch, braucht Run_support_model.bat; '' = aus)")
    p.add_argument("--engine", choices=["NEUTRINO", "VOICEVOX", "Vorschau"], help="wer singt")
    p.add_argument("--voicevox-stimme", type=int, metavar="ID", help="VOICEVOX-Singstimme (Stil-ID)")
    p.add_argument("--ohne-voicevox-dynamik", action="store_true", help="VOICEVOX singt gleich laut; Silben und Phrasen werden erst danach lauter und leiser")
    p.add_argument("--fassungen", type=int, choices=[1, 2, 3], help="NEUTRINO singt so oft, die sauberste zählt")
    p.add_argument("--album", type=int, metavar="N",
                   help="Album über Nacht: N Songs (bis 30) am Stück, nach Note sortiert in Alben\\<Datum> <Name>")
    p.add_argument("--album-stile", type=lambda v: [x.strip() for x in v.split(",") if x.strip()], metavar="STILE",
                   help="Stile für --album, reihum, z. B. 'Rock,Ballade' (ohne: der eingestellte Stil)")
    p.add_argument("--album-texte", metavar="ORDNER", help="Liedtexte für --album: eine .txt pro Song")
    p.add_argument("--album-name", metavar="NAME", default="", help="Name des Albums (ohne: Nacht <Datum>)")
    p.add_argument("--album-gleich", action="store_true",
                   help="alle Album-Songs in Tonart und Tempo des Stils, statt sie leicht zu ändern")
    p.add_argument("--entwurf", action="store_true",
                   help="schneller Entwurf ohne Gesang-Synthese: die Lead-Stimme spielt die Melodie (Ordner Entwurf)")
    p.add_argument("--vibrato", type=float, metavar="X", help="0 = gerade Töne, 1 = wie gesungen, 2 = doppelt")
    p.add_argument("--uebergaenge", type=float, metavar="X",
                   help="Übergänge zwischen Tönen: 0 = springen, 1 = wie gesungen, 2 = doppelt so lang")
    p.add_argument("--ohne-psola", action="store_true",
                   help="Vibrato und Übergänge mit dem WORLD-Vocoder statt mit Praat-PSOLA ändern")
    p.add_argument("--ohne-atmer", action="store_true", help="kein Einatmen vor den Phrasen")
    p.add_argument("--ohne-echo", action="store_true", help="kein Echo auf dem letzten Wort")
    p.add_argument("--ohne-chor", action="store_true", help="kein Chor im letzten Refrain")
    p.add_argument("--ohne-comping", action="store_true",
                   help="bei mehreren Fassungen die sauberste ganze statt jeder Phrase aus der saubersten")
    p.add_argument("--ohne-ausdruck", action="store_true", help="kein Ausdruck pro Phrase (Lautstärke, Helligkeit)")
    p.add_argument("--ohne-gesangskette", action="store_true",
                   help="ohne Sättigung, Hall und Delay je Sektion und echte Doppelung für den Gesang")
    p.add_argument("--ohne-stimmkette", action="store_true",
                   help="dieselbe Gesangskette für jede Stimme und jeden Stil (wie bis 1.0)")
    p.add_argument("--ohne-airwindows", action="store_true",
                   help="Airwindows Consolidated nicht benutzen, auch wenn es eingerichtet ist")
    p.add_argument("--ohne-telefon", action="store_true", help="die erste Zeile nicht wie durchs Telefon")
    p.add_argument("--ohne-stutter", action="store_true", help="kein Stottern der Stimme vor dem Refrain")
    p.add_argument("--ohne-hardtune", action="store_true", help="kein harter Tune im Refrain")
    p.add_argument("--ohne-formant", action="store_true", help="die Formanten der Stimme nicht verschieben")
    p.add_argument("--ohne-gesangsswing", action="store_true", help="der Gesang bleibt gerade, auch wenn die Band swingt")
    p.add_argument("--ohne-romaji", action="store_true", help="Romaji im Liedtext nicht japanisch singen")
    p.add_argument("--ohne-haltezeichen", action="store_true", help="lange Vokale für NEUTRINO nicht als ー schreiben")
    p.add_argument("--ohne-atemzeichen", action="store_true", help="keine Atemzeichen in langen Zeilen")
    p.add_argument("--ohne-doppelvokale", action="store_true", help="schnelle Töne nicht auf einem Ton zusammenlegen")
    p.add_argument("--ohne-englisch", action="store_true", help="englische Wörter nicht als Katakana singen")
    p.add_argument("--ohne-singbarkeit", action="store_true",
                   help="die Melodie nicht auf Sprünge, Spitzen auf Sechzehnteln und Atempausen prüfen")
    p.add_argument("--ohne-sektions-stil", action="store_true",
                   help="Strophe und Refrain mit demselben StyleShift singen")
    p.add_argument("--strophe-stil", type=int, choices=range(-3, 4), metavar="-3..3",
                   help="StyleShift der Strophen zum StyleShift dazu (Standard -1)")
    p.add_argument("--refrain-stil", type=int, choices=range(-3, 4), metavar="-3..3",
                   help="StyleShift der Refrains zum StyleShift dazu (Standard +1)")
    p.add_argument("--ohne-harmonie-wechsel", action="store_true",
                   help="in jedem Refrain dieselbe Harmonie (die Terz darüber), keine Oktave")
    p.add_argument("--ohne-doppel-harmonie", action="store_true", help="die zweite Stimme nur einmal singen")
    p.add_argument("--ohne-flaechen", action="store_true", help="keine gesungenen Flächen im Refrain")
    p.add_argument("--ohne-adlibs", action="store_true", help="keine Ad-libs im letzten Refrain")
    p.add_argument("--ohne-echte-atmer", action="store_true",
                   help="Atmer aus Rauschen, auch wenn im Ordner Atmer Aufnahmen liegen")
    p.add_argument("--ohne-silben-lautstaerke", action="store_true",
                   help="alle Silben gleich laut (keine Betonung, kein weicher Einsatz)")
    p.add_argument("--ohne-platte", action="store_true",
                   help="Gesangshall wie bisher (Algorithmus) statt der Platte aus einer Impulsantwort")
    p.add_argument("--ohne-delay-ducking", action="store_true",
                   help="das Gesangs-Delay nicht leiser machen, solange gesungen wird")
    p.add_argument("--ohne-platz", action="store_true",
                   help="die Band macht dem Gesang keinen Platz (keine Absenkung in seinen Frequenzen)")
    p.add_argument("--ohne-nachfuehren", action="store_true",
                   help="die Lautstärke des Gesangs nicht auf der Band nachführen")
    p.add_argument("--ohne-gleiche-fassungen", action="store_true",
                   help="Fassungen eine Stufe heller und dunkler singen und nach jeder Abweichung werten")
    p.add_argument("--schlagzeug", choices=["soundfont", "808", "909"],
                   help="Klang des Schlagzeugs: SoundFont oder Drum-Machine (sonst wie der Stil)")
    p.add_argument("--ohne-verstaerker", action="store_true",
                   help="verzerrte Gitarren aus dem SoundFont statt über Verstärker und Box")
    p.add_argument("--box", metavar="WAV", help="Impulsantwort einer Gitarrenbox")
    p.add_argument("--ohne-samples", action="store_true",
                   help="Orchester aus dem SoundFont statt aus den echten Aufnahmen (setup_samples.py)")
    p.add_argument("--ohne-echtes-schlagzeug", action="store_true",
                   help="Schlagzeug aus dem SoundFont statt aus dem DRS Kit (setup_drums.py)")
    p.add_argument("--ohne-echte-grooves", action="store_true",
                   help="eingebaute Schlagzeug-Muster statt Grooves echter Schlagzeuger (setup_grooves.py)")
    p.add_argument("--ohne-bass-leben", action="store_true", help="Bass ohne Ghost-Notes und Slides")
    p.add_argument("--ohne-anschlagmuster", action="store_true",
                   help="Gitarre schlägt immer dasselbe Muster an statt je nach Teil")
    p.add_argument("--ohne-lofi-klang", action="store_true", help="Lo-Fi ohne Knistern und Bandmaschine")
    p.add_argument("--ohne-bewegung", action="store_true",
                   help="Mix ohne Anlauf vor dem Refrain, Hall pro Sektion und breitere Refrains")
    p.add_argument("--ohne-veredler", action="store_true",
                   help="keine zweite Fassung mit von ACE-Step veredelter Band (setup_ace_step.py)")
    p.add_argument("--veredler-staerke", type=float, metavar="0.1-0.9",
                   help="wie viel ACE-Step am Klang der Band ändert (Standard 0.4)")
    p.add_argument("--veredler-klang", metavar="TEXT", help="Klangbeschreibung für ACE-Step auf Englisch")
    p.add_argument("--vorbild", action="append", metavar="DATEI",
                   help="Vorbild-Song (mehrfach möglich); ersetzt die Vorbilder aus den Einstellungen")
    p.add_argument("--ki-begleitung", action="store_true",
                   help="die Begleitstimmen schreibt der Anticipatory Music Transformer (setup_begleitung.py, Versuch)")
    p.add_argument("--ohne-ki-begleitung", action="store_true", help="die komponierte Begleitung, auch wenn die "
                   "KI-Begleitung in den Einstellungen an ist")
    p.add_argument("--ohne-vorbild-gruppen", action="store_true",
                   help="Gesang, Schlagzeug, Bass und Rest nicht einzeln an die Vorbilder angleichen (Demucs)")
    p.add_argument("--ohne-vorbild-gesangsklang", action="store_true",
                   help="die Klangkurve des Gesangs nicht an den Gesang der Vorbilder angleichen")
    p.add_argument("--vom-vorbild", action="store_true",
                   help="Tempo, Tonart und Stil der Vorbilder übernehmen (soweit in den Einstellungen erlaubt)")
    p.add_argument("--lautheit", type=float, metavar="LUFS", help="Ziel-Lautheit des Masters, z. B. -14 für YouTube")
    p.add_argument("--verlauf", nargs="?", const="", metavar="SUCHE",
                   help="die Songs im Verlauf auflisten und beenden; mit SUCHE nur passende (Name, Notiz, Stil, Seed)")
    p.add_argument("--sortieren", choices=list(history.SORTS), default="neu",
                   help="Reihenfolge für --verlauf: neu, bewertung (beste Note zuerst) oder name")
    p.add_argument("--aus-verlauf", type=int, metavar="NR",
                   help="Einstellungen und Seed eines Songs aus dem Verlauf nehmen (1 = der neueste)")
    p.add_argument("--neu", action="append", type=_rerollable, metavar="TEIL[:SEKTION]",
                   help="nur diesen Teil neu würfeln, der Rest bleibt (mehrfach möglich): " + ", ".join(REROLLABLE)
                   + "; mit :SEKTION nur dort, z. B. melody:Chorus. Ohne --seed und --aus-verlauf gilt der letzte Song.")
    p.add_argument("--refrains", type=int, metavar="N",
                   help="N neue Refrain-Melodien als kurze Vorschau (WAV) schreiben, ohne den ganzen Song")
    p.add_argument("--casting", action="store_true",
                   help="Stimmen-Casting: den Refrain-Hook mit jeder installierten NEUTRINO-Stimme singen (WAVs)")
    p.add_argument("--refrain", type=int, metavar="NR",
                   help="den ganzen Song mit dieser Refrain-Melodie erzeugen (Nummer aus der Ausgabe von --refrains, "
                        "mit demselben --seed)")
    p.add_argument("--akkorde", action="append", type=_custom_chords, metavar="SEKTION=AKKORDE",
                   help="eigene Akkorde, z. B. 'Chorus=F G Em Am' oder 'Verse=vi IV I V' (mehrfach möglich, "
                        "'Chorus=' nimmt wieder die des Stils)")
    p.add_argument("--melodie-midi", metavar="DATEI", help="eigene Melodie als MIDI-Datei ('' = komponieren)")
    p.add_argument("--eigener-gesang", metavar="WAV",
                   help="eigene Gesangsspur statt der Hauptstimme, z. B. aus dem NEUTRINO-Tuning-Tool ('' = die "
                        "Engine singt)")
    p.add_argument("--ohne-ausrichten", action="store_true",
                   help="die eigene Gesangsspur nicht an den Noten ausrichten (sie beginnt mit dem Song)")
    p.add_argument("--noten-zip", metavar="DATEI",
                   help="die Noten des Gesangs für Tuning-Tools als ZIP exportieren (MusicXML, UST, MIDI)")
    p.add_argument("--summen", metavar="AUFNAHME",
                   help="eine gesummte Melodie (WAV, MP3 …) in Noten verwandeln und singen lassen")
    p.add_argument("--takte", action="append", type=_section_bars, metavar="SEKTION=N",
                   help="Länge einer Sektion in Takten, z. B. 'Chorus=8' (mehrfach möglich)")
    p.add_argument("--youtube", nargs="?", const="", metavar="TITEL",
                   help="danach MP3, Video, Titelbild und Beschreibung in einen Ordner unter YouTube legen")
    p.add_argument("--lyric-video", nargs="?", const="", metavar="DATEI",
                   help="dazu ein Lyric-Video (MP4) mit dem Text zum Mitlesen; ohne DATEI neben dem Song")
    p.add_argument("--melodie-sektion", metavar="SEKTION", help="dort singt die eigene Melodie (Standard: Chorus)")
    p.add_argument("--motive", metavar="ORDNER", help="Rhythmen und Gesten aus den MIDI-Melodien in diesem Ordner lernen")
    p.add_argument("--ohne-motive", action="store_true",
                   help="nur die alten eingebauten Rhythmen und Gesten (ohne zusätzliche und gelernte)")
    p.add_argument("--ohne-bewertung", action="store_true",
                   help="mehrere Fassungen nicht automatisch bewerten (sonst mit setup_bewertung.py)")
    p.add_argument("--varianten", type=int, default=1, metavar="N",
                   help="N Songs am Stück erzeugen; mit --neu N Fassungen der gewählten Teile")
    p.add_argument("--zip", metavar="DATEI", help="den Song mit allen Spuren als ZIP für eine DAW exportieren")
    p.add_argument("--ohne-wiederverwenden", action="store_true",
                   help="alles neu berechnen, auch wenn Gesang und Spuren vom letzten Mal passen würden")
    p.add_argument("--system-pruefen", action="store_true",
                   help="jeden Baustein kurz echt ausprobieren (Instrumente, NEUTRINO, MP3, ... und ein kurzer Song)")
    p.add_argument("--gruendlich", action="store_true",
                   help="mit --system-pruefen: auch ACE-Step und die KI-Begleitung ausprobieren")
    p.add_argument("--fehlerbericht", nargs="?", const="", metavar="DATEI",
                   help="Protokolle, Einstellungen und Systeminfo als ZIP speichern (ohne Songs) und beenden")
    p.add_argument("--einrichten", metavar="TEILE",
                   help="Klänge und Modelle laden: 'alles' (was noch fehlt) oder z. B. 'soundfonts,samples'")
    p.add_argument("-v", "--verbose", action="store_true", help="alle Details ausgeben")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    userdata.migrate()

    settings = SongSettings.load(args.settings)
    _logging(settings.log_file, args.verbose)
    overrides = {"output_ordner": args.output, "reuse_steps": False if args.ohne_wiederverwenden else None}
    settings = settings.with_updates(**{k: v for k, v in overrides.items() if v is not None})

    if args.verlauf is not None:
        return _list_history(settings, args.verlauf, args.sortieren)
    if args.fehlerbericht is not None:
        import fehlerbericht
        log.info("Fehlerbericht: %s", fehlerbericht.save(args.fehlerbericht or None, settings))
        return 0
    if args.einrichten:
        return _setup(args.einrichten)
    if args.system_pruefen:
        return _check(settings, args.gruendlich)
    if args.aus_verlauf or (args.neu and args.seed is None):
        settings = _from_history(settings, args.aus_verlauf or 1)
        if settings is None:
            return 1

    if args.vorbild:
        settings = settings.with_updates(reference_tracks=[ReferenceTrack(path=p).model_dump() for p in args.vorbild])
    if args.vom_vorbild:
        settings = from_references(settings)
    overrides = {"seed": args.seed, "bpm": args.bpm, "style": args.style, "key": args.key, "scale": args.scale,
                 "singer": args.stimme, "duet_singer": args.duett, "support_singer": args.support_stimme, "master_lufs": args.lautheit,
                 "vocal_engine": args.engine, "voicevox_singer": args.voicevox_stimme,
                 "voicevox_dynamics": False if args.ohne_voicevox_dynamik else None, "vocal_takes": args.fassungen,
                 "vibrato": args.vibrato, "glide": args.uebergaenge,
                 "psola_reshape": False if args.ohne_psola else None,
                 "breaths": False if args.ohne_atmer else None, "echo_throws": False if args.ohne_echo else None,
                 "final_choir": False if args.ohne_chor else None,
                 "vocal_comping": False if args.ohne_comping else None,
                 "phrase_expression": False if args.ohne_ausdruck else None,
                 "vocal_chain": False if args.ohne_gesangskette else None,
                 "vocal_tone": False if args.ohne_stimmkette else None,
                 "airwindows": False if args.ohne_airwindows else None,
                 "telephone_fx": False if args.ohne_telefon else None,
                 "stutter_fx": False if args.ohne_stutter else None,
                 "hard_tune": False if args.ohne_hardtune else None,
                 "formant_fx": False if args.ohne_formant else None,
                 "vocal_swing": False if args.ohne_gesangsswing else None,
                 "romaji": False if args.ohne_romaji else None,
                 "long_vowel_mark": False if args.ohne_haltezeichen else None,
                 "breath_marks": False if args.ohne_atemzeichen else None,
                 "fast_diphthongs": False if args.ohne_doppelvokale else None,
                 "english_kana": False if args.ohne_englisch else None,
                 "singable_melody": False if args.ohne_singbarkeit else None,
                 "section_style": False if args.ohne_sektions_stil else None,
                 "verse_style_shift": args.strophe_stil, "chorus_style_shift": args.refrain_stil,
                 "even_takes": False if args.ohne_gleiche_fassungen else None,
                 "harmony_variety": False if args.ohne_harmonie_wechsel else None,
                 "harmony_double": False if args.ohne_doppel_harmonie else None,
                 "sung_pads": False if args.ohne_flaechen else None,
                 "adlibs": False if args.ohne_adlibs else None,
                 "syllable_dynamics": False if args.ohne_silben_lautstaerke else None,
                 "recorded_breaths": False if args.ohne_echte_atmer else None,
                 "convolution_reverb": False if args.ohne_platte else None,
                 "ducked_delay": False if args.ohne_delay_ducking else None,
                 "vocal_unmask": False if args.ohne_platz else None,
                 "vocal_ride": False if args.ohne_nachfuehren else None,
                 "guitar_amp": False if args.ohne_verstaerker else None, "cabinet_ir": args.box,
                 "samples": False if args.ohne_samples else None,
                 "real_drums": False if args.ohne_echtes_schlagzeug else None,
                 "real_grooves": False if args.ohne_echte_grooves else None,
                 "lively_bass": False if args.ohne_bass_leben else None,
                 "guitar_strums": False if args.ohne_anschlagmuster else None,
                 "auto_rating": False if args.ohne_bewertung else None,
                 "lofi_texture": False if args.ohne_lofi_klang else None,
                 "mix_movement": False if args.ohne_bewegung else None,
                 "ref_stems": False if args.ohne_vorbild_gruppen else None,
                 "ref_vocal_curve": False if args.ohne_vorbild_gesangsklang else None,
                 "ai_accompaniment": False if args.ohne_ki_begleitung else (True if args.ki_begleitung else None),
                 "polish": False if args.ohne_veredler else None, "polish_strength": args.veredler_staerke,
                 "polish_caption": args.veredler_klang,
                 "melody_midi": args.melodie_midi, "melody_midi_section": args.melodie_sektion,
                 "own_vocal": args.eigener_gesang, "own_vocal_align": False if args.ohne_ausrichten else None,
                 "motif_folder": args.motive,
                 "more_motifs": False if args.ohne_motive else None,
                 "learned_motifs": False if args.ohne_motive else None}
    if args.akkorde:
        overrides["custom_chords"] = {**settings.custom_chords, **dict(args.akkorde)}
    if args.takte:
        overrides["section_bars"] = {**settings.section_bars, **dict(args.takte)}
    if args.refrain:
        overrides["variations"] = {**settings.variations, f"melody:{hook_kind(settings)}": args.refrain}
    if args.schlagzeug:
        channels = {ch: data.model_dump() for ch, data in settings.channels.items()}
        channels["drums"]["style"] = args.schlagzeug
        overrides["channels"] = channels
    settings = settings.with_updates(**{k: v for k, v in overrides.items() if v is not None})
    if args.summen:
        settings = _hummed(settings, args.summen)
        if settings is None:
            return 1
    parts = tuple(args.neu or ())
    if args.style and not args.stimme:
        import casting
        settings = casting.favorite(settings)
    if args.entwurf:
        settings = draft_settings(settings)

    log.info("=== Vocaloid Song Generator ===")
    log.info("Stil: %s | BPM: %d | Tonart: %s %s", settings.style, settings.bpm, settings.key, settings.scale)
    log.info("Struktur: %s", " → ".join(settings.active_sections))

    def progress(f, msg):
        log.info("[%3d%%] %s", round(f * 100), msg)

    if args.refrains:
        return _hooks(settings, args.refrains, progress)
    if args.casting:
        return _casting(settings, progress)
    if args.album:
        return _album(settings.with_updates(album_vary=not args.album_gleich), args, progress)
    try:
        if args.varianten > 1 or parts:
            results = generate_variants(settings, args.varianten, parts, progress=progress)
        else:
            results = [generate_song(settings, progress=progress)]
    except (RuntimeError, ValueError) as e:
        log.error("%s", e)
        return 1

    for result in results:
        log.info("Fertig! Seed %d: %s", result.seed, result.history or result.audio)
        if result.polished_wav:
            log.info("Veredelte Fassung: %s", result.polished_mp3 or result.polished_wav)
    chosen = best(results)
    if chosen.rating:
        log.info("Beste Fassung: Seed %d, %s", chosen.seed, chosen.rating.describe())
    if args.lyric_video is not None:
        try:
            log.info("Lyric-Video: %s", lyric_video(chosen, args.lyric_video or None))
        except RuntimeError as e:
            log.error("%s", e)
            return 1
    if args.youtube is not None:
        import youtube
        try:
            package = youtube.make(chosen, args.youtube)
        except RuntimeError as e:
            log.error("%s", e)
            return 1
        log.info("Fertig für YouTube: %s", package.describe())
    if args.zip:
        from exporter import exportiere_projekt
        log.info("ZIP: %s", exportiere_projekt(chosen, args.zip))
    if args.noten_zip:
        from exporter import exportiere_noten
        log.info("Noten für Tuning-Tools: %s", exportiere_noten(chosen, args.noten_zip))
    return 0


def _quiet(record: logging.LogRecord) -> bool:
    """Im Fenster nur die eigenen Meldungen und Warnungen; die Protokolldatei bekommt alles."""
    return record.levelno >= logging.WARNING or record.name == log.name


def _logging(to_file: bool, verbose: bool) -> None:
    if not verbose:
        for handler in logging.getLogger().handlers:
            if type(handler) is logging.StreamHandler:
                handler.addFilter(_quiet)
    applog.setup(to_file)


def _check(settings: SongSettings, thorough: bool) -> int:
    import systemcheck
    results = systemcheck.run_all(settings, lambda f, m: log.info("[%3d%%] %s", round(f * 100), m), thorough)
    for r in results:
        log.info("%s %s: %s", r.symbol, r.name, r.message)
    log.info("%s", systemcheck.summary(results))
    return 1 if any(r.ok is False for r in results) else 0


def _setup(which: str) -> int:
    import einrichten
    if which.strip().lower() == "alles":
        keys = [c.key for c in einrichten.missing()]
    else:
        keys = [k.strip() for k in which.split(",") if k.strip()]
        unknown = [k for k in keys if einrichten.find(k) is None]
        if unknown:
            log.error("Unbekannt: %s (möglich: %s)", ", ".join(unknown),
                      ", ".join(c.key for c in einrichten.components()))
            return 1
    if not keys:
        log.info("Alles ist schon eingerichtet.")
        return 0
    results = einrichten.install(keys, log.info)
    return 0 if all(results.values()) else 1


def _hummed(settings: SongSettings, recording: str):
    """Die Einstellungen mit der gesummten Melodie als eigener Melodie; None, wenn keine zu hören ist."""
    import humming
    target = humming.target_for(recording, settings.output_dir())
    count = humming.transcribe(recording, settings.bpm, target)
    if not count:
        log.error("In %s ist keine Melodie zu hören", recording)
        return None
    log.info("Gesummte Melodie: %d Töne in %s", count, target)
    return settings.with_updates(melody_midi=target)


def _hooks(settings: SongSettings, count: int, progress) -> int:
    try:
        choices = hook_choices(settings, count, progress)
    except ValueError as e:
        log.error("%s", e)
        return 1
    key = f"melody:{hook_kind(settings)}"
    for choice in choices:
        log.info("Refrain %d: %s  (ganzer Song: --seed %d --refrain %d)", choice.number, choice.preview,
                 choice.settings.seed, choice.settings.variations[key])
    return 0


def _casting(settings: SongSettings, progress) -> int:
    import casting
    try:
        auditions = casting.cast(settings, progress)
    except ValueError as e:
        log.error("%s", e)
        return 1
    for a in auditions:
        log.info("%s: %s", a.singer, a.wav)
    return 0


def _album(settings: SongSettings, args, progress) -> int:
    import album
    unknown = [s for s in args.album_stile or () if s not in STYLES]
    if unknown:
        log.error("Unbekannte Stile: %s. Vorhanden: %s", ", ".join(unknown), ", ".join(STYLES))
        return 1
    try:
        made = album.make(settings, args.album, args.album_stile or [settings.style], args.album_texte or "",
                          progress, args.album_name)
    except ValueError as e:
        log.error("%s", e)
        return 1
    for path in made.files:
        log.info("  %s", os.path.basename(path))
    log.info("Album: %s", made.describe())
    return 0 if made.files else 1


def _list_history(settings: SongSettings, text: str = "", sort: str = "neu") -> int:
    every = history.entries(settings.output_dir())
    if not every:
        log.info("Der Verlauf ist leer.")
    numbers = {e.info: nr for nr, e in enumerate(every, 1)}         # die Nummer für --aus-verlauf
    for entry in history.find(every, text, sort=sort):
        score = f"  Note {entry.score:.1f}" if entry.score is not None else ""
        note = f"  ({entry.note})" if entry.note else ""
        log.info("%2d. %s%s%s%s", numbers[entry.info], "★ " if entry.favorite else "", entry.title, score, note)
    return 0


def _from_history(settings: SongSettings, nr: int):
    found = history.entries(settings.output_dir())
    if not 1 <= nr <= len(found):
        log.error("Im Verlauf gibt es keinen Song Nr. %d (vorhanden: %d).", nr, len(found))
        return None
    entry = found[nr - 1]
    log.info("Aus dem Verlauf: %s", entry.title)
    return entry.restore(settings)


if __name__ == "__main__":
    sys.exit(main())
