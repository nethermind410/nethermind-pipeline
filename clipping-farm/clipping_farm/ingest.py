"""Source ingestion contracts. Rights are checked before processing."""
from dataclasses import dataclass
from pathlib import Path
import hashlib

@dataclass
class Source:
    source_id: str
    location: str
    kind: str = "file"

class SourceIngestor:
    def __init__(self, db):
        self.db=db

    def ingest_file(self, source: Source):
        rights=self.db.rights(source.source_id)
        if not rights or rights["state"]!="AUTHORISED":
            raise PermissionError(f"Source {source.source_id} is not AUTHORISED")
        p=Path(source.location).expanduser().resolve()
        if not p.is_file(): raise FileNotFoundError(p)
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        return {"source_id":source.source_id,"path":str(p),"sha256":h,"bytes":p.stat().st_size}
