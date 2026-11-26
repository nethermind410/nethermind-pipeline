#!/usr/bin/env python3
"""100 BRICKS assembly: cut an episode's clips to its voice and lay the brick counter, the plus and minus numbers and
the A or B card on top. RUNS ON GITHUB ACTIONS (.github/workflows/bricks-assemble.yml), never in a Claude session.

  python3 assemble.py episodes/ep01 out/ep01.mp4 [--silent]

Reads <episode>/episode.json. Each shot runs for its voice line plus the gap; the last shot holds for the tail with the
vote card up. A clip shorter than its slot is slowed by up to 20 percent, then its last frame is held; a longer one is
cut. A shot marked "loop" whose line runs much longer than its clip plays forward then backward instead of freezing. If <episode>/music.mp3 is there (or the file named by "music" in episode.json) it is laid quietly under the voice, at
"music_db" decibels (default -20). --silent builds the picture with no voice (used until the voice files are in the repo). No generation, no network.
Prints one JSON line: {"ok":true,"seconds":S,"shots":N,"voice":true|false,"out":"..."}"""
import json, os, re, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 24
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'PixelifySans-700.ttf')   # his pick (A), OFL, from the studio set
# Torch gold: his pick (2). The colours come from the torchlight in the scene. No teal, no red.
GOLD, GOLD_HI, AMBER, WHITE, INK = (255, 196, 64), (255, 232, 150), (255, 140, 40), (255, 255, 255), (8, 6, 14)
try:                                   # a self-contained ffmpeg from pip, so the cloud run needs no system packages
    import imageio_ffmpeg; FF = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FF = 'ffmpeg'


def font(px):
    return ImageFont.truetype(FONT, px)


def text(d, xy, s, px, fill, anchor='mm', sh=5):
    d.text((xy[0] + sh, xy[1] + sh), s, font=font(px), fill=(0, 0, 0, 235), anchor=anchor)     # hard black edge: reads over any picture
    d.text(xy, s, font=font(px), fill=fill, anchor=anchor)


def overlay(ep, shot, path):
    """One transparent 1080x1920 picture per shot: the health bar always, a number when the shot has one, the vote card on the last."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    n, full = shot.get('count', ep['count']), ep.get('full', 100); x0, y0, bw, bh = 150, 150, 700, 54
    # health bar, like a game: brick icon, a bar of twenty segments that empties as bricks are lost, the number
    d.rectangle([x0 - 78, y0 - 6, x0 - 14, y0 + bh + 6], fill=(0, 0, 0, 255)); d.rectangle([x0 - 72, y0, x0 - 20, y0 + bh], fill=GOLD)
    d.rectangle([x0 - 72, y0, x0 - 20, y0 + 8], fill=GOLD_HI); d.ellipse([x0 - 60, y0 + 13, x0 - 32, y0 + 41], fill=GOLD_HI); d.ellipse([x0 - 58, y0 + 16, x0 - 34, y0 + 40], fill=GOLD)
    d.rectangle([x0 - 6, y0 - 6, x0 + bw + 6, y0 + bh + 6], fill=(0, 0, 0, 255)); d.rectangle([x0, y0, x0 + bw, y0 + bh], fill=(38, 30, 52, 255))
    w = bw * max(0, min(n, full)) / full
    if w > 0: d.rectangle([x0, y0, x0 + w, y0 + bh], fill=GOLD); d.rectangle([x0, y0, x0 + w, y0 + 9], fill=GOLD_HI)
    for k in range(1, 20): d.rectangle([x0 + bw * k / 20 - 2, y0, x0 + bw * k / 20 + 1, y0 + bh], fill=(0, 0, 0, 255))
    text(d, (x0 + bw + 26, y0 + bh / 2), str(n), 68, WHITE, 'lm'); text(d, (x0 - 72, y0 + bh + 44), 'bricks', 42, WHITE, 'lm', 4)
    if shot.get('label'):
        t = shot['label']['text']; text(d, (W / 2, 520), t, 240, GOLD if t.startswith('+') else AMBER, 'mm', 9)
    if shot.get('vote'):
        v = ep['vote']; d.rectangle([0, 1150, W, 1650], fill=INK + (95,))            # see-through: the picture stays visible behind the card
        text(d, (W / 2, 1225), v['q'], 72, WHITE)
        for i, (k, s, col) in enumerate((('a', v['a'], GOLD), ('b', v['b'], AMBER))):
            y = 1340 + i * 116; d.rectangle([150, y - 48, 246, y + 48], fill=(0, 0, 0, 255)); d.rectangle([156, y - 42, 240, y + 42], fill=col)
            d.text((198, y - 2), k, font=font(70), fill=INK, anchor='mm'); text(d, (282, y), s, 74, WHITE, 'lm')
        text(d, (W / 2, 1585), 'comment a or b', 60, WHITE)
    im.save(path)


def dur(p):
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', subprocess.run([FF, '-hide_banner', '-i', p], capture_output=True, text=True).stderr)
    if not m: raise SystemExit(f'cannot read the length of {p}')
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]; silent = '--silent' in sys.argv
    if len(a) != 2: raise SystemExit(__doc__)
    root, out = a; ep = json.load(open(os.path.join(root, 'episode.json'))); shots = ep['shots']
    voices = [os.path.join(root, s['voice']) for s in shots]; have = all(os.path.exists(v) for v in voices) and not silent
    if not have and not silent: raise SystemExit('voice files missing: ' + ', '.join(v for v in voices if not os.path.exists(v)) + '  (use --silent for a picture-only cut)')
    tmp = tempfile.mkdtemp(); ins, fc, vs, au = [], [], [], []
    for i, s in enumerate(shots):
        clip = os.path.join(root, s['clip']); slot = (dur(voices[i]) if have else s['seconds']) + ep['gap'] + (ep['tail'] if i == len(shots) - 1 else 0)
        c = dur(clip); k = min(1.2, max(1.0, slot / c)); ov = os.path.join(tmp, f'ov{i}.png'); overlay(ep, s, ov)
        ins += ['-i', clip, '-loop', '1', '-t', f'{slot:.3f}', '-i', ov]
        src = f'[{2 * i}:v]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}'
        if s.get('loop') and slot > c * 1.2 + 0.5:   # a line much longer than its clip: play it forward, back, forward, back, so nothing freezes
            k = min(1.2, max(1.0, slot / (4 * c)))
            src += f',split=4[p{i}a][p{i}b][p{i}c][p{i}d];[p{i}b]reverse[p{i}e];[p{i}d]reverse[p{i}f];[p{i}a][p{i}e][p{i}c][p{i}f]concat=n=4:v=1:a=0'
        fc.append(f'{src},setpts={k:.4f}*PTS,tpad=stop_mode=clone:stop_duration=30,trim=duration={slot:.3f},setpts=PTS-STARTPTS[c{i}];'
                  f'[c{i}][{2 * i + 1}:v]overlay=shortest=1,format=yuv420p[v{i}]')
        vs.append(f'[v{i}]')
    n = len(shots); fc.append(''.join(vs) + f'concat=n={n}:v=1:a=0[v]'); maps = ['-map', '[v]']
    if have:
        for i, v in enumerate(voices):
            slot = dur(v) + ep['gap'] + (ep['tail'] if i == n - 1 else 0); ins += ['-i', v]
            fc.append(f'[{2 * n + i}:a]aresample=48000,apad,atrim=duration={slot:.3f}[a{i}]'); au.append(f'[a{i}]')
        music = os.path.join(root, ep.get('music', 'music.mp3'))
        if os.path.exists(music):  # a quiet bed under the voice: looped to length, dipped while he speaks, faded at both ends
            total = sum(dur(v) + ep['gap'] for v in voices) + ep['tail']; ins += ['-stream_loop', '-1', '-i', music]
            fc.append(''.join(au) + f'concat=n={n}:v=0:a=1,asplit[vo][key]')
            fc.append(f'[{3 * n}:a]aresample=48000,volume={ep.get("music_db", -20)}dB,atrim=duration={total:.3f},afade=t=in:d=0.5,'
                      f'afade=t=out:st={total - 2:.3f}:d=2[m];[m][key]sidechaincompress=threshold=0.03:ratio=5:attack=20:release=500[md];'
                      f'[vo][md]amix=inputs=2:normalize=0:duration=first[a]')
        else:
            fc.append(''.join(au) + f'concat=n={n}:v=0:a=1[a]')
        maps += ['-map', '[a]', '-c:a', 'aac', '-b:a', '192k']
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    subprocess.check_call([FF, '-y', '-loglevel', 'error', *ins, '-filter_complex', ';'.join(fc), *maps, '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                           '-r', str(FPS), '-movflags', '+faststart', out])
    print(json.dumps({'ok': True, 'seconds': round(dur(out), 2), 'shots': n, 'voice': have, 'music': have and os.path.exists(os.path.join(root, ep.get('music', 'music.mp3'))), 'out': os.path.abspath(out)}))


if __name__ == '__main__':
    main()
