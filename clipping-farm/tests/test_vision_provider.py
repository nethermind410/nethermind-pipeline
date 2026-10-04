import base64, tempfile, unittest
from pathlib import Path
from PIL import Image

from clipping_farm.db import DB
from clipping_farm.model_registry import ModelRegistry, ModelSpec
from clipping_farm.provider_health import ProviderHealth
from clipping_farm.vision_provider import (
    VisionRequest, FakeVisionProvider, AdaptiveVisionBrain,
    prepare_image_payload, VisionProviderProtocolError,
)

class VisionProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmpdb=tempfile.NamedTemporaryFile(suffix=".db")
        self.db=DB(self.tmpdb.name)
        self.tmpdir=tempfile.TemporaryDirectory()
        self.frame=Path(self.tmpdir.name)/"frame.png"
        Image.new("RGB",(2000,1200),"white").save(self.frame)
        self.frames=[{"path":str(self.frame),"time":0.0,"sha256":"frame-a"}]

    def tearDown(self):
        self.tmpdb.close()
        self.tmpdir.cleanup()

    def test_image_is_bounded_and_encoded(self):
        payload=prepare_image_payload(self.frames)
        self.assertEqual(len(payload),1)
        self.assertTrue(payload[0]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        raw=base64.b64decode(payload[0]["image_url"]["url"].split(",",1)[1])
        self.assertLessEqual(len(raw),4*1024*1024)

    def test_invalid_frame_rejected(self):
        with self.assertRaises(VisionProviderProtocolError):
            prepare_image_payload([{"path":str(Path(self.tmpdir.name)/"missing.png"),"time":0,"sha256":"x"}])

    def test_six_frame_limit(self):
        frames=self.frames*8
        payload=prepare_image_payload(frames)
        self.assertEqual(len(payload),6)

    def test_fake_provider_escalates_and_then_caches(self):
        fake=FakeVisionProvider(confidence=.91)
        registry=ModelRegistry([
            ModelSpec("deterministic-vision","brain.vision","image","deterministic",0,.72,1),
            ModelSpec("fake-vision","brain.vision","image","cheap",.006,.84,.8),
        ])
        brain=AdaptiveVisionBrain(self.db,registry=registry,providers=[fake],
                                  health=ProviderHealth(cooldown_seconds=999))
        req=VisionRequest("job1","candidate1","visual evidence",self.frames,budget_remaining=.01)
        result,trace=brain.analyse(req)
        self.assertEqual(result.model,"fake-vision")
        self.assertEqual(fake.calls,1)
        self.assertTrue(any(x.get("stage")=="cheap" and x.get("status")=="executed" for x in trace))
        result2,trace2=brain.analyse(req)
        self.assertEqual(fake.calls,1)
        self.assertTrue(any(x.get("status")=="cache_hit" for x in trace2))

    def test_zero_budget_blocks_paid_vision(self):
        fake=FakeVisionProvider()
        registry=ModelRegistry([ModelSpec("fake-vision","brain.vision","image","cheap",.006,.84,.8)])
        brain=AdaptiveVisionBrain(self.db,registry=registry,providers=[fake])
        req=VisionRequest("job2","candidate2","visual evidence",self.frames,budget_remaining=0)
        result,trace=brain.analyse(req)
        self.assertEqual(fake.calls,0)
        self.assertTrue(any(x.get("status")=="blocked" for x in trace))

    def test_failed_provider_is_released_and_health_degrades(self):
        class Bad(FakeVisionProvider):
            def analyse_images(self,request):
                self.calls += 1
                from clipping_farm.vision_provider import VisionProviderTimeout
                raise VisionProviderTimeout("timeout")
        bad=Bad("bad-vision")
        registry=ModelRegistry([ModelSpec("bad-vision","brain.vision","image","cheap",.006,.84,.8)])
        health=ProviderHealth(cooldown_seconds=999)
        brain=AdaptiveVisionBrain(self.db,registry=registry,providers=[bad],health=health)
        req=VisionRequest("job3","candidate3","visual evidence",self.frames,budget_remaining=.01)
        brain.analyse(req)
        costs=self.db.cx.execute("SELECT status FROM costs WHERE job_id='job3'").fetchall()
        self.assertTrue(any(r["status"]=="RELEASED" for r in costs))
        self.assertEqual(health.state("bad-vision"),"HEALTHY")
        brain.analyse(req)
        self.assertEqual(health.state("bad-vision"),"DEGRADED")

if __name__=="__main__":
    unittest.main()
