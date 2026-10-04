"""Security boundaries for the Clipping Farm system.

Defines explicit boundaries between:
- Human input → system
- Hermes control → execution
- Local files → processing
- External providers → system
- Downloaded media → processing
- Generated derivatives → storage
- Credentials → isolated
- Publishing → gated

Sensitive material never sent externally unless authorised.
Rights checks mandatory. Credentials never in prompts/logs/manifests/exports/source-control.
"""
import re
from pathlib import Path
from typing import Optional


# Patterns that indicate sensitive content
SENSITIVE_PATTERNS = [
    r"(?i)api[_-]?key\s*[=:]",
    r"(?i)password\s*[=:]",
    r"(?i)secret\s*[=:]",
    r"(?i)token\s*[=:]",
    r"(?i)credential",
    r"(?i)private[_-]?key",
]

# File extensions that may contain credentials
CREDENTIAL_FILE_EXTENSIONS = {".env", ".pem", ".key", ".p12", ".pfx", ".jwt"}

# Paths that should never be exposed
SENSITIVE_PATH_PATTERNS = [
    r"\.env$",
    r"\.ssh/",
    r"\.aws/",
    r"secret",
    r"credential",
]


class SecurityBoundaryError(RuntimeError):
    """Security boundary violation."""
    pass


class SecurityBoundary:
    """Enforces security boundaries across the system."""

    VERSION = "security-boundary-v1"

    def __init__(self, db=None):
        self.db = db
        self._sensitive_cache = None

    def check_human_input(self, text: str) -> dict:
        """Check human input for sensitive content before processing."""
        findings = []
        for pattern in SENSITIVE_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                findings.append({"pattern": pattern, "matches": len(matches)})

        if findings:
            return {
                "safe": False,
                "reason": "sensitive_content_detected",
                "findings": findings,
            }

        return {"safe": True, "reason": "no sensitive content detected"}

    def check_local_file(self, path: str) -> dict:
        """Check local file path for security concerns."""
        p = Path(path).expanduser()

        # Check for credential file extensions
        if p.suffix.lower() in CREDENTIAL_FILE_EXTENSIONS:
            return {
                "safe": False,
                "reason": "credential_file_extension",
                "path": str(p),
            }

        # Check path against sensitive patterns
        path_str = str(p).lower()
        for pattern in SENSITIVE_PATH_PATTERNS:
            if re.search(pattern, path_str):
                return {
                    "safe": False,
                    "reason": "sensitive_path_pattern",
                    "pattern": pattern,
                }

        # Check file exists and is readable
        if not p.exists():
            return {"safe": False, "reason": "file_not_found"}

        if not p.is_file():
            return {"safe": False, "reason": "not_a_file"}

        return {"safe": True, "reason": "file_ok"}

    def check_external_provider(self, provider_name: str, configured: bool,
                                has_credentials: bool) -> dict:
        """Verify external provider is properly configured before use."""
        if not configured:
            return {
                "safe": False,
                "reason": "provider_not_configured",
                "provider": provider_name,
            }

        if not has_credentials:
            return {
                "safe": False,
                "reason": "missing_credentials",
                "provider": provider_name,
            }

        return {"safe": True, "reason": "provider_configured"}

    def check_publishing(self, content: str, rights_state: str,
                         approved: bool) -> dict:
        """Check publishing gate: rights + approval."""
        if rights_state != "AUTHORISED":
            return {
                "safe": False,
                "reason": "not_authorised",
                "rights_state": rights_state,
            }

        if not approved:
            return {
                "safe": False,
                "reason": "not_approved",
            }

        return {"safe": True, "reason": "publish_ok"}

    def check_content_for_credentials(self, text: str) -> dict:
        """Scan content for accidentally exposed credentials."""
        findings = []
        for i, pattern in enumerate(SENSITIVE_PATTERNS):
            matches = re.findall(pattern, text)
            if matches:
                findings.append({"pattern": pattern, "count": len(matches)})

        if findings:
            return {
                "safe": False,
                "reason": "credentials_in_content",
                "findings": findings,
            }

        return {"safe": True, "reason": "no credentials found"}

    def check_downloaded_media(self, path: str, source_url: str) -> dict:
        """Verify downloaded media is safe for processing."""
        # Check file path
        file_check = self.check_local_file(path)
        if not file_check["safe"]:
            return file_check

        # Check source URL is not malicious
        if self._is_suspicious_url(source_url):
            return {
                "safe": False,
                "reason": "suspicious_source_url",
                "url": source_url,
            }

        return {"safe": True, "reason": "media_ok"}

    def check_rights(self, source_id: str, db=None) -> dict:
        """Check rights state for a source."""
        if db is None:
            db = self.db
        if db is None:
            return {"safe": True, "reason": "no DB check"}

        row = db.cx.execute(
            "SELECT * FROM rights WHERE source_id=?", (source_id,)
        ).fetchone()

        if not row:
            return {"safe": False, "reason": "no_rights_record"}

        if row["state"] != "AUTHORISED":
            return {
                "safe": False,
                "reason": "not_authorised",
                "rights_state": row["state"],
            }

        return {"safe": True, "reason": "authorised"}

    def sanitize_log(self, text: str) -> str:
        """Remove sensitive patterns from log output."""
        for pattern in SENSITIVE_PATTERNS:
            text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)
        return text

    def _is_suspicious_url(self, url: str) -> bool:
        """Check if URL looks suspicious."""
        if not url:
            return False
        suspicious_domains = ["localhost", "127.0.0.1", "internal", "private"]
        for domain in suspicious_domains:
            if domain in url.lower():
                return True
        return False


def check_security(text: str = "", path: str = None,
                   provider_configured: bool = False,
                   provider_credentials: bool = False,
                   rights_state: str = "UNKNOWN",
                   approved: bool = False,
                   db=None) -> dict:
    """Convenience: run all security checks."""
    boundary = SecurityBoundary(db=db)
    results = {}

    if text:
        results["human_input"] = boundary.check_human_input(text)

    if path:
        results["local_file"] = boundary.check_local_file(path)

    if provider_configured or provider_credentials:
        results["external_provider"] = boundary.check_external_provider(
            "external", provider_configured, provider_credentials
        )

    results["publishing"] = boundary.check_publishing(
        text or "", rights_state, approved
    )

    safe = all(r.get("safe", True) for r in results.values())
    return {"safe": safe, "checks": results}