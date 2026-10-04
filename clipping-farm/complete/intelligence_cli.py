from pathlib import Path
import sys
import json

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from intelligence.engine import analyse


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python complete/intelligence_cli.py /path/to/video.mp4")
        sys.exit(1)

    path = sys.argv[1]

    if not Path(path).exists():
        print("ERROR: file does not exist:")
        print(path)
        sys.exit(1)

    print("")
    print("============================================================")
    print(" NETHERMIND LOCAL INTELLIGENCE")
    print("============================================================")
    print("")
    print("SOURCE:", Path(path).resolve())
    print("")
    print("TRANSCRIBING LOCALLY...")
    print("The first run may download the Whisper model.")
    print("")

    result = analyse(path)

    print("=== TRANSCRIPT ===")
    print("Language:", result["transcript"].get("language"))
    print("Characters:", len(result["transcript"].get("text", "")))
    print("Segments:", len(result["transcript"].get("segments", [])))

    print("")
    print("=== INTELLIGENT CANDIDATES ===")

    for i, c in enumerate(result["candidates"], 1):
        print(
            f"[{c['score']}] "
            f"{c['start']:.1f}-{c['end']:.1f}s "
            f"{c['id']}"
        )
        print("   ", c["text"][:240])
        print("    ", ", ".join(c["reasons"]))

    print("")
    print("=== OUTPUT ===")
    print("Transcript:", result["transcript"]["source"])
    print(
        "Analysis:",
        HERE / "intelligence_runs" /
        ("INT-" + __import__("hashlib").sha1(
            str(Path(path).resolve()).encode()
        ).hexdigest()[:12] + ".json")
    )
    print("")


if __name__ == "__main__":
    main()
