#!/usr/bin/env python3
"""dashboard.py — build out/dashboard.html, the phone-friendly "Nethermind Daily" page.

    python3 dashboard.py

Reads out/posted.json, out/stats.json (run stats.py first), cfg/ + packaging/, and the
latest out/daily/<date>.md written by the daily run. Thumbnails are embedded, so the
file is self-contained; the daily task publishes it to the same claude.ai link each day.
"""
import base64, datetime, io, json
from html import escape as e
from pathlib import Path
from string import Template
from PIL import Image
import studio_api

HERE = Path(__file__).resolve().parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
import channel
OUT = DATA / "out"


def jload(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def thumb_uri(path, width=640):
    if not path.exists():
        return None
    im = Image.open(path).convert("RGB")
    im.thumbnail((width, width * 2))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=72)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def when(iso):
    try:
        d = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return d.strftime("%a %d %b, %H:%M")
    except Exception:
        return iso or ""


def copy_block(label, text):
    if not text:
        return ""
    return (f'<div class="copy"><div class="copy-head"><span>{e(label)}</span>'
            f'<button type="button" class="copy-btn">Copy</button></div><pre>{e(text)}</pre></div>')


def ready_videos(posted):
    """Built + packaged + passed QA, not yet posted — newest first."""
    out = []
    for cfg in sorted((DATA / "cfg").glob("*.json"), key=lambda p: -p.stat().st_mtime):
        vid = cfg.stem
        if vid.endswith("_tiktok") or vid.startswith(("test", "zz")) or vid in posted:
            continue
        c = jload(cfg, {})
        mp4 = OUT / f"{c.get('file', vid)}.mp4"
        pkg = jload(DATA / "packaging" / f"{vid}.json", None)
        if mp4.exists() and pkg and (OUT / f"{vid}_qa_contact.jpg").exists():
            out.append((vid, pkg))
    return out


def main():
    posted = jload(OUT / "posted.json", {})
    stats = jload(OUT / "stats.json", {})
    videos = stats.get("videos", {})
    scheduled = stats.get("scheduled", [])
    logs = sorted((OUT / "daily").glob("*.md")) if (OUT / "daily").exists() else []
    log_text = logs[-1].read_text() if logs else "No daily run yet. The first one happens at 7:00."
    log_date = logs[-1].stem if logs else ""
    ready = ready_videos(posted)

    # performance: the app's own true numbers (YouTube from YouTube, TikTok/Instagram from Buffer)
    rows = []
    for r in studio_api.performance()["rows"]:
        by = {p["platform"]: p for p in r["posts"]}
        rows.append((r["views"], r["id"], by, int(sum(p.get("shares") or 0 for p in r["posts"])),
                     int(sum(p.get("saves") or 0 for p in r["posts"]))))
    rows.sort(reverse=True)
    top = rows[0][0] if rows and rows[0][0] else 1
    import studio_channel
    ch = studio_channel.channel()
    goals = ""
    if ch.get("ready"):
        goals = "".join(f'<div class="stat"><span>{e(g["label"])}</span><strong>{g["value"]:,}</strong>'
                        f'<em>{g["value"] / g["goal"] * 100:.1f}% of {g["goal"]:,} · {e(g["note"])}</em></div>' for g in ch["goals"])

    today = studio_api.today()
    titles = {v["id"]: v["title"] for v in studio_api.videos()}
    todo = []
    for c in today["cards"]:
        line = f"<li><b>{e(c['title'])}</b> {e(c['text'])}"
        if c.get("steps"):
            line += "<ul>" + "".join(f"<li>{'✓ ' if s['done'] else ''}{e(s['label'])}</li>" for s in c["steps"]) + "</ul>"
        if c.get("link"):
            line += f' <a href="{e(c["link"])}" target="_blank" rel="noopener">Open YouTube Studio</a>'
        todo.append(line + "</li>")
    if todo:
        todo.append(f'<li class="hint">Tick these off in the {e(channel.get("app_name"))} app on your Mac — they clear here after the next update.</li>')

    ready_html = ""
    for vid, pkg in ready[:2]:
        t = thumb_uri(OUT / f"{vid}_thumb.jpg")
        qa = thumb_uri(OUT / f"{vid}_qa_contact.jpg", 900)
        ready_html += f"""
      <article class="ready">
        <div class="ready-media">{f'<img src="{t}" alt="Thumbnail for {e(vid)}">' if t else ''}
          {f'<details><summary>QA contact sheet</summary><img src="{qa}" alt="QA frames for {e(vid)}"></details>' if qa else ''}</div>
        <div class="ready-text">
          <p class="eyebrow">Ready for you</p>
          <h3>{e(pkg.get('title', vid))}</h3>
          {copy_block('YouTube description', pkg.get('youtube_description'))}
          {copy_block('YouTube tags', pkg.get('youtube_tags'))}
          {copy_block('TikTok caption', pkg.get('tiktok_caption'))}
          {copy_block('Instagram caption', pkg.get('instagram_caption'))}
          {copy_block('Pinned comment', pkg.get('pinned_comment'))}
        </div>
      </article>"""
    if not ready_html:
        ready_html = '<p class="empty">Nothing waiting. The next video is built at 7:00.</p>'

    sched_html = "".join(
        f'<li><span class="plat plat-{e(s["platform"])}">{e(s["platform"])}</span>'
        f'<span class="sv">{e(titles.get(s["video"], s["video"]))}</span><time>{e(when(s["dueAt"]))}</time></li>'
        for s in scheduled) or '<li class="empty">Nothing queued in Buffer.</li>'

    perf_html = "".join(f"""
        <tr><th scope="row">{e(titles.get(vid, vid))}<span class="bar" style="--w:{max(2, round(total / top * 100))}%"></span></th>
          <td>{total:,}</td>
          <td>{int((by.get('youtube') or {}).get('views') or 0):,}</td>
          <td>{int((by.get('tiktok') or {}).get('views') or 0):,}</td>
          <td>{int((by.get('instagram') or {}).get('views') or 0):,}</td>
          <td>{shares}</td><td>{saves}</td></tr>""" for total, vid, by, shares, saves in rows) \
        or '<tr><td colspan="7" class="empty">No stats yet.</td></tr>'

    best = f"{rows[0][0]:,} views" if rows else "—"
    updated = when(stats.get("updated", "")) or "never"

    page = TEMPLATE.substitute(
        updated=e(updated), n_ready=len(ready), n_sched=len(scheduled), best=best,
        todo="".join(todo) or '<li class="empty">You\'re all caught up.</li>',
        goals=goals,
        best_title=e(titles.get(rows[0][1], rows[0][1])) if rows else "",
        ready=ready_html, sched=sched_html, perf=perf_html,
        log=e(log_text), log_date=e(log_date))
    page = page.replace("<title>Nethermind Daily</title>", f"<title>{e(channel.get('name'))} Daily</title>", 1)   # the template names the original channel
    (OUT / "dashboard.html").write_text(page)
    print(f"wrote {OUT / 'dashboard.html'} ({len(page) // 1024} KB)")


TEMPLATE = Template((HERE / "studio" / "dashboard_template.html").read_text())

if __name__ == "__main__":
    main()
