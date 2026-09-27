#!/usr/bin/env python3
"""resilience.py — network readiness, transient-error retries, and the dead-letter guard used
by daily.py and orchestrator.py to survive a Mac that just woke up, a flaky connection, or an
app that got closed mid-job.

    wait_online(max_wait=600)         block (cheap polling) until online, or give up after max_wait
    is_transient_network_error(e)     True for a connection/DNS/timeout error, not other failures
    retry_network(fn, delays=...)     call fn(); retry only transient network errors, growing gaps
    run_with_network_retry(cmd, ...)  like subprocess.run, but retries a transient-looking failure
    error_signature(text)             a short fingerprint of an error, blurred of ids/timestamps
    is_repeat_failure(prev, new)      True if two error texts are "the same failure again"
"""
import re
import socket
import subprocess
import time

# Cheap reachability checks: a raw TCP connect, no HTTP request and no API key needed.
NETWORK_HOSTS = [("api.anthropic.com", 443), ("www.googleapis.com", 443), ("youtube.com", 443)]

_TRANSIENT_PATTERNS = re.compile(
    r"ConnectionError|Connection aborted|Connection refused|Connection reset|EOF occurred|"
    r"Name or service not known|nodename nor servname|Temporary failure in name resolution|"
    r"getaddrinfo failed|gaierror|ETIMEDOUT|ENETUNREACH|EHOSTUNREACH|Network is unreachable|"
    r"Read timed out|ReadTimeout|ConnectTimeout|Max retries exceeded|Errno 22.*Invalid argument|"
    r"Errno 8|Errno 60|Errno 65|Errno 51",
    re.IGNORECASE)


def is_online(timeout=3):
    for host, port in NETWORK_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def wait_online(max_wait=600, poll=10):
    """Poll cheaply until online, up to max_wait seconds (default 10 min) — covers a Mac that
    just woke from sleep and hasn't reconnected yet. Returns True if online, False if it gave up
    (callers should proceed anyway; individual steps retry their own network calls)."""
    if is_online():
        return True
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        time.sleep(min(poll, max(0.0, deadline - time.monotonic())))
        if is_online():
            return True
    return False


def is_transient_network_error(err):
    """err can be an Exception or a plain string (e.g. subprocess stdout+stderr)."""
    if isinstance(err, (ConnectionError, TimeoutError, socket.timeout, socket.gaierror)):
        return True
    text = err if isinstance(err, str) else f"{type(err).__name__}: {err}"
    return bool(_TRANSIENT_PATTERNS.search(text))


def retry_network(fn, delays=(30, 120, 300), on_retry=None):
    """Call fn() (a zero-arg callable — use a lambda/closure for args). Retries only a transient
    network error, waiting a growing gap between tries. Any other exception, or the error on the
    last try, is re-raised so a real bug still surfaces."""
    attempts = (0,) + tuple(delays)
    for i, delay in enumerate(attempts):
        if delay:
            time.sleep(delay)
        try:
            return fn()
        except Exception as e:
            if not is_transient_network_error(e) or i == len(attempts) - 1:
                raise
            if on_retry:
                try:
                    on_retry(i + 1, delay, e)
                except Exception:
                    pass


def run_with_network_retry(cmd, delays=(30, 120, 300), on_retry=None, **kwargs):
    """Like subprocess.run(cmd, **kwargs), but if it fails (nonzero exit) AND the output looks
    like a transient network error, retries with growing gaps. A non-network failure, or the
    result of the last try, is returned as-is (caller checks .returncode as usual)."""
    attempts = (0,) + tuple(delays)
    result = None
    for i, delay in enumerate(attempts):
        if delay:
            time.sleep(delay)
        result = subprocess.run(cmd, **kwargs)
        if result.returncode == 0:
            return result
        text = (result.stdout or "") + (result.stderr or "")
        if not is_transient_network_error(text) or i == len(attempts) - 1:
            return result
        if on_retry:
            try:
                on_retry(i + 1, delay, text)
            except Exception:
                pass
    return result


# Any alphanumeric token containing a digit — ids, hashes, filenames, timestamps — so two
# errors that differ only in *which* file/id/run they hit still fingerprint as the same failure.
_BLUR = re.compile(r"\b\w*\d\w*\b")


def error_signature(text):
    """A short, stable fingerprint of an error message: its first line, with ids/timestamps/
    counts blurred out so the same underlying failure still matches across attempts."""
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    return _BLUR.sub("#", line)[:200]


def is_repeat_failure(prev_error, new_error):
    """True if two error texts represent the same failure happening again."""
    if not prev_error or not new_error:
        return False
    return error_signature(prev_error) == error_signature(new_error)


DEAD_LETTER_NOTE = "\n\n[Needs you — same error as last time; won't retry automatically]"


def is_dead_lettered(error_text):
    return bool(error_text) and DEAD_LETTER_NOTE.strip() in error_text
