// piano_roll.js – Noten aller Spuren über die Zeit. Folgt dem Player ("vg-time"), ein Klick springt
// im Player an diese Stelle ("vg-seek").
export default {
  template: `
    <div ref="box" class="vg-roll" :style="{ height: height + 'px' }" @click="seek">
      <canvas ref="canvas"></canvas>
      <div ref="head" class="vg-head"></div>
    </div>`,
  props: {
    notes: Array, // [start, ende, tonhöhe, spur]
    tracks: Array, // [{name, color}]
    hidden: Array, // Indizes ausgeblendeter Spuren
    duration: Number,
    pxPerSecond: { type: Number, default: 36 },
    height: { type: Number, default: 240 },
  },
  mounted() {
    this.onTime = (e) => this.follow(e.detail);
    window.addEventListener("vg-time", this.onTime);
    this.draw();
  },
  unmounted() {
    window.removeEventListener("vg-time", this.onTime);
  },
  watch: {
    notes() {
      this.draw();
    },
    hidden() {
      this.draw();
    },
  },
  methods: {
    draw() {
      const canvas = this.$refs.canvas;
      const box = this.$refs.box;
      const notes = this.notes || [];
      const hidden = new Set(this.hidden || []);
      const width = Math.max(box.clientWidth, Math.ceil((this.duration || 0) * this.pxPerSecond) + 20);
      const height = this.height - 14;
      const ratio = window.devicePixelRatio || 1;
      canvas.width = width * ratio;
      canvas.height = height * ratio;
      canvas.style.width = width + "px";
      canvas.style.height = height + "px";
      const ctx = canvas.getContext("2d");
      ctx.scale(ratio, ratio);
      ctx.clearRect(0, 0, width, height);
      const shown = notes.filter((n) => !hidden.has(n[3]));
      if (!shown.length) return;
      let lo = 127;
      let hi = 0;
      for (const n of shown) {
        lo = Math.min(lo, n[2]);
        hi = Math.max(hi, n[2]);
      }
      lo -= 2;
      hi += 2;
      const row = height / (hi - lo + 1);
      // Oktaven (jedes C) als feine Linien
      ctx.fillStyle = "rgba(255,255,255,0.06)";
      for (let p = lo; p <= hi; p++) {
        if (p % 12 === 0) ctx.fillRect(0, height - (p - lo + 1) * row, width, 1);
      }
      // Sekundenraster alle 10 Sekunden
      ctx.fillStyle = "rgba(255,255,255,0.08)";
      for (let t = 10; t < (this.duration || 0); t += 10) ctx.fillRect(t * this.pxPerSecond, 0, 1, height);
      for (const [start, end, pitch, track] of shown) {
        ctx.fillStyle = (this.tracks[track] || {}).color || "#90a4ae";
        const x = start * this.pxPerSecond;
        const w = Math.max(2, (end - start) * this.pxPerSecond - 1);
        ctx.fillRect(x, height - (pitch - lo + 1) * row, w, Math.max(2, row - 1));
      }
    },
    follow(t) {
      const x = t * this.pxPerSecond;
      this.$refs.head.style.transform = `translateX(${x}px)`;
      const box = this.$refs.box;
      if (x < box.scrollLeft || x > box.scrollLeft + box.clientWidth - 40) box.scrollLeft = Math.max(0, x - 60);
    },
    seek(e) {
      const box = this.$refs.box;
      const x = e.clientX - box.getBoundingClientRect().left + box.scrollLeft;
      window.dispatchEvent(new CustomEvent("vg-seek", { detail: x / this.pxPerSecond }));
    },
  },
};
