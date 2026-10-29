"""Nonsecret current-tree guard against accidentally tracking local environment values."""
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def test_local_env_is_ignored_and_not_tracked():
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".env"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    )
    assert tracked.returncode != 0
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", ".env"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    )
    assert ignored.returncode == 0


def test_public_example_has_no_filled_runtime_credentials():
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assignments = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    names = [line.split("=", 1)[0] for line in assignments]
    assert "AUTH_SECRET" in names
    assert "MENU_ADMIN_KEY" not in names
    assert all(line.split("=", 1)[1].strip() == "" for line in assignments)
