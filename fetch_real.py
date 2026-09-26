"""
fetch_real.py — fetch real public-domain/CC0/CC-BY photos from Wikimedia
Commons for a config's "kb" segments.

    python3 fetch_real.py cfg/my_topic.json [--force]

Scans every {"t":"kb", "src":..., "real":{"query":...}} segment. For each
"src" not already in assets/ (or every one, with --force), searches Wikimedia
Commons, picks the first result whose license is explicitly "Public domain",
"CC0", or plain "CC BY" (Commons' own curator-reviewed metadata, not a
user-supplied tag). CC BY-SA and CC BY-NC are deliberately excluded — SA's
copyleft and NC's commercial restriction are different risk categories this
script doesn't attempt to navigate. Downloads the image and prints the source
URL + license + (for CC BY) the required attribution string, for the config's
"credit" field (real content needs real credit, unlike Gemini's "ART:
ORIGINAL, AI-GENERATED").

Other real-content sources considered and dropped for this script:
  - Library of Congress: behind a Cloudflare bot-challenge, not reliably
    fetchable from a script.
  - archive.org comics collection: NOT used here — it's open-upload with
    unreliable/user-supplied license tags (verified: a search filtered to
    "public domain" surfaced an actual 1977 Marvel comic and a 2002 DC/
    Vertigo comic sitting right next to genuinely PD titles). Comic scans
    are a manual, per-issue, human-verified job — see README.md.
"""
import html, json, os, re, sys, time
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
from channel import DATA, PKG  # the data folder (this folder unless NETHER_DATA is set)
A = os.path.join(DATA, "assets")
UA = "ContentPipelineBot/1.0 (single-operator research/educational use)"
OK_LICENSES = {"public domain", "cc0"}
OK_LICENSE_PREFIXES = ("cc by ",)  # plain CC BY only — not "cc by-sa"/"cc by-nc"
CREDIT_START, CREDIT_END = "── image credits ──", "── end image credits ──"


def _strip_html(s):
    return re.sub(r"<[^>]+>", "", html.unescape(s or "")).strip()


def search(query, limit=5):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrlimit": limit, "gsrnamespace": 6,
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1600,
    }
    r = requests.get("https://commons.wikimedia.org/w/api.php", params=params,
                      headers={"User-Agent": UA}, timeout=15)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    out = []
    for p in pages.values():
        title = p.get("title", "")
        if not title.lower().endswith((".jpg", ".jpeg", ".png")):
            continue  # skip PDF/document scans — their thumbnail is a JPG but the match was on OCR'd text, not the image itself
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        license_ = (meta.get("LicenseShortName", {}).get("value") or "").strip().lower()
        url = ii.get("thumburl") or ii.get("url")
        if not url:
            continue
        out.append({
            "title": p.get("title"), "url": url, "license": license_,
            "artist": _strip_html(meta.get("Artist", {}).get("value", "")),
            "page": f"https://commons.wikimedia.org/wiki/{p.get('title', '').replace(' ', '_')}",
        })
    return out


def _license_ok(license_):
    return license_ in OK_LICENSES or license_.startswith(OK_LICENSE_PREFIXES)


def apply_credits(vid, credits):
    """Write/refresh a CC BY attribution block in this video's YouTube description (real content needs real
    credit — CC0/public domain need none). Idempotent: re-running fetch_real replaces the old block rather
    than piling up duplicates. Silently does nothing if there's no packaging file yet for this id."""
    lines, seen = [], set()
    for c in credits:
        if not c["license"].startswith(OK_LICENSE_PREFIXES):
            continue
        who = c.get("artist") or "Wikimedia Commons"
        if who in seen:
            continue
        seen.add(who)
        lines.append(f"{who} — {c['page']} (CC BY, via Wikimedia Commons)")
    if not lines:
        return False
    p = PKG / f"{vid}.json"
    if not p.exists():
        return False
    pkg = json.loads(p.read_text())
    desc = pkg.get("youtube_description", "")
    base = re.sub(rf"\n*{re.escape(CREDIT_START)}.*?{re.escape(CREDIT_END)}", "", desc, flags=re.S).rstrip()
    pkg["youtube_description"] = base + f"\n\n{CREDIT_START}\n" + "\n".join(lines) + f"\n{CREDIT_END}"
    p.write_text(json.dumps(pkg, indent=1, ensure_ascii=False) + "\n")
    return True


def fetch(query, out_path):
    for cand in search(query):
        if not _license_ok(cand["license"]):
            continue
        for wait in (0, 10, 30, 60):  # Wikimedia rate-limits bursts with 429
            time.sleep(wait)
            img = requests.get(cand["url"], headers={"User-Agent": UA}, timeout=30)
            if img.status_code != 429:
                break
            print(f"  rate-limited by Wikimedia, retrying in {wait or 10}s ...")
        img.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(img.content)
        return cand
    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    force = "--force" in sys.argv
    cfg = json.load(open(sys.argv[1]))
    seen = set()
    credits = []
    for s in cfg["segments"]:
        v = s["vis"]
        if v.get("t") != "kb" or "real" not in v or v["src"] in seen:
            continue
        seen.add(v["src"])
        out = os.path.join(A, v["src"])
        if os.path.exists(out) and not force:
            print(f"  have  {v['src']}")
            continue
        print(f"  fetch {v['src']}  ({v['real']['query']!r}) ...")
        got = fetch(v["real"]["query"], out)
        if got:
            print(f"  ok    {v['src']}  [{got['license']}]  {got['page']}")
            if got["license"].startswith(OK_LICENSE_PREFIXES) and got["artist"]:
                print(f"        CC BY — attribution required: {got['artist']}")
            credits.append(got)
        else:
            print(f"  MISS  {v['src']}  — no public-domain/CC0/CC-BY result found, try a different query")
    if credits:
        print("\nAdd real sources to this config's \"credit\" field:")
        for c in credits:
            if c["license"].startswith(OK_LICENSE_PREFIXES) and c["artist"]:
                print(f"  {c['page']}  (CC BY — credit: {c['artist']})")
            else:
                print(f"  {c['page']}")
        if apply_credits(cfg["id"], credits):
            print(f"\nAdded CC BY attribution to the description in packaging/{cfg['id']}.json.")
