from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(exist_ok=True)

ACTIVE = {}
LOCK = threading.Lock()


def new_run_id() -> str:
    return "HUD-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


def write_state(run_dir: Path, **updates):
    state_file = run_dir / "HUD_STATE.json"

    with LOCK:
        state = {}
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
            except Exception:
                state = {}

        state.update(updates)
        state["updated_at"] = datetime.now().isoformat(timespec="seconds")
        state_file.write_text(json.dumps(state, indent=2))


def run_pipeline(run_id: str, target: str, authorized: bool):
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    write_state(
        run_dir,
        run_id=run_id,
        target=target,
        authorized=authorized,
        status="RUNNING",
        stage="STARTING",
        progress=0,
    )

    stages = [
        ("DISCOVER", 5),
        ("SOURCE", 10),
        ("RIGHTS", 15),
        ("ACQUIRE", 25),
        ("UNDERSTAND", 45),
        ("FIND MOMENTS", 60),
        ("SCORE", 72),
        ("REPAIR / QC", 85),
        ("EXPORT", 100),
    ]

    try:
        # The existing complete CLI remains the source of truth.
        # This wrapper owns orchestration/status only.
        cmd = [
            sys.executable,
            "-m",
            "complete_cli",
            "complete",
            target,
        ]

        if authorized:
            cmd.append("--authorized")

        process = subprocess.Popen(
            cmd,
            cwd=str(ROOT.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        current_stage = "STARTING"
        progress = 0
        output_lines = []

        for raw in process.stdout:
            line = raw.rstrip()
            output_lines.append(line)

            upper = line.upper()

            for stage, pct in stages:
                if stage in upper:
                    current_stage = stage
                    progress = pct
                    break

            write_state(
                run_dir,
                status="RUNNING",
                stage=current_stage,
                progress=progress,
                output="\n".join(output_lines[-80:]),
            )

        return_code = process.wait()

        # Preserve the real pipeline result rather than inventing success.
        result_files = list(run_dir.rglob("RESULTS.json"))

        if return_code == 0:
            write_state(
                run_dir,
                status="COMPLETE",
                stage="EXPORT",
                progress=100,
                return_code=return_code,
                results=str(result_files[0]) if result_files else None,
                output="\n".join(output_lines[-100:]),
            )
        else:
            write_state(
                run_dir,
                status="FAILED",
                stage=current_stage,
                progress=progress,
                return_code=return_code,
                output="\n".join(output_lines[-100:]),
            )

    except Exception as exc:
        write_state(
            run_dir,
            status="FAILED",
            stage="ERROR",
            error=str(exc),
        )

    finally:
        with LOCK:
            ACTIVE.pop(run_id, None)


class Handler(BaseHTTPRequestHandler):

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/autorun/runs":
            runs = []

            for run_dir in sorted(RUNS.glob("HUD-*"), reverse=True):
                state_file = run_dir / "HUD_STATE.json"

                if not state_file.exists():
                    continue

                try:
                    state = json.loads(state_file.read_text())
                    runs.append(state)
                except Exception:
                    pass

            self._json({"runs": runs[:25]})
            return

        if parsed.path == "/api/autorun/status":
            query = parse_qs(parsed.query)
            run_id = query.get("run_id", [""])[0]

            run_dir = RUNS / run_id
            state_file = run_dir / "HUD_STATE.json"

            if not state_file.exists():
                self._json({"error": "run not found"}, 404)
                return

            try:
                self._json(json.loads(state_file.read_text()))
            except Exception as exc:
                self._json({"error": str(exc)}, 500)

            return

        self._json({"service": "clipping-farm-hud-autorun", "ok": True})

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path != "/api/autorun/start":
            self._json({"error": "not found"}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or "{}")
        except Exception:
            self._json({"error": "invalid JSON"}, 400)
            return

        target = str(payload.get("target", "")).strip()
        authorized = bool(payload.get("authorized", False))

        if not target:
            self._json({"error": "target is required"}, 400)
            return

        if not authorized:
            self._json(
                {
                    "error": "Authorisation confirmation is required before acquisition."
                },
                400,
            )
            return

        run_id = new_run_id()

        with LOCK:
            ACTIVE[run_id] = True

        thread = threading.Thread(
            target=run_pipeline,
            args=(run_id, target, authorized),
            daemon=True,
        )
        thread.start()

        self._json(
            {
                "ok": True,
                "run_id": run_id,
                "status": "STARTING",
            },
            202,
        )

    def log_message(self, *_):
        pass


def main():
    port = int(os.environ.get("CLIPPING_FARM_AUTORUN_PORT", "8766"))

    server = HTTPServer(("127.0.0.1", port), Handler)

    print()
    print("==============================================")
    print(" CLIPPING FARM — FULL AUTO HUD SERVICE")
    print("==============================================")
    print(f" http://127.0.0.1:{port}")
    print()
    print("API:")
    print(" POST /api/autorun/start")
    print(" GET  /api/autorun/status?run_id=...")
    print(" GET  /api/autorun/runs")
    print()
    print("Press Ctrl-C to stop.")
    print()

    server.serve_forever()


if __name__ == "__main__":
    main()
