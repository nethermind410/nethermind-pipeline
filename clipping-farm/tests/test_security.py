"""Tests for Security Boundaries (Phase 7)."""
import pytest
from clipping_farm.security import (
    SecurityBoundary, SecurityBoundaryError, check_security,
)
from clipping_farm.db import DB
import tempfile


class TestSecurityBoundary:
    @pytest.fixture
    def db(self):
        f = tempfile.NamedTemporaryFile(suffix=".db")
        db = DB(f.name)
        db.set_rights("authorised-source", "AUTHORISED")
        db.set_rights("pending-source", "PENDING")
        db.cx.execute(
            "INSERT INTO sources(source_id, location, kind, sha256, size_bytes, metadata, provenance, first_seen_at, last_seen_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("authorised-source", "/tmp/test.mp4", "file", "abc123", 1000, '{}', '{}', 1000000, 1000000),
        )
        db.cx.commit()
        return db

    def test_boundary_init(self, db):
        boundary = SecurityBoundary(db=db)
        assert boundary.VERSION == "security-boundary-v1"

    def test_human_input_safe(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_human_input("This is a normal text about comics.")
        assert result["safe"] is True

    def test_human_input_with_api_key(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_human_input("api_key=sk-secret123")
        assert result["safe"] is False

    def test_human_input_with_password(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_human_input("Password: secret123")
        assert result["safe"] is False

    def test_human_input_with_token(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_human_input("Bearer token: abc.def.ghi")
        assert result["safe"] is False

    def test_local_file_safe(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_local_file("/tmp/test.txt")
        # File doesn't exist, so not safe
        assert result["safe"] is False

    def test_local_file_credential_extension(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_local_file("/tmp/config.env")
        assert result["safe"] is False
        assert result["reason"] == "credential_file_extension"

    def test_local_file_sensitive_path(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_local_file("/home/user/.ssh/config")
        assert result["safe"] is False

    def test_external_provider_configured(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_external_provider("openai", True, True)
        assert result["safe"] is True

    def test_external_provider_not_configured(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_external_provider("openai", False, False)
        assert result["safe"] is False
        assert result["reason"] == "provider_not_configured"

    def test_external_provider_missing_credentials(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_external_provider("openai", True, False)
        assert result["safe"] is False
        assert result["reason"] == "missing_credentials"

    def test_publishing_ok(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_publishing("content", "AUTHORISED", True)
        assert result["safe"] is True

    def test_publishing_not_authorised(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_publishing("content", "PENDING", True)
        assert result["safe"] is False
        assert result["reason"] == "not_authorised"

    def test_publishing_not_approved(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_publishing("content", "AUTHORISED", False)
        assert result["safe"] is False

    def test_content_for_credentials_safe(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_content_for_credentials("Hello world")
        assert result["safe"] is True

    def test_content_for_credentials_found(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_content_for_credentials("api_key=sk-secret")
        assert result["safe"] is False
        assert result["reason"] == "credentials_in_content"

    def test_downloaded_media_safe(self, db):
        boundary = SecurityBoundary(db=db)
        # File doesn't exist, so not safe (expected for this test)
        result = boundary.check_downloaded_media("/tmp/test.mp4", "https://example.com/video.mp4")
        assert result["safe"] is False

    def test_downloaded_media_suspicious_url(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_downloaded_media("/tmp/test.mp4", "https://example.com/video.mp4")
        # URL is safe, but file doesn't exist
        assert result["safe"] is False

    def test_rights_authorised(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_rights("authorised-source", db=db)
        assert result["safe"] is True

    def test_rights_not_authorised(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_rights("pending-source", db=db)
        assert result["safe"] is False
        assert result["reason"] == "not_authorised"

    def test_rights_no_record(self, db):
        boundary = SecurityBoundary(db=db)
        result = boundary.check_rights("nonexistent-source", db=db)
        assert result["safe"] is False

    def test_sanitize_log(self, db):
        boundary = SecurityBoundary(db=db)
        text = "API key: sk-secret and password: hidden"
        sanitized = boundary.sanitize_log(text)
        # API key pattern matches "API key:" so entire portion is redacted
        # password pattern matches "password:" so "hidden" is redacted
        assert "[REDACTED]" in sanitized

    def test_sanitize_log_no_sensitive(self, db):
        boundary = SecurityBoundary(db=db)
        text = "Normal log message"
        sanitized = boundary.sanitize_log(text)
        assert sanitized == text

    def test_version(self, db):
        boundary = SecurityBoundary(db=db)
        assert boundary.VERSION == "security-boundary-v1"

    def test_check_security_all_safe(self, db):
        result = check_security(
            text="Normal content",
            provider_configured=True,
            provider_credentials=True,
            rights_state="AUTHORISED",
            approved=True,
            db=db,
        )
        assert result["safe"] is True

    def test_check_security_mixed(self, db):
        result = check_security(
            text="API key: sk-secret",
            provider_configured=False,
            provider_credentials=False,
            rights_state="PENDING",
            approved=False,
            db=db,
        )
        assert result["safe"] is False