// karaoke.js – Der Liedtext zum Mitlesen: die laufende Zeile, Silbe für Silbe eingefärbt, darunter die nächste.
// Folgt dem Player ("vg-time").
export default {
  template: `
    <div class="vg-karaoke" v-show="lines && lines.length">
      <div class="vg-line">
        <span v-for="(s, i) in current.syllables || []" :key="i" :class="{ sung: s[0] <= time }">{{ s[2] }}</span>
      </div>
      <div class="vg-next">{{ nextText }}</div>
    </div>`,
  props: {
    lines: Array, // [{start, end, syllables: [[start, ende, text]]}]
  },
  data() {
    return { time: 0 };
  },
  computed: {
    index() {
      const lines = this.lines || [];
      // die Zeile, die gerade läuft, sonst die nächste (oder die letzte)
      let i = lines.findIndex((l) => this.time < l.end + 0.3);
      return i < 0 ? lines.length - 1 : i;
    },
    current() {
      return (this.lines || [])[this.index] || {};
    },
    nextText() {
      const next = (this.lines || [])[this.index + 1];
      return next ? next.syllables.map((s) => s[2]).join("") : "";
    },
  },
  mounted() {
    this.onTime = (e) => (this.time = e.detail);
    window.addEventListener("vg-time", this.onTime);
  },
  unmounted() {
    window.removeEventListener("vg-time", this.onTime);
  },
  watch: {
    lines() {
      this.time = 0;
    },
  },
};
