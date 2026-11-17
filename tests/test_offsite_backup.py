"""Off-server backup (deploy/offsite.sh) with fake rclone/wget on PATH."""
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "deploy" / "offsite.sh"
SH = shutil.which("sh")
pytestmark = pytest.mark.skipif(SH is None, reason="needs a POSIX sh")


def _fake(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run(tmp_path, *, rclone_exit=0, creds=True):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    _fake(bin_dir, "rclone", f'echo "rclone $*" >> "{log.as_posix()}"; exit {rclone_exit}')
    _fake(bin_dir, "wget", f'echo "wget $*" >> "{log.as_posix()}"')
    backups = tmp_path / "backups"
    backups.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("RCLONE_", "B2_", "SENTRY_"))}
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["B2_BUCKET"] = "luma-test"
    env["OFFSITE_STATUS_FILE"] = str(backups / "offsite-status.txt")
    env["SENTRY_DSN"] = "https://abc123@o1.ingest.de.sentry.io/42"
    if creds:
        env["RCLONE_CONFIG_B2_ACCOUNT"] = "id"
        env["RCLONE_CONFIG_B2_KEY"] = "key"
    result = subprocess.run([SH, str(SCRIPT), "once"], env=env, capture_output=True, text=True, timeout=60)
    calls = log.read_text(encoding="utf-8") if log.exists() else ""
    status = backups / "offsite-status.txt"
    return result, calls, status.read_text(encoding="utf-8") if status.exists() else ""


def test_idles_without_b2_credentials(tmp_path):
    result, calls, _ = _run(tmp_path, creds=False)
    assert result.returncode == 1
    assert "not set" in result.stderr
    assert calls == ""


def test_copies_dumps_and_mirrors_photos(tmp_path):
    result, calls, status = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "rclone copy /backups b2:luma-test/db --include luma-*.dump" in calls
    assert "rclone delete b2:luma-test/db --min-age 14d --b2-hard-delete" in calls
    assert "rclone sync photos:luma-private b2:luma-test/photos --b2-hard-delete" in calls
    assert "wget" not in calls
    assert status.split()[1] == "ok"


def test_failure_is_reported_to_sentry(tmp_path):
    result, calls, status = _run(tmp_path, rclone_exit=1)
    assert result.returncode == 1
    assert "FAILED" in status
    assert "https://o1.ingest.de.sentry.io/api/42/store/" in calls
    assert "sentry_key=abc123" in calls


def test_compose_offsite_service_does_not_block_deploys():
    compose = (ROOT / "deploy" / "compose.vds.yaml").read_text(encoding="utf-8")
    block = compose[compose.index("  offsite:"):compose.index("\n  storage:")]
    # Optional credentials: a deploy without them must still start every container.
    assert "RCLONE_CONFIG_B2_ACCOUNT: ${B2_ACCOUNT_ID:-}" in block
    assert "RCLONE_CONFIG_B2_KEY: ${B2_APPLICATION_KEY:-}" in block
    assert "image: rclone/rclone:1." in block
    # Downloads go over the S3 API: B2's native download hosts are blocked from Turkey.
    assert "RCLONE_CONFIG_B2S3_ENDPOINT: ${B2_S3_ENDPOINT:-" in block
    drill = (ROOT / "deploy" / "restore-drill.sh").read_text(encoding="utf-8")
    assert "b2s3:" in drill and '"b2:' not in drill
    assert "../../backups:/backups" in block
