"""
gen_visuals.py — generate a config's missing "kb" still images with Gemini.

    python3 gen_visuals.py cfg/my_topic.json [--force]

Scans every {"t":"kb", "src":..., "prompt":...} segment in the config. For
each "src" not already in assets/ (or every one, with --force), asks Gemini
for a stylized image and saves it there. "prompt" is segment-specific; a
STYLE_PRESET (below) supplies the house style, so a segment prompt only
needs to describe the scene. Pick a preset with a "style" key on the vis
block (or "edit_style" for an edit_from segment) — default "comic".

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

Needs in .env (see .env.example):
    GEMINI_API_KEY   your Gemini API key
"""
import base64, json, os, sys
from dotenv import load_dotenv
from google import genai

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "assets")
load_dotenv(os.path.join(HERE, ".env"))

MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
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


def generate(prompt, out_path, aspect_ratio="9:16", style="comic"):
    client = genai.Client()
    interaction = client.interactions.create(
        model=MODEL,
        input=STYLE_PRESETS[style] + prompt,
        response_format={"type": "image", "mime_type": "image/jpeg",
                          "aspect_ratio": aspect_ratio, "image_size": "2K"},
    )
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(interaction.output_image.data))


def edit(prompt, base_image_path, out_path, aspect_ratio="9:16"):
    """Edit an existing generated image (e.g. recolor it) instead of generating
    fresh — keeps the same line art/character across segments instead of letting
    each independent generation drift into a different (and possibly riskier)
    design. `prompt` should describe only the change, not the whole scene. No
    style preset here — the base image's own style already carries through."""
    client = genai.Client()
    base_bytes = open(base_image_path, "rb").read()
    interaction = client.interactions.create(
        model=MODEL,
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
