"""
gen_visuals.py — generate a config's missing "kb" still images.

    python3 gen_visuals.py cfg/my_topic.json [--force]

Scans every {"t":"kb", "src":..., "prompt":...} segment in the config. For
each "src" not already in assets/ (or every one, with --force), asks an
image backend for a stylized image and saves it there. "prompt" is
segment-specific; a STYLE_PRESET (below) supplies the house style, so a
segment prompt only needs to describe the scene. Pick a preset with a
"style" key on the vis block (or "edit_style" for an edit_from segment) —
default "comic".

Presets:
  comic     — Marvel/hero vertical. Bold ink outlines, halftone shading,
              comic-page look. Also enforces original-character-only framing.
  science   — space/odd-facts verticals, for a fact no real photo/diagram
              could show. Realistic NASA-concept-art / documentary-illustration
              style — NOT comic panel style — so it sits naturally next to
              real photos and real charts in the same video.

Keep "comic" prompts to archetypes, poses, palettes and mood — not named
characters or exact costume/logo details. That's a prompting-level habit,
not something the API enforces or guarantees; it's on us to keep the art
clearly original.

Backends (set IMAGE_BACKEND in .env, default "cloudflare" — free):
  cloudflare — Cloudflare Workers AI, @cf/black-forest-labs/flux-1-schnell.
               $0 cost on the free tier (10,000 neurons/day, ~30+ images/day
               at ~325 neurons each). Needs CLOUDFLARE_ACCOUNT_ID +
               CLOUDFLARE_API_TOKEN (a scoped token, Account > Workers AI >
               Edit only — not the Global API Key). Square 1024x1024 output;
               the Ken-Burns renderer already crops/pans arbitrary source
               images into the vertical frame, same as it does with real
               photos, so this isn't a problem.
  gemini     — Google Gemini image generation. Needs GEMINI_API_KEY and an
               AI Studio project with billing enabled (the free tier alone
               hits a 402 "prepayment credits depleted" wall quickly). Kept
               as an optional path, not the default, since it isn't free.

Needs in .env (see .env.example) depending on backend chosen above.
"""
import base64, json, os, sys
import requests
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
A = os.path.join(DATA, "assets")
load_dotenv(os.path.join(DATA, ".env"))

BACKEND = os.environ.get("IMAGE_BACKEND", "cloudflare")
GEMINI_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
CF_MODEL = os.environ.get("CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")

STYLE_PRESETS = {
    "comic": (
        "Authentic comic-book page art style: bold heavy black ink outlines, "
        "dynamic diagonal composition, halftone-dot shading in the shadows, "
        "dramatic high-contrast comic lighting, punchy saturated color palette, "
        "printed comic paper texture. Non-photorealistic. Original character "
        "design only — invented pose, costume and features, not a reproduction "
        "of any specific trademarked character design or logo. Portrait "
        "composition. "
    ),
    "science": (
        "Realistic digital matte-painting illustration style, the kind NASA/ESA "
        "commission for an artist's-impression concept image: naturalistic "
        "lighting and color, smooth painterly rendering, physically plausible "
        "detail. Not a comic panel — no ink outlines, no halftone dots, no "
        "comic paper texture. Portrait composition. "
    ),
    "handdrawn": (
        "Hand-drawn naturalist field-guide illustration style: warm aged-paper "
        "texture, visible hand-inked linework, light watercolor washes, gentle "
        "cross-hatch shading, whimsical and charming, like a page from an "
        "explorer's field notebook. Not photorealistic, not a comic panel — no "
        "halftone dots, no glossy digital rendering. Portrait composition. "
    ),
}


def _generate_cloudflare(prompt, out_path, style="science", steps=8):
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        raise RuntimeError(
            "IMAGE_BACKEND=cloudflare but CLOUDFLARE_ACCOUNT_ID / "
            "CLOUDFLARE_API_TOKEN are not set in .env"
        )
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{CF_MODEL}"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
        json={"prompt": STYLE_PRESETS[style] + prompt, "steps": steps},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Cloudflare Workers AI error: {data.get('errors')}")
    img_bytes = base64.b64decode(data["result"]["image"])
    with open(out_path, "wb") as f:
        f.write(img_bytes)


def _generate_gemini(prompt, out_path, style="comic", aspect_ratio="9:16"):
    from google import genai
    client = genai.Client()
    interaction = client.interactions.create(
        model=GEMINI_MODEL,
        input=STYLE_PRESETS[style] + prompt,
        response_format={"type": "image", "mime_type": "image/jpeg",
                          "aspect_ratio": aspect_ratio, "image_size": "2K"},
    )
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(interaction.output_image.data))


def generate(prompt, out_path, aspect_ratio="9:16", style="comic", backend=None):
    backend = backend or BACKEND
    if backend == "cloudflare":
        _generate_cloudflare(prompt, out_path, style=style)
    elif backend == "gemini":
        _generate_gemini(prompt, out_path, style=style, aspect_ratio=aspect_ratio)
    else:
        raise ValueError(f"Unknown IMAGE_BACKEND: {backend!r} (use 'cloudflare' or 'gemini')")


def edit(prompt, base_image_path, out_path, aspect_ratio="9:16"):
    """Edit an existing generated image (e.g. recolor it) instead of generating
    fresh — keeps the same line art/character across segments instead of letting
    each independent generation drift into a different (and possibly riskier)
    design. `prompt` should describe only the change, not the whole scene. No
    style preset here — the base image's own style already carries through.
    Gemini-only for now — Workers AI's flux-1-schnell doesn't do image edits;
    fall back to a fresh `generate()` call with a fuller prompt if on Cloudflare."""
    from google import genai
    client = genai.Client()
    base_bytes = open(base_image_path, "rb").read()
    interaction = client.interactions.create(
        model=GEMINI_MODEL,
        input=[
            {"type": "image", "data": base64.b64encode(base_bytes).decode("utf-8"), "mime_type": "image/jpeg"},
            {"type": "text", "text": prompt},
        ],
        response_format={"type": "image", "mime_type": "image/jpeg",
                          "aspect_ratio": aspect_ratio, "image_size": "2K"},
    )
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(interaction.output_image.data))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    force = "--force" in sys.argv
    cfg = json.load(open(sys.argv[1]))
    seen = set()
    print(f"  backend: {BACKEND}")
    # two passes: plain "prompt" generations first, then "edit_from" ones,
    # so an edit's base image is guaranteed to already exist on disk.
    segs = list(cfg["segments"])
    for s in sorted(segs, key=lambda s: "edit_from" in s["vis"]):
        v = s["vis"]
        if v.get("t") != "kb" or v["src"] in seen or ("prompt" not in v and "edit_from" not in v):
            continue
        seen.add(v["src"])
        out = os.path.join(A, v["src"])
        if os.path.exists(out) and not force:
            print(f"  have  {v['src']}")
            continue
        if "edit_from" in v:
            base = os.path.join(A, v["edit_from"])
            print(f"  edit  {v['src']}  (from {v['edit_from']}) ...")
            edit(v["prompt"], base, out)
        else:
            style = v.get("style", "comic")
            print(f"  gen   {v['src']} ({style}) ...")
            generate(v["prompt"], out, style=style)
        print(f"  ok    {v['src']}")
