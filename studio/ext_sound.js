"use strict";
/* Sound for Nethermind: interface sounds (soft, off by default) and music.
   Music is either "Nether drift" — generative ambient made live in the browser (slow minor chords, a filtered pad,
   sparse pentatonic plucks; never repeats, no files, no rights issues) — or your own tracks: drop .mp3/.m4a files
   into the pipeline's music/ folder and they appear in the list.
   window.nxSound.play("tick" | "handoff" | "done" | "celebrate")   window.nxSound.music.toggle() */
(() => {
  const LS = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };
  const S = {sfx: LS("nx-sfx") === "1", vol: +(LS("nx-vol") || 0.5), src: LS("nx-src") || "drift", on: LS("nx-music") === "1"};
  let ctx = null, master = null, sfxBus = null, musicBus = null;
  function audio() {
    if (ctx) { if (ctx.state === "suspended") ctx.resume(); return ctx; }
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = ctx.createGain(); master.gain.value = 1; master.connect(ctx.destination);
    sfxBus = ctx.createGain(); sfxBus.gain.value = 0.35; sfxBus.connect(master);
    musicBus = ctx.createGain(); musicBus.gain.value = S.vol * 0.5; musicBus.connect(master);
    return ctx;
  }
  // a small shared reverb: a decaying noise impulse
  let verb = null;
  function reverb() {
    if (verb) return verb;
    const c = audio(), len = c.sampleRate * 3.2, buf = c.createBuffer(2, len, c.sampleRate);
    for (let ch = 0; ch < 2; ch++) { const d = buf.getChannelData(ch); for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.6); }
    verb = c.createConvolver(); verb.buffer = buf;
    const wet = c.createGain(); wet.gain.value = 0.55; verb.connect(wet); wet.connect(master);
    return verb;
  }
  function note(freq, t, dur, {type = "sine", gain = 0.2, bus = sfxBus, wet = 0.5, attack = 0.005} = {}) {
    const c = audio(), o = c.createOscillator(), g = c.createGain();
    o.type = type; o.frequency.value = freq;
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(gain, t + attack); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(bus);
    if (wet) { const w = c.createGain(); w.gain.value = wet; g.connect(w); w.connect(reverb()); }
    o.start(t); o.stop(t + dur + 0.05);
  }
  const hz = m => 440 * Math.pow(2, (m - 69) / 12);
  const SFX = {
    tick: t => note(hz(96), t, 0.09, {gain: 0.08, wet: 0.2}),
    handoff: t => { note(hz(84), t, 0.5, {gain: 0.07, type: "triangle"}); note(hz(91), t + 0.09, 0.7, {gain: 0.06, type: "triangle"}); },
    done: t => [72, 76, 79].forEach((m, i) => note(hz(m), t + i * 0.07, 0.6, {gain: 0.09, type: "triangle"})),
    celebrate: t => { [69, 72, 76, 81, 84, 88].forEach((m, i) => note(hz(m), t + i * 0.08, 1.4, {gain: 0.09, type: "triangle"}));
                      [57, 64].forEach(m => note(hz(m), t, 2.4, {gain: 0.08, attack: 0.05})); },
  };
  function play(name, force) {
    if (!(S.sfx || force) || !SFX[name]) return;
    try { SFX[name](audio().currentTime + 0.01); } catch (e) {}
  }

  /* ---------- Nether drift: generative ambient ---------- */
  // A minor, slow: i – VI – III – VII (Am9, Fmaj7, Cmaj7, G6), 9 s per chord, voices glide between chords
  const CHORDS = [[45, 57, 60, 64, 71], [41, 57, 60, 64, 69], [48, 55, 59, 64, 67], [43, 55, 59, 62, 64]];
  const PENTA = [69, 72, 74, 76, 79, 81, 84];
  let drift = null;
  function startDrift() {
    const c = audio(), out = c.createGain(); out.gain.value = 0; out.connect(musicBus);
    out.gain.linearRampToValueAtTime(1, c.currentTime + 4);
    const lp = c.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 900; lp.Q.value = 0.6; lp.connect(out);
    const lfo = c.createOscillator(), lfoG = c.createGain(); lfo.frequency.value = 0.05; lfoG.gain.value = 450; lfo.connect(lfoG); lfoG.connect(lp.frequency); lfo.start();
    const w = c.createGain(); w.gain.value = 0.7; lp.connect(w); w.connect(reverb());
    const voices = CHORDS[0].map((m, i) => {
      const g = c.createGain(); g.gain.value = i === 0 ? 0.05 : 0.03; g.connect(lp);
      const oscs = [-6, 6].map(d => { const o = c.createOscillator(); o.type = i === 0 ? "sine" : "sawtooth"; o.detune.value = d; o.frequency.value = hz(m); o.connect(g); o.start(); return o; });
      return {oscs};
    });
    let k = 0;
    const step = () => {
      k = (k + 1) % CHORDS.length;
      const t = c.currentTime;
      voices.forEach((v, i) => v.oscs.forEach(o => o.frequency.setTargetAtTime(hz(CHORDS[k][i]), t, 1.6)));
    };
    const chordT = setInterval(step, 9000);
    const pluck = () => {                            // sparse plucks: a few notes per chord, sometimes none
      if (Math.random() < 0.55) note(hz(PENTA[Math.floor(Math.random() * PENTA.length)]), c.currentTime + 0.05, 2.8,
        {gain: 0.035, type: "triangle", bus: out, wet: 0.9, attack: 0.01});
    };
    const pluckT = setInterval(pluck, 1700);
    drift = {stop() {
      const t = c.currentTime; out.gain.cancelScheduledValues(t); out.gain.setValueAtTime(out.gain.value, t); out.gain.linearRampToValueAtTime(0, t + 1.5);
      clearInterval(chordT); clearInterval(pluckT);
      setTimeout(() => { voices.forEach(v => v.oscs.forEach(o => o.stop())); lfo.stop(); out.disconnect(); }, 1700);
    }};
  }

  /* ---------- your own tracks (music/ folder) ---------- */
  const el = new Audio(); el.preload = "none";
  let tracks = [], ti = 0;
  el.addEventListener("ended", () => { if (tracks.length) { ti = (ti + 1) % tracks.length; el.src = "/music/" + encodeURIComponent(tracks[ti]); el.play().catch(() => {}); } });
  let wired = false;
  function startFiles() {
    if (!tracks.length) return false;
    const c = audio();
    if (!wired) { const n = c.createMediaElementSource(el); n.connect(musicBus); wired = true; }
    const start = S.src === "files" ? Math.floor(Math.random() * tracks.length) : Math.max(0, tracks.indexOf(S.src));
    ti = start; el.src = "/music/" + encodeURIComponent(tracks[ti]); el.play().catch(() => {});
    return true;
  }
  const music = {
    playing: false,
    start() {
      this.stop(true);
      if (S.src === "drift" || !startFiles()) startDrift();
      this.playing = true; S.on = true; LS("nx-music", "1"); ui();
    },
    stop(keep) { if (drift) { drift.stop(); drift = null; } el.pause(); this.playing = false; if (!keep) { S.on = false; LS("nx-music", "0"); } ui(); },
    toggle() { this.playing ? this.stop() : this.start(); },
    now() { return S.src === "drift" || !tracks.length ? "Nether drift" : (tracks[ti] || "").replace(/\.[a-z0-9]+$/i, ""); },
  };

  /* ---------- the control: a small ♪ chip bottom-left, a panel on click ---------- */
  const chip = document.createElement("div");
  chip.className = "snd";
  chip.innerHTML = `<button class="snd-btn" aria-label="Music" aria-expanded="false"><span class="snd-eq"><i></i><i></i><i></i></span><span class="snd-now">Music</span></button>
    <div class="snd-panel" hidden>
      <div class="snd-row"><button class="btn small primary" data-snd="play">Play</button><span class="snd-title"></span></div>
      <label class="snd-row"><span class="k">Music</span><select data-snd="src"></select></label>
      <label class="snd-row"><span class="k">Volume</span><input type="range" min="0" max="1" step="0.05" data-snd="vol"></label>
      <label class="snd-row snd-check"><input type="checkbox" data-snd="sfx"> Interface sounds <span class="nx-meta">(hand-offs, done, a video going live)</span></label>
      <p class="nx-meta">Add your own tracks: put .mp3 or .m4a files in the pipeline's <b>music</b> folder.</p></div>`;
  function ui() {
    const p = $(".snd-panel", chip);
    chip.classList.toggle("on", music.playing);
    $(".snd-now", chip).textContent = music.playing ? music.now() : "Music";
    $("[data-snd=play]", chip).textContent = music.playing ? "Pause" : "Play";
    $(".snd-title", chip).textContent = music.playing ? music.now() : "Off";
    $("[data-snd=vol]", chip).value = S.vol; $("[data-snd=sfx]", chip).checked = S.sfx;
    const sel = $("[data-snd=src]", chip);
    sel.innerHTML = `<option value="drift">Nether drift (generative)</option>` +
      (tracks.length ? `<option value="files">Your tracks — shuffle</option>` + tracks.map(t => `<option value="${esc(t)}">${esc(t.replace(/\.[a-z0-9]+$/i, ""))}</option>`).join("") : "");
    sel.value = S.src; if (sel.value !== S.src) sel.value = "drift";
    p.hidden = !chip.classList.contains("open");
  }
  chip.addEventListener("click", e => {
    const b = e.target.closest(".snd-btn"); if (b) { chip.classList.toggle("open"); b.setAttribute("aria-expanded", chip.classList.contains("open")); return ui(); }
    if (e.target.closest("[data-snd=play]")) music.toggle();
  });
  chip.addEventListener("input", e => {
    const t = e.target.dataset.snd;
    if (t === "vol") { S.vol = +e.target.value; LS("nx-vol", S.vol); if (musicBus) musicBus.gain.setTargetAtTime(S.vol * 0.5, ctx.currentTime, 0.1); }
    if (t === "sfx") { S.sfx = e.target.checked; LS("nx-sfx", S.sfx ? "1" : "0"); if (S.sfx) play("done"); }
    if (t === "src") { S.src = e.target.value; LS("nx-src", S.src); if (music.playing) music.start(); }
  });
  document.addEventListener("click", e => { if (!chip.contains(e.target) && chip.classList.contains("open")) { chip.classList.remove("open"); ui(); } });
  // browsers only allow sound after you touch the page: if music was on last time, it resumes on your first click
  const resume = () => { document.removeEventListener("pointerdown", resume, true); if (S.on && !music.playing) music.start(); };
  document.addEventListener("pointerdown", resume, true);
  document.addEventListener("DOMContentLoaded", async () => {
    document.body.appendChild(chip);
    try { tracks = (await get("/api/music")).tracks || []; } catch (e) {}
    ui();
  });
  window.nxSound = {play, music};
})();
