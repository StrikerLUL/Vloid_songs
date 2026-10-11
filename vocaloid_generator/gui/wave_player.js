// wave_player.js – Player mit Wellenform (wavesurfer.js). Meldet die Zeit an die Piano-Roll ("vg-time")
// und springt, wenn die Piano-Roll eine Stelle anklickt ("vg-seek").
import WaveSurfer from "wavesurfer";

function fmt(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export default {
  template: `
    <div class="vg-player">
      <div ref="wave" class="vg-wave"></div>
      <div class="vg-controls">
        <button type="button" class="vg-play" :disabled="!url" @click="playPause">{{ playing ? "❚❚" : "▶" }}</button>
        <span class="vg-time">{{ time(current) }} / {{ time(total) }}</span>
        <span class="vg-title">{{ title }}</span>
      </div>
    </div>`,
  props: {
    url: String,
    title: String,
    peaks: Array,
    duration: Number,
    height: { type: Number, default: 110 },
  },
  data() {
    return { playing: false, current: 0, total: 0 };
  },
  mounted() {
    this.ws = WaveSurfer.create({
      container: this.$refs.wave,
      height: this.height,
      waveColor: "#9575cd",
      progressColor: "#ff4f8b",
      cursorColor: "#ffffff",
      cursorWidth: 2,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      normalize: true,
      dragToSeek: true,
    });
    this.ws.on("play", () => (this.playing = true));
    this.ws.on("pause", () => (this.playing = false));
    this.ws.on("finish", () => (this.playing = false));
    this.ws.on("ready", (d) => (this.total = d));
    this.ws.on("timeupdate", (t) => {
      this.current = t;
      window.dispatchEvent(new CustomEvent("vg-time", { detail: t }));
    });
    this.onSeek = (e) => {
      if (this.url) this.ws.setTime(e.detail);
    };
    window.addEventListener("vg-seek", this.onSeek);
    this.load(false);
  },
  unmounted() {
    window.removeEventListener("vg-seek", this.onSeek);
    if (this.ws) this.ws.destroy();
  },
  watch: {
    url() {
      this.load(true);
    },
  },
  methods: {
    time: fmt,
    load(keepPosition) {
      // Beim Wechsel zwischen Mix und Einzelspur geht es an derselben Stelle weiter
      const position = keepPosition ? this.ws.getCurrentTime() : 0;
      const resume = keepPosition && this.playing;
      this.current = 0;
      this.total = this.duration || 0;
      if (!this.url) {
        this.ws.empty();
        return;
      }
      const peaks = this.peaks && this.peaks.length ? [this.peaks] : undefined;
      this.ws.load(this.url, peaks, this.duration || undefined).then(() => {
        if (position) this.ws.setTime(Math.min(position, this.ws.getDuration()));
        if (resume) this.ws.play();
      }).catch(() => {});
    },
    playPause() {
      if (this.url) this.ws.playPause();
    },
    stop() {
      this.ws.stop();
    },
  },
};
