"""OCR fallback for screen recordings with no trustworthy speech transcript."""
import difflib
import re
import shutil
import subprocess

from .candidates import generate_candidates


class ScreenTextAnalyzer:
    def __init__(self, ocr=None):
        self.ocr = ocr or self._tesseract

    @staticmethod
    def _tesseract(path):
        if not shutil.which("tesseract"):
            return ""
        result = subprocess.run(
            ["tesseract", str(path), "stdout", "--psm", "6"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout if result.returncode == 0 else ""

    @staticmethod
    def _normalize(text):
        return " ".join((text or "").split())

    @staticmethod
    def _similarity(left, right):
        left_words = set(re.findall(r"[a-z0-9]{3,}", left.casefold()))
        right_words = set(re.findall(r"[a-z0-9]{3,}", right.casefold()))
        if not left_words or not right_words:
            return difflib.SequenceMatcher(None, left.casefold(), right.casefold()).ratio()
        return len(left_words & right_words) / len(left_words | right_words)


    def detect(self, frames, *, duration):
        snapshots = []
        for frame in sorted(frames, key=lambda item: float(item["time"])):
            text = self._normalize(self.ocr(frame["path"]))
            if not text:
                continue
            if snapshots:
                if self._similarity(snapshots[-1]["text"], text) >= 0.85:
                    continue
            snapshots.append({"time": float(frame["time"]), "text": text})

        if len(snapshots) < 2:
            return []

        segments = []
        for index, item in enumerate(snapshots):
            end = snapshots[index + 1]["time"] if index + 1 < len(snapshots) else float(duration)
            if end - item["time"] >= 8:
                segments.append({"start": item["time"], "end": end, "text": item["text"]})
        return segments

    def candidates(self, frames, *, duration):
        candidates = generate_candidates(self.detect(frames, duration=duration))
        for candidate in candidates:
            candidate.source_modality = "screen_ocr"
            candidate.decision = "REVIEW"
        return candidates
