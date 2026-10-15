# test_rap.py – Rap- und Sprechteil (v6 Nr. 7)
import io
import json
import os
import random
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import music21
import numpy as np
import pytest
import soundfile as sf

import config
import pipeline
import rap
import vocal_check
import voicevox
from orchestrator import orchestrate_song
from settings import SongSettings
from voicevox import running as real_running

RAP_HZ = 200.0
SPEAKERS = [
    {"name": "四国めたん", "styles": [{"id": 2, "name": "ノーマル", "type": "talk"},
                                      {"id": 3002, "name": "ノーマル", "type": "frame_decode"}]},
    {"name": "ずんだもん", "styles": [{"id": 3, "name": "ノーマル"}]},          # ältere Engines nennen keinen Typ
]
SMALL = set("ゃゅょぁぃぅぇぉ")


class FakeTalk(BaseHTTPRequestHandler):
    """Spricht wie VOICEVOX: eine More pro Kana; Konsonanten sind still, Vokale ein Ton mit RAP_HZ."""
    requests = []

    def log_message(self, *args):
        pass

    def _send(self, code, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/version":
            self._send(200, "0.16.0")
        elif path == "/speakers":
            self._send(200, SPEAKERS)
        else:
            self._send(404, {"detail": "Not Found"})

    def do_POST(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        FakeTalk.requests.append((url.path, int(query["speaker"][0]), query.get("text", [""])[0]))
        if url.path == "/audio_query":
            moras = []
            for c in query["text"][0]:
                if c in SMALL and moras:
                    moras[-1]["text"] += c
                    continue
                vowel = {"ん": "N", "っ": "cl"}.get(c, "a")
                consonant = None if c in "あいうえおんっー" else "k"
                moras.append({"text": c, "consonant": consonant, "consonant_length": 0.06 if consonant else None,
                              "vowel": vowel, "vowel_length": 0.11, "pitch": 5.6})
            self._send(200, {"accent_phrases": [{"moras": moras, "accent": 1, "pause_mora": None}],
                             "speedScale": 1.0, "pitchScale": 0.0, "intonationScale": 1.0, "volumeScale": 1.0,
                             "prePhonemeLength": 0.1, "postPhonemeLength": 0.1, "outputSamplingRate": 24000,
                             "outputStereo": False, "kana": ""})
        elif url.path == "/synthesis":
            rate = body["outputSamplingRate"]
            parts = [np.zeros(int(round(body["prePhonemeLength"] * rate)))]
            for phrase in body["accent_phrases"]:
                for m in phrase["moras"]:
                    parts.append(np.zeros(int(round((m["consonant_length"] or 0.0) * rate))))
                    n = int(round(m["vowel_length"] * rate))
                    parts.append(0.3 * np.sin(2 * np.pi * RAP_HZ * np.arange(n) / rate))
            parts.append(np.zeros(int(round(body["postPhonemeLength"] * rate))))
            buffer = io.BytesIO()
            sf.write(buffer, np.concatenate(parts).astype(np.float32), rate, format="WAV")
            self._send(200, buffer.getvalue(), "audio/wav")


@pytest.fixture
def fake_talk(monkeypatch):
    FakeTalk.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeTalk)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(voicevox, "running", real_running)
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def onsets(audio, rate, threshold=0.05):
    """Wo ein Vokal (Ton) nach Stille beginnt, in Sekunden."""
    loud = np.abs(audio) > threshold
    hop = int(0.002 * rate)
    frames = loud[:len(loud) // hop * hop].reshape(-1, hop).any(axis=1)
    starts = np.flatnonzero(frames[1:] & ~frames[:-1]) + 1
    return starts * hop / rate


# ── Sprechen im Takt ──────────────────────────────────────────────────────────────
def test_every_vowel_starts_on_its_note(fake_talk):
    data = [(None, 4.0), (60, 0.5), (60, 0.5), (60, 0.25), (60, 0.75), (None, 2.0), (62, 0.5), (62, 1.0)]
    silben = ["き", "みゃ", "か", "く", "た", "か"]          # mit Konsonant: vor jedem Vokal ist es still
    spans = [(4.0, 12.0)]
    audio = rap.render(data, silben, 120, spans, fake_talk, 2, 48000, 48000 * 7)
    expected = [2.0, 2.25, 2.5, 2.625, 4.0, 4.25]
    found = onsets(audio, 48000)
    assert len(found) == len(expected) and found == pytest.approx(expected, abs=0.006)
    texts = [r[2] for r in FakeTalk.requests if r[0] == "/audio_query"]
    assert texts == ["きみゃかく", "たか"]                          # zwei Phrasen, getrennt an der Pause


def test_a_phrase_voicevox_reads_differently_is_stretched_to_its_length():
    moras = [{"text": "か", "consonant": "k", "consonant_length": 0.05, "vowel": "a", "vowel_length": 0.1}] * 3
    query = {"accent_phrases": [{"moras": [dict(m) for m in moras], "accent": 1,
                                 "pause_mora": {"text": "、", "vowel": "pau", "vowel_length": 0.3}}]}
    timed, ahead = rap.timed(query, [0.0, 0.25, 0.5, 0.75, 1.0], [0.25] * 5)
    total = sum((m["consonant_length"] or 0) + m["vowel_length"] for p in timed["accent_phrases"] for m in p["moras"])
    assert total == pytest.approx(1.0 + 0.25) and ahead == rap.LEAD
    assert timed["accent_phrases"][0]["pause_mora"] is None
    assert query["accent_phrases"][0]["moras"][0]["vowel_length"] == 0.1          # die Anfrage selbst bleibt


def test_the_engine_gets_rests_where_the_rap_is():
    tracks = {"melody_data": [(60, 1.0), (None, 1.0), (62, 1.0), (64, 1.0), (65, 2.0)],
              "silben": ["あ", "い", "う", "え"]}
    out = rap.without(tracks, [(2.0, 4.0)])
    assert out["melody_data"] == [(60, 1.0), (None, 3.0), (65, 2.0)]
    assert out["silben"] == ["あ", "え"] and tracks["silben"] == ["あ", "い", "う", "え"]


def test_kana_for_voicevox():
    assert [rap._kana(s) for s in ("カ", "きゃ", "ー", "la", "っ", "")] == ["か", "きゃ", "ー", "ら", "っ", "ら"]


def test_talk_voices_are_listed_and_picked(fake_talk):
    assert voicevox.talkers(fake_talk) == {2: "四国めたん (ノーマル)", 3: "ずんだもん (ノーマル)"}
    assert voicevox.pick_talker(fake_talk, 3) == (3, "ずんだもん (ノーマル)")
    assert voicevox.pick_talker(fake_talk, 77)[0] == 2


# ── Komposition ───────────────────────────────────────────────────────────────────
def test_the_rap_is_dense_and_almost_on_one_note():
    random.seed(4)
    tracks = orchestrate_song("J-Pop", 100, ["Verse", "Rap", "Chorus"], "C", "minor", config.SECTION_CONFIG,
                              output_dir=None, lyrics={"Rap": list("きみのなまえをよぶたびにこころのおくがさわぐんだ" * 2)})
    plan, spb = tracks["plan"], 60 / 100
    by_kind = {}
    for n in tracks["vocal_melody"]:
        by_kind.setdefault(plan.section_at(n.start / spb).kind, []).append(n)
    verse, rapped = by_kind["Verse"], by_kind["Rap"]
    rap_sec = next(s for s in plan.sections if s.kind == "Rap")
    verse_sec = next(s for s in plan.sections if s.kind == "Verse")
    assert len(rapped) / rap_sec.beats > len(verse) / verse_sec.beats
    assert np.std([n.pitch for n in rapped]) < 0.6 * np.std([n.pitch for n in verse])
    assert max(n.pitch for n in rapped) - min(n.pitch for n in rapped) <= 7


def test_a_rap_header_in_the_lyrics_is_the_rap_section():
    from lyrics import parse_lyrics
    assert set(parse_lyrics("[Rap]\nよ る\n[Sprechteil 2]\nあ さ")) == {"Rap", "Rap#2"}


# ── Ganzer Song ───────────────────────────────────────────────────────────────────
def song(tmp_path, root, url, **kw):
    s = SongSettings(active_sections=["Verse", "Rap"], section_bars={"Verse": 4, "Rap": 4},
                     lyrics="[Verse]\nよ る の ま ち\n[Rap]\nき み の な ま え を よ ぶ た び に",
                     output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root), singer="MERROW", seed=5,
                     voicevox_url=url, rap_speaker=3, harmonies=False, final_choir=False, breaths=False,
                     phrase_expression=False, syllable_dynamics=False, harmony_double=False, sung_pads=False,
                     adlibs=False, polish=False, auto_rating=False, vocal_versions=False, id3_tags=False)
    return s.with_updates(**kw)


def sung_notes(out):
    return [n for n in music21.converter.parse(os.path.join(out, "vocals.xml")).recurse().notes]


def level_at(path, hz, start, end):
    audio, rate = sf.read(path, always_2d=True)
    part = audio[int(start * rate):int(end * rate)].mean(axis=1)
    spectrum = np.abs(np.fft.rfft(part))
    freqs = np.fft.rfftfreq(len(part), 1 / rate)
    return spectrum[np.abs(freqs - hz) < 4].max() / len(part)


def test_voicevox_speaks_the_rap_and_neutrino_sings_the_rest(tmp_path, neutrino_attrappe, fake_talk):
    root, _ = neutrino_attrappe
    s = song(tmp_path, root, fake_talk)
    pipeline.generate_song(s, keep_history=False)
    out = s.output_dir()
    tracks = pipeline.compose(s)[0]
    rap_sec = next(sec for sec in tracks["plan"].sections if sec.kind == "Rap")
    verse_syllables = len([n for n in tracks["vocal_melody"] if n.start < rap_sec.start * 60 / s.bpm])
    assert len(sung_notes(out)) == verse_syllables                    # NEUTRINO singt den Rap nicht
    assert {r[1] for r in FakeTalk.requests if r[0] == "/synthesis"} == {3}
    vocals = os.path.join(out, "vocals.wav")
    spb = 60 / s.bpm
    assert level_at(vocals, RAP_HZ, rap_sec.start * spb, rap_sec.end * spb) > \
        20 * level_at(vocals, RAP_HZ, 0.5, rap_sec.start * spb - 0.5)
    assert vocal_check.describe(vocal_check.read(out))[0].endswith("Rap: VOICEVOX-Sprechstimme ずんだもん (ノーマル)")


def test_without_the_switch_or_without_voicevox_the_singer_sings_the_rap(tmp_path, neutrino_attrappe, fake_talk):
    root, _ = neutrino_attrappe
    s = song(tmp_path, root, fake_talk, rap_voice=False)
    pipeline.generate_song(s, keep_history=False)
    tracks = pipeline.compose(s)[0]
    assert len(sung_notes(s.output_dir())) == len(tracks["silben"])
    assert not FakeTalk.requests or all(r[0] != "/audio_query" for r in FakeTalk.requests)
    s = song(tmp_path / "b", root, "http://127.0.0.1:9")                # dort läuft kein VOICEVOX
    pipeline.generate_song(s, keep_history=False)
    assert len(sung_notes(s.output_dir())) == len(pipeline.compose(s)[0]["silben"])


def test_a_song_of_only_rap_is_spoken(tmp_path, neutrino_attrappe, fake_talk):
    root, calls = neutrino_attrappe
    s = song(tmp_path, root, fake_talk, active_sections=["Rap"])
    calls.clear()
    pipeline.generate_song(s, keep_history=False)
    assert calls == []                                                 # NEUTRINO hatte nichts zu singen
    assert level_at(os.path.join(s.output_dir(), "vocals.wav"), RAP_HZ, 0.0, 8.0) > 0
