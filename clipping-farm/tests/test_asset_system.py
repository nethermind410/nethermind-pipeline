import json
from pathlib import Path

from clipping_farm.db import DB
from clipping_farm.ingest import Source, SourceIngestor
from clipping_farm.library import AssetLibrary
from clipping_farm.reference import ReferenceInspector


def test_local_ingest_creates_asset_library_and_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    media=tmp_path/"demo.mp4"
    media.write_bytes(b"asset-media")

    db=DB(tmp_path/"db.sqlite")
    db.set_rights("source-1","AUTHORISED",{"basis":"test"})
    result=SourceIngestor(db).ingest_file(
        Source("source-1",str(media),metadata={"purpose":"reference"})
    )

    assert result["asset_id"].startswith("ASSET-")
    asset=db.get_asset(result["asset_id"])
    assert asset["purpose"]=="reference"
    assert asset["acquisition_state"]=="ACQUIRED"
    assert Path(asset["local_path"]).is_file()
    manifest=AssetLibrary().asset_dir(asset["asset_id"])/"manifests"/"asset_manifest.json"
    assert manifest.is_file()
    assert json.loads(manifest.read_text())["asset_id"]==asset["asset_id"]


def test_asset_deduplicates_by_hash(tmp_path):
    db=DB(tmp_path/"db.sqlite")
    a,_=db.create_asset(source_type="file",sha256="abc",purpose="reference")
    b,duplicate=db.create_asset(source_type="file",sha256="abc",purpose="reference")
    assert duplicate is True
    assert b["asset_id"]==a["asset_id"]


def test_reference_inspection_does_not_erase_authorisation(tmp_path):
    db=DB(tmp_path/"db.sqlite")
    metadata={
        "source_url":"https://example.com/watch?v=abc",
        "extractor":"example","extractor_key":"Example","id":"abc",
        "title":"Example",
    }
    first=ReferenceInspector().persist(db,metadata)
    db.set_rights(first["source_id"],"AUTHORISED",{"basis":"operator"})
    second=ReferenceInspector().persist(db,metadata)
    assert second["source_id"]==first["source_id"]
    assert db.rights(first["source_id"])["state"]=="AUTHORISED"


def test_reference_dna_file_created(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from clipping_farm.dna import write_reference_dna
    db=DB(tmp_path/"db.sqlite")
    asset,_=db.create_asset(
        source_type="file",purpose="reference",source_id="ref-1",
        original_filename="x.mp4",local_path=str(tmp_path/"x.mp4"),
        metadata={"format":{"duration":30}},
    )
    db.set_rights("ref-1","AUTHORISED")
    job,_=db.add_job(
        "transcribe","transcript_agent",
        {"source_id":"ref-1","asset_id":asset["asset_id"]},
        idempotency_key="dna-test-transcribe",
    )
    db.cx.execute(
        "UPDATE jobs SET state='COMPLETE',result=? WHERE id=?",
        (json.dumps({"transcript":[{"start":0,"end":5,"text":"A surprising opening claim."}]}),job["id"]),
    )
    dna,path=write_reference_dna(db,asset["asset_id"])
    assert path.is_file()
    assert dna["hook"]["opening_text"]=="A surprising opening claim."
