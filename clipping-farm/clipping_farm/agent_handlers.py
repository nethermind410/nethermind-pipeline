"""Concrete local handlers. Dependency results are persisted in SQLite; workers remain disposable."""
from pathlib import Path
from .analysis import MediaAnalyzer
from .audio import AudioAnalyzer
from .frames import FrameSampler
from .scenes import SceneDetector
from .transcript import build_transcriber
from .screen_text import ScreenTextAnalyzer
from .candidates import generate_candidates, rank, Candidate
from .selection import select
from .brain import DeterministicBrain
from .adaptive_brain import AdaptiveBrain
from .mock_providers import CheapMockProvider, PremiumMockProvider
from .providers import DeterministicProvider
from .provider_adapters import build_configured_providers
from .context import standalone_evidence
from .evidence import build_packet
from .vision import VisionBrain
from .vision_provider import AdaptiveVisionBrain, VisionRequest, build_configured_vision_providers
from .multimodal import MultimodalCandidateBrain
from .qc import run_qc
from .repair import repair_candidate
from .export import write_review_manifest
from .intelligence.jev import score_candidate as jev_score_candidate
from .intelligence.context_repair import looks_context_dependent, repair_candidate as repair_context_candidate
from .intelligence.boundary_optimizer import optimize_candidate
from .intelligence.semantic_qc import semantic_qc
from .library import AssetLibrary

class LocalHandlers:

    def __init__(self, db, workdir='clipping_farm_work', transcriber=None):
        self.db = db
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.library = AssetLibrary()
        self.transcriber = transcriber if transcriber is not None else build_transcriber()
        self.meta = MediaAnalyzer(db)
        self.audio = AudioAnalyzer(db)
        self.frames = FrameSampler(db)
        self.scenes = SceneDetector(db)
        self.screen_text = ScreenTextAnalyzer()
        self.vision = VisionBrain(db, max_frames=6)
        self.vision_adaptive = AdaptiveVisionBrain(db, deterministic=self.vision, providers=build_configured_vision_providers())
        self.fusion = MultimodalCandidateBrain()
        self.brain = AdaptiveBrain(db)
        self.brain.register_provider(DeterministicProvider(DeterministicBrain()))
        for provider in build_configured_providers():
            self.brain.register_provider(provider)

    def _path(self, j):
        p = Path(j['payload'].get('source_path') or '')
        if not p.exists():
            raise FileNotFoundError(str(p))
        return p

    def _deps(self, j):
        import json
        out = []
        for dep in json.loads(j['depends_on'] or '[]'):
            row = self.db.cx.execute('SELECT result,state FROM jobs WHERE id=?', (dep,)).fetchone()
            if not row or row['state'] != 'COMPLETE':
                raise RuntimeError(f'dependency {dep} not complete')
            out.append(json.loads(row['result'] or '{}'))
        return out

    def _find(self, results, key, default=None):
        for r in results:
            if key in r:
                return r[key]
        return default

    def metadata(self, j):
        return {'decision': 'complete', 'metadata': self.meta.metadata(j['payload']['source_id'], self._path(j)), 'actual_cost': 0}

    def analyse_audio(self, j):
        return {'decision': 'complete', 'audio': self.audio.analyse(j['payload']['source_id'], self._path(j)), 'actual_cost': 0}

    def analyse_scenes(self, j):
        return {'decision': 'complete', 'scenes': self.scenes.detect(self._path(j)), 'actual_cost': 0}

    def analyse_screen_text(self, j):
        results = self._deps(j)
        transcript = self._find(results, 'transcript', [])
        if any(((item.get('text') or '').strip() for item in transcript)):
            return {'decision': 'complete', 'screen_text': [], 'status': 'skipped_speech_transcript_available', 'actual_cost': 0}
        meta = self._find(results, 'metadata', {})
        duration = float(meta.get('format', {}).get('duration', 0) or 0)
        if duration <= 0:
            return {'decision': 'complete', 'screen_text': [], 'status': 'missing_duration', 'actual_cost': 0}
        source = j['payload']['source_id']
        path = self._path(j)
        count = min(60, max(2, int(duration / 3) + 1))
        frames = self.frames.sample(source, path, duration, count=count, start=0.0, end=duration)
        segments = self.screen_text.detect(frames, duration=duration)
        return {'decision': 'complete', 'screen_text': segments, 'status': 'changes_detected' if segments else 'no_meaningful_screen_changes', 'actual_cost': 0}

    def transcribe(self, j):
        tr = self.transcriber.transcribe(self._path(j))
        return {'decision': 'complete', 'transcript': [s.__dict__ for s in tr.segments], 'language': tr.language, 'actual_cost': 0}

    def generate_candidates(self, j):
        r = self._deps(j)
        transcript = self._find(r, 'transcript', [])
        if any(((item.get('text') or '').strip() for item in transcript)):
            cs = generate_candidates(transcript)
        else:
            cs = generate_candidates(self._find(r, 'screen_text', []))
            for candidate in cs:
                candidate.source_modality = 'screen_ocr'
                candidate.decision = 'REVIEW'
        return {'decision': 'complete', 'candidates': [c.__dict__ for c in cs], 'actual_cost': 0}

    def score_candidates(self, j):
        r = self._deps(j)
        transcript = self._find(r, 'transcript', [])
        audio = self._find(r, 'audio', {})
        scenes = self._find(r, 'scenes', [])
        meta = self._find(r, 'metadata', {})
        duration = float(meta.get('format', {}).get('duration', 0) or 0)
        scored = []

        def jev_fn(candidate_text, start_time, end_time):
            return jev_score_candidate(candidate_text, start_time, end_time)
        for raw in self._find(r, 'candidates', []):
            c = Candidate(**raw)
            ctx = standalone_evidence(c, transcript)
            if transcript:
                optimised = optimize_candidate(c.__dict__, transcript, jev_fn, max_duration=60.0)
                c.start = float(optimised.get('start', c.start))
                c.end = float(optimised.get('end', c.end))
                c.text = str(optimised.get('text', c.text))
            jev = jev_fn(c.text, c.start, c.end)
            c.scores.update({'jev_score': jev.get('jev_score', 0), 'jev_metrics': jev.get('metrics', {}), 'jev_verdict': jev.get('verdict', 'JEV_REVIEW'), 'jev_risks': jev.get('risks', [])})
            repair_trace = {'attempted': False, 'applied': False}
            if transcript and looks_context_dependent(c.text):
                repaired = repair_context_candidate(c.__dict__, transcript, jev_fn, max_duration=60.0)
                repair_trace = repaired.get('context_repair', repair_trace)
                if repair_trace.get('applied'):
                    c.start = float(repaired.get('start', c.start))
                    c.end = float(repaired.get('end', c.end))
                    c.text = str(repaired.get('text', c.text))
                    jev = jev_fn(c.text, c.start, c.end)
                    c.scores.update({'jev_score': jev.get('jev_score', 0), 'jev_metrics': jev.get('metrics', {}), 'jev_verdict': jev.get('verdict', 'JEV_REVIEW'), 'jev_risks': jev.get('risks', [])})
            semantic = semantic_qc({'start': c.start, 'end': c.end, 'text': c.text, 'jev_score': c.scores.get('jev_score', 0), 'jev_verdict': c.scores.get('jev_verdict', ''), 'jev_risks': c.scores.get('jev_risks', [])})
            ctx = standalone_evidence(c, transcript)
            frames = self.frames.sample(j['payload']['source_id'], self._path(j), duration, count=6, start=max(0.0, c.start - 1.0), end=min(duration, c.end + 1.0)) if duration else []
            packet = build_packet(c, transcript, audio, scenes, frames, meta)
            d = self.brain.analyse(build_packet(c, transcript, audio, scenes, frames, meta))
            budget_remaining = max(0.0, float(j.get('budget') or 0) - float(getattr(d, 'actual_cost', 0) or 0))
            vr = VisionRequest(j['id'], f"{j['id']}:{c.start:.3f}:{c.end:.3f}", 'candidate visual evidence', frames, quality_required=0.78, budget_remaining=budget_remaining)
            visual_result, visual_trace = self.vision_adaptive.analyse(vr)
            visual = visual_result.to_dict() if hasattr(visual_result, 'to_dict') else visual_result
            fused = self.fusion.analyse(c.__dict__, visual=visual, audio=audio, transcript=transcript, context=ctx)
            c.scores.update(d.result.scores)
            c.scores.update(fused.scores)
            c.scores.update({'brain_confidence': d.result.confidence, 'brain_decision': d.result.decision, 'brain_evidence': d.result.evidence, 'brain_provider': d.result.model, 'brain_trace': d.trace, 'fusion_confidence': fused.confidence, 'fusion_decision': fused.decision, 'fusion_evidence': fused.evidence, 'missing_modalities': fused.missing_modalities, 'visual_evidence': visual, 'visual_trace': visual_trace, 'evidence_digest': packet.digest(), 'jev_score': jev.get('jev_score', 0), 'jev_metrics': jev.get('metrics', {}), 'jev_verdict': jev.get('verdict', 'JEV_REVIEW'), 'jev_risks': jev.get('risks', []), 'semantic_qc': semantic, 'context_repair': repair_trace})
            fusion_accept = str(fused.decision).upper() == 'ACCEPT'
            jev_accept = float(jev.get('jev_score', 0) or 0) >= 7.5 and str(jev.get('verdict', '')).upper() != 'JEV_REJECT'
            semantic_accept = bool(semantic.get('pass'))
            if c.source_modality == 'screen_ocr':
                c.decision = 'REVIEW'
            elif fusion_accept and jev_accept and semantic_accept:
                c.decision = 'ACCEPT'
            elif str(jev.get('verdict', '')).upper() == 'JEV_REJECT' or not semantic_accept:
                c.decision = 'REVIEW'
            else:
                c.decision = str(fused.decision).upper()
            scored.append(c.__dict__)
        return {'decision': 'complete', 'candidates': scored, 'actual_cost': 0}

    def select_candidates(self, j):
        cs = [Candidate(**x) for x in self._find(self._deps(j), 'candidates', []) if str(x.get('decision', 'REVIEW')).upper() == 'ACCEPT']
        chosen = select(rank(cs), limit=10)
        return {'decision': 'complete', 'selected': [c.__dict__ for c in chosen], 'actual_cost': 0}

    def produce_clips(self, j):
        import hashlib
        from .media import FFmpegMedia
        media = FFmpegMedia(self.db)
        selected = self._find(self._deps(j), 'selected', [])
        selected = [raw for raw in selected if str(raw.get('decision', 'REVIEW')).upper() == 'ACCEPT']
        source = j['payload']['source_id']
        asset_id = j['payload'].get('asset_id')
        reference_mode = str(j['payload'].get('mode', '')).upper() == 'REFERENCE'
        outdir = self.library.ensure(asset_id)['clips'] if reference_mode and asset_id else self.workdir / source / 'clips'
        outdir.mkdir(parents=True, exist_ok=True)
        results = []
        for i, raw in enumerate(selected, 1):
            c = Candidate(**raw)
            out = outdir / (f'reference_{i:03d}.mp4' if reference_mode else f'clip_{i:03d}.mp4')
            media.cut(self._path(j), out, c.start, c.end)
            digest = hashlib.sha256()
            with out.open('rb') as fh:
                while True:
                    chunk = fh.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
            content_hash = digest.hexdigest()
            cache_key = f'clip:{source}:{i}:{c.start}:{c.end}:{content_hash}'
            self.db.put_artifact(cache_key=cache_key, kind='video_clip', path=str(out), content_hash=content_hash, metadata={'source_id': source, 'asset_id': asset_id, 'clip_index': i, 'start': c.start, 'end': c.end, 'candidate_decision': c.decision})
            results.append({**raw, 'path': str(out), 'artifact_cache_key': cache_key, 'artifact_hash': content_hash})
        return {'decision': 'complete', 'clips': results, 'actual_cost': 0}

    def qc(self, j):
        results = []
        for raw in self._find(self._deps(j), 'clips', []):
            c = Candidate(**{k: v for k, v in raw.items() if k in {'start', 'end', 'text', 'scores', 'decision'}})
            artifact_key = raw.get('artifact_cache_key')
            artifact_verification = None
            artifact_ok = True
            if artifact_key:
                artifact_verification = self.db.verify_artifact(artifact_key)
                artifact_ok = artifact_verification.get('valid', False)
            q = run_qc(c, visual_ok=artifact_ok)
            results.append({'candidate': raw, 'qc': q.asdict(), 'artifact_verification': artifact_verification})
        return {'decision': 'complete', 'qc': results, 'actual_cost': 0}

    def repair(self, j):
        repaired = []
        for item in self._find(self._deps(j), 'qc', []):
            raw = item['candidate']
            c = Candidate(**{k: v for k, v in raw.items() if k in {'start', 'end', 'text', 'scores', 'decision'}})
            q = run_qc(c)
            if not q.passed and q.repairable:
                c, q, _ = repair_candidate(c, run_qc, max_repairs=2)
            clip = {'candidate': c.__dict__, 'qc': q.asdict()}
            if 'path' in raw:
                clip['path'] = raw['path']
            if 'artifact_cache_key' in raw:
                clip['artifact_cache_key'] = raw['artifact_cache_key']
            if 'artifact_hash' in raw:
                clip['artifact_hash'] = raw['artifact_hash']
            repaired.append(clip)
        return {'decision': 'complete', 'clips': repaired, 'actual_cost': 0}

    def export_review(self, j):
        source = j['payload']['source_id']
        deps = self._deps(j)
        clips = self._find(deps, 'clips', [])
        review = self._find(deps, 'review_candidates', [])
        if not clips and (not review):
            raise RuntimeError('no reviewable output available')
        path = self.workdir / source / 'review_manifest.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        return {'decision': 'complete', 'manifest': write_review_manifest(path, source, clips, review), 'actual_cost': 0}

    def handlers(self):
        return {'metadata': self.metadata, 'analyse_audio': self.analyse_audio, 'analyse_scenes': self.analyse_scenes, 'analyse_screen_text': self.analyse_screen_text, 'transcribe': self.transcribe, 'generate_candidates': self.generate_candidates, 'score_candidates': self.score_candidates, 'select_candidates': self.select_candidates, 'produce_clips': self.produce_clips, 'qc': self.qc, 'repair': self.repair, 'export_review': self.export_review}
