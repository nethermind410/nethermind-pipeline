import subprocess
import sys
from pathlib import Path

from clipping_farm.db import DB


def test_asset_exists_with_local_path():
    db = DB()
    asset = db.get_asset("ASSET-000003")
    assert asset is not None
    assert asset["source_id"]
    assert asset["local_path"]
    assert Path(asset["local_path"]).exists()


def test_run_accepts_asset_id_and_source_path_arguments():
    result = subprocess.run(
        [sys.executable, "-m", "clipping_farm.cli", "--help"],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert "--asset-id" in result.stdout
    assert "--source-path" in result.stdout


def test_pipeline_asset_resolution_occurs_before_rights_check():
    source = Path("clipping_farm/pipeline.py").read_text()
    a = source.index("self.db.get_asset(asset_id)")
    b = source.index("self.harness.rights.check(source_id)")
    assert a < b
