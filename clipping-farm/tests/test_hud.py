from clipping_farm.hud import HTML

def test_hud_contains_real_intake_controls():
    assert "UPLOAD VIDEO" in HTML
    assert "INSPECT URL" in HTML
    assert "/api/upload" in HTML
    assert "/api/acquire" in HTML
    assert "REFERENCE" in HTML
    assert "REVIEW CANDIDATES" in HTML
    assert "data.review_candidates" in HTML
    assert "REVIEW ONLY" in HTML
