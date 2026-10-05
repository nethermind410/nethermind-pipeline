from pathlib import Path
from unittest.mock import patch

from clipping_farm.frames import FrameSampler


def test_sampling_different_windows_never_reuses_other_candidate_frames(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    sampler = FrameSampler(workdir=tmp_path / "frames")

    def fake_ffmpeg(args, **_kwargs):
        Path(args[-1]).write_bytes(f"frame@{args[3]}".encode())

    with patch("clipping_farm.frames.subprocess.run", side_effect=fake_ffmpeg) as run:
        first = sampler.sample("source-1", source, 20, count=2, start=0, end=4)
        second = sampler.sample("source-1", source, 20, count=2, start=10, end=14)

    assert run.call_count == 6
    assert {frame["path"] for frame in first}.isdisjoint(
        {frame["path"] for frame in second}
    )
    assert [Path(frame["path"]).read_bytes() for frame in first] == [
        b"frame@0.000",
        b"frame@4.000",
    ]
    assert [Path(frame["path"]).read_bytes() for frame in second] == [
        b"frame@10.000",
        b"frame@14.000",
    ]
