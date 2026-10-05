import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from clipping_farm.media import FFmpegMedia


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
class MediaFixtureTests(unittest.TestCase):
    def test_generated_fixture_can_be_probed_and_cut(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "fixture.mp4"
            clip = root / "clip.mp4"
            subprocess.run([
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
                "-t", "12", "-c:v", "libx264", "-c:a", "aac", str(source),
            ], check=True, capture_output=True)
            media = FFmpegMedia()
            metadata = media.probe(source)
            self.assertGreater(float(metadata["format"]["duration"]), 11)
            media.cut(source, clip, 2, 8)
            clip_meta = media.probe(clip)
            self.assertTrue(clip.exists())
            self.assertGreater(float(clip_meta["format"]["duration"]), 5)
            self.assertLess(float(clip_meta["format"]["duration"]), 7)


if __name__ == "__main__":
    unittest.main()
