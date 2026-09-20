"""
score.py — synthesized ambient score + SFX bed for make_short.py.

build_audio() mixes a procedural drone (ducked under narration and any
payoff clip's own audio) with a few percussive stings, then loudness-
normalises the whole thing to -14 LUFS.
"""
import os, subprocess, wave
import numpy as np


def build_audio(segs, TOTAL, TMP, VID, A, TTS_DIR, deep, SR=48000):
    N = int(TOTAL * SR)
    tt = np.arange(N) / SR
    rng = np.random.default_rng(7)
    f0 = 44 if deep else 55
    drone = (.55 * np.sin(2 * np.pi * f0 * tt) + .35 * np.sin(2 * np.pi * (f0 * 1.007) * tt)
             + .25 * np.sin(2 * np.pi * f0 * 1.5 * tt) + .16 * np.sin(2 * np.pi * f0 * 2.005 * tt))
    drone *= .75 + .25 * np.sin(2 * np.pi * .22 * tt)
    br = np.cumsum(rng.standard_normal(N))
    br -= np.convolve(br, np.ones(4800) / 4800, mode="same")
    drone += .8 * br / (np.abs(br).max() + 1e-9)
    pts = [(0, 0), (.4, .5)]
    pay = next((s for s in segs if s.get("payoff")), None)
    if pay:
        pts += [(pay["start"] - .25, 1.0), (pay["start"], 0.0), (pay["end"], 0.0), (pay["end"] + .35, .55)]
    pts += [(TOTAL - .35, .55), (TOTAL, 0)]
    ts, vs = zip(*sorted(pts))
    drone = drone / (np.abs(drone).max() + 1e-9) * np.interp(tt, ts, vs) * .15

    sfx = np.zeros(N)
    def boom(t0, g=.8, fb=48, dd=1.2):
        i0 = int(t0 * SR); n = min(int(dd * SR), N - i0)
        if n <= 0: return
        u = np.arange(n) / SR
        sfx[i0:i0 + n] += g * np.sin(2 * np.pi * np.cumsum(fb * (1 + 1.5 * np.exp(-u * 12))) / SR) * np.exp(-u * 3.2)
    def whoosh(t0, g=.22, dd=0.45):
        i0 = max(int(t0 * SR), 0); n = min(int(dd * SR), N - i0)
        if n <= 0: return
        u = np.arange(n) / SR
        z = rng.standard_normal(n); z -= np.convolve(z, np.ones(40) / 40, mode="same")
        sfx[i0:i0 + n] += g * z / (np.abs(z).max() + 1e-9) * np.sin(np.pi * u / dd) ** 2 * np.exp(-u * 2)
    def ping(t0, g=.2, fr=880):
        i0 = int(t0 * SR); n = min(int(1.1 * SR), N - i0)
        if n <= 0: return
        u = np.arange(n) / SR
        sfx[i0:i0 + n] += g * np.sin(2 * np.pi * fr * u) * np.exp(-u * 6)
    def riser(t0, t1, g=.3):
        i0, i1 = max(int(t0 * SR), 0), min(int(t1 * SR), N)
        if i1 <= i0: return
        n = i1 - i0; u = np.arange(n) / SR; dd = n / SR
        z = rng.standard_normal(n); z -= np.convolve(z, np.ones(30) / 30, mode="same")
        tone = np.sin(2 * np.pi * np.cumsum(90 * (1 + 3 * (u / dd) ** 2)) / SR)
        sfx[i0:i1] += g * (.5 * z / (np.abs(z).max() + 1e-9) + .5 * tone) * (u / dd) ** 2.2

    boom(0, .8)
    for s in segs[1:]:
        (ping if s["vis"]["t"] == "ice" else whoosh)(max(s["start"] - .12, 0))
    if pay:
        riser(pay["start"] - 1.6, pay["start"]); boom(pay["start"], .5, 40)
    boom(segs[-1]["start"], .32, 44)

    bed = np.clip(drone + sfx, -1, 1)
    bedp = os.path.join(TMP, VID + "_bed.wav")
    with wave.open(bedp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((bed * 32767).astype(np.int16).tobytes())

    inp, fc, lab, i = ["-i", bedp], [], ["[0:a]"], 1
    for s in segs:
        dl = int(s["start"] * 1000)
        if s.get("payoff"):
            src = os.path.join(A, s["vis"]["src"])
            inp += ["-i", src]
            fc.append(f"[{i}:a]atrim={s['vis'].get('ss',0)}:{s['vis'].get('ss',0)+s['dur']:.3f},asetpts=PTS-STARTPTS,"
                      f"aformat=sample_fmts=fltp:channel_layouts=mono:sample_rates={SR},"
                      f"afade=t=in:d=0.12,afade=t=out:st={s['dur']-.45:.3f}:d=0.45,volume={s.get('vol',1.6)},"
                      f"adelay={dl}[p{i}]")
            lab.append(f"[p{i}]"); i += 1
        elif s.get("text"):
            inp += ["-i", os.path.join(TTS_DIR, s["id"] + ".mp3")]
            fc.append(f"[{i}:a]aformat=sample_fmts=fltp:channel_layouts=mono:sample_rates={SR},adelay={dl}[v{i}]")
            lab.append(f"[v{i}]"); i += 1
    fc.insert(0, f"[0:a]aformat=sample_fmts=fltp:channel_layouts=mono:sample_rates={SR}[bed]")
    lab[0] = "[bed]"
    fc.append("".join(lab) + f"amix=inputs={len(lab)}:normalize=0:duration=longest,"
                             f"atrim=0:{TOTAL:.3f},loudnorm=I=-14:TP=-1.0:LRA=9[out]")
    mixp = os.path.join(TMP, VID + "_mix.wav")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y"] + inp + ["-filter_complex", ";".join(fc),
                          "-map", "[out]", "-ar", str(SR), "-ac", "2", mixp])
    return mixp
