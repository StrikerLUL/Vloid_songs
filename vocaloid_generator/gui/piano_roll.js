// piano_roll.js – Noten aller Spuren über die Zeit. Folgt dem Player ("vg-time"), ein Klick springt
// im Player an diese Stelle ("vg-seek"). Mit editable lassen sich die Töne der Gesangsmelodie nach oben und
// unten ziehen oder mit den Pfeiltasten verschieben (Umschalt: Oktave); jede Änderung meldet "edit".
export default {
  template: `
    <div ref="box" class="vg-roll" :class="{ editing: editable }" :style="{ height: height + 'px' }" tabindex="0"
         @click="seek" @mousedown="grab" @keydown="key">
      <canvas ref="canvas"></canvas>
      <div ref="head" class="vg-head"></div>
    </div>`,
  props: {
    notes: Array, // [start, ende, tonhöhe, spur]
    tracks: Array, // [{key, name, color}]
    hidden: Array, // Indizes ausgeblendeter Spuren
    duration: Number,
    editable: Boolean,
    pxPerSecond: { type: Number, default: 36 },
    height: { type: Number, default: 240 },
  },
  data() {
    return { selected: null };
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
      this.selected = null;
      this.fixed = null;
      this.draw();
    },
    hidden() {
      this.draw();
    },
    editable() {
      this.selected = null;
      this.draw();
    },
  },
  methods: {
    vocalTrack() {
      return (this.tracks || []).findIndex((t) => t.key === "vocals");
    },
    range(shown) {
      let lo = 127;
      let hi = 0;
      for (const n of shown) {
        lo = Math.min(lo, n[2]);
        hi = Math.max(hi, n[2]);
      }
      // beim Bearbeiten etwas mehr Platz nach oben und unten, und die Lage bleibt beim Ziehen stehen
      const pad = this.editable ? 5 : 2;
      if (this.editable && this.fixed) return this.fixed;
      const r = [lo - pad, hi + pad];
      if (this.editable) this.fixed = r;
      return r;
    },
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
      if (!this.editable) this.fixed = null;
      const shown = notes.filter((n) => !hidden.has(n[3]));
      if (!shown.length) return;
      const [lo, hi] = this.range(shown);
      const row = height / (hi - lo + 1);
      this.geometry = { lo, hi, row, height };
      // Oktaven (jedes C) als feine Linien
      ctx.fillStyle = "rgba(255,255,255,0.06)";
      for (let p = lo; p <= hi; p++) {
        if (p % 12 === 0) ctx.fillRect(0, height - (p - lo + 1) * row, width, 1);
      }
      // Sekundenraster alle 10 Sekunden
      ctx.fillStyle = "rgba(255,255,255,0.08)";
      for (let t = 10; t < (this.duration || 0); t += 10) ctx.fillRect(t * this.pxPerSecond, 0, 1, height);
      const vocal = this.vocalTrack();
      for (const n of shown) {
        const [start, end, pitch, track] = n;
        // beim Bearbeiten treten die anderen Spuren zurück
        ctx.globalAlpha = this.editable && track !== vocal ? 0.25 : 1;
        ctx.fillStyle = (this.tracks[track] || {}).color || "#90a4ae";
        const x = start * this.pxPerSecond;
        const w = Math.max(2, (end - start) * this.pxPerSecond - 1);
        ctx.fillRect(x, height - (pitch - lo + 1) * row, w, Math.max(2, row - 1));
        if (n === this.selected) {
          ctx.strokeStyle = "#ffffff";
          ctx.lineWidth = 2;
          ctx.strokeRect(x - 1, height - (pitch - lo + 1) * row - 1, w + 2, Math.max(2, row - 1) + 2);
        }
      }
      ctx.globalAlpha = 1;
    },
    noteAt(e) {
      const box = this.$refs.box;
      const rect = box.getBoundingClientRect();
      const x = e.clientX - rect.left + box.scrollLeft;
      const y = e.clientY - rect.top;
      const g = this.geometry;
      const vocal = this.vocalTrack();
      if (!g || vocal < 0 || (this.hidden || []).includes(vocal)) return null;
      const t = x / this.pxPerSecond;
      return (this.notes || []).find((n) => {
        if (n[3] !== vocal || t < n[0] || t > n[1]) return false;
        const top = g.height - (n[2] - g.lo + 1) * g.row;
        return y >= top - 3 && y <= top + Math.max(2, g.row - 1) + 3;
      }) || null;
    },
    grab(e) {
      if (!this.editable) return;
      const note = this.noteAt(e);
      if (!note) return;
      e.preventDefault();
      this.$refs.box.focus();
      this.selected = note;
      this.draw();
      const startY = e.clientY;
      const before = note[2];
      const move = (m) => {
        const steps = Math.round((startY - m.clientY) / this.geometry.row);
        const pitch = Math.max(this.geometry.lo, Math.min(this.geometry.hi, before + steps));
        if (pitch !== note[2]) {
          note[2] = pitch;
          this.draw();
        }
      };
      const up = () => {
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
        this.dragged = true;
        if (note[2] !== before) this.$emit("edit", { start: note[0], pitch: note[2] });
      };
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    },
    key(e) {
      if (!this.editable || !this.selected || !["ArrowUp", "ArrowDown"].includes(e.key)) return;
      e.preventDefault();
      const step = (e.key === "ArrowUp" ? 1 : -1) * (e.shiftKey ? 12 : 1);
      this.selected[2] = Math.max(0, Math.min(127, this.selected[2] + step));
      this.draw();
      this.$emit("edit", { start: this.selected[0], pitch: this.selected[2] });
    },
    follow(t) {
      const x = t * this.pxPerSecond;
      this.$refs.head.style.transform = `translateX(${x}px)`;
      const box = this.$refs.box;
      if (x < box.scrollLeft || x > box.scrollLeft + box.clientWidth - 40) box.scrollLeft = Math.max(0, x - 60);
    },
    seek(e) {
      if (this.dragged) {
        this.dragged = false; // das Loslassen nach dem Ziehen eines Tons springt nicht
        return;
      }
      const box = this.$refs.box;
      const x = e.clientX - box.getBoundingClientRect().left + box.scrollLeft;
      window.dispatchEvent(new CustomEvent("vg-seek", { detail: x / this.pxPerSecond }));
    },
  },
};
