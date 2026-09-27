"""
Tests for scripts/nas/nightly-sync.sh and the Calibre -> mobile app chain docs.

nightly-sync.sh runs on the NAS host (DSM Task Scheduler, not in a container):
it stops the calibre-web-automated (CWA) container, rsyncs the Calibre Desktop
library (synced to the NAS by Synology Drive) into CWA's books/ folder, then
restarts CWA. The lmelp-export container reads that CWA library through
CALIBRE_HOST_PATH, so this script must always complete before lmelp-export's
daily anacron run (issue #68, lmelp-mobile#135).
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml


SCRIPT = Path("scripts/nas/nightly-sync.sh")

NAS_DEFAULTS = {
    "CALIBRE_SOURCE_PATH": (
        "/volume1/homes/guillaume/Backup/framework/home/guillaume/Calibre Library"
    ),
    "CWA_BOOKS_PATH": "/volume1/docker/calibre-web-automated/books",
    "CWA_CONTAINER": "calibre-web-automated",
    "NIGHTLY_SYNC_LOG": "/volume1/docker/calibre-web-automated/rsync-nightly.log",
}


class TestNightlySyncScriptStatic:
    """Static checks on the versioned nightly-sync.sh."""

    def test_script_exists(self):
        assert SCRIPT.is_file(), f"{SCRIPT} should be versioned in this repo"

    def test_script_is_executable(self):
        assert SCRIPT.stat().st_mode & stat.S_IXUSR, f"{SCRIPT} should be +x"

    def test_script_has_valid_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr

    def test_script_uses_nounset_and_pipefail(self):
        """No -e on purpose: the script checks each step itself so every
        failure gets an explicit message in the DSM Task Scheduler run detail."""
        assert "set -uo pipefail" in SCRIPT.read_text()

    @pytest.mark.parametrize(("var", "default"), NAS_DEFAULTS.items())
    def test_nas_default_is_overridable_by_env(self, var, default):
        """Paths keep the NAS values by default but can be overridden, so the
        script behaves identically on the NAS and stays testable."""
        content = SCRIPT.read_text()
        assert f'"${{{var}:-{default}}}' in content, (
            f"{SCRIPT} should read {var} with {default!r} as default"
        )


class TestNightlySyncScriptBehaviour:
    """Run the script with stubbed docker/rsync binaries recording their calls.

    The docker stub keeps the container state in a file, so that
    `docker inspect -f '{{.State.Running}}'` reflects previous stop/start calls.
    """

    @staticmethod
    def _stub(bin_dir: Path, name: str, body: str) -> None:
        path = bin_dir / name
        path.write_text(f'#!/bin/bash\necho "{name} $*" >> "$CALLS_LOG"\n{body}\n')
        path.chmod(0o755)

    def _run(self, tmp_path: Path, rsync_exit: int = 0, running: bool = True):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        state = tmp_path / "state"
        state.write_text("true" if running else "false")
        self._stub(
            bin_dir,
            "docker",
            f'case "$1" in\n'
            f'  inspect) cat "{state}" ;;\n'
            f'  stop) echo false > "{state}" ;;\n'
            f'  start) echo true > "{state}" ;;\n'
            f"esac",
        )
        self._stub(bin_dir, "rsync", f"exit {rsync_exit}")
        self._stub(bin_dir, "sleep", "exit 0")

        source = tmp_path / "Calibre Library"
        books = tmp_path / "books"
        source.mkdir()
        books.mkdir()
        calls_log = tmp_path / "calls.log"
        calls_log.touch()

        env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "CALLS_LOG": str(calls_log),
            "CALIBRE_SOURCE_PATH": str(source),
            "CWA_BOOKS_PATH": str(books),
            "CWA_CONTAINER": "cwa-test",
            "NIGHTLY_SYNC_LOG": str(tmp_path / "rsync-nightly.log"),
        }
        result = subprocess.run(
            ["bash", str(SCRIPT)], env=env, capture_output=True, text=True
        )
        calls = calls_log.read_text().splitlines()
        return result, calls, source, books

    @staticmethod
    def _index(calls: list[str], prefix: str) -> int:
        matches = [i for i, c in enumerate(calls) if c.startswith(prefix)]
        assert matches, f"expected a call starting with {prefix!r}, got {calls}"
        return matches[0]

    def test_stop_rsync_start_order(self, tmp_path):
        result, calls, _, _ = self._run(tmp_path)
        assert result.returncode == 0, result.stderr
        stop = self._index(calls, "docker stop cwa-test")
        sync = self._index(calls, "rsync")
        start = self._index(calls, "docker start cwa-test")
        assert stop < sync < start, calls

    def test_rsync_copies_source_into_cwa_books(self, tmp_path):
        _, calls, source, books = self._run(tmp_path)
        rsync_call = calls[self._index(calls, "rsync")]
        assert f"{source}/" in rsync_call, rsync_call
        assert str(books) in rsync_call, rsync_call

    def test_cwa_restarted_even_if_rsync_fails(self, tmp_path):
        """A failed rsync must never leave CWA stopped until the next night."""
        result, calls, _, _ = self._run(tmp_path, rsync_exit=1)
        assert result.returncode != 0, "rsync failure should be reported"
        assert any(c.startswith("docker start cwa-test") for c in calls), calls

    def test_aborts_without_sync_if_cwa_not_running(self, tmp_path):
        """A stopped CWA before the run is abnormal: never rsync behind it."""
        result, calls, _, _ = self._run(tmp_path, running=False)
        assert result.returncode != 0
        assert not any(c.startswith(("rsync", "docker stop")) for c in calls), calls

    def test_run_is_logged(self, tmp_path):
        self._run(tmp_path)
        log = tmp_path / "rsync-nightly.log"
        assert log.is_file() and log.read_text().strip(), (
            "the script should append its run to NIGHTLY_SYNC_LOG"
        )


class TestCalibreToMobileDocs:
    """The full chain is documented in a user guide page."""

    PAGE = Path("docs/user/calibre-vers-app-mobile.md")

    def test_page_exists_and_is_in_nav(self):
        assert self.PAGE.is_file()
        with open("docs/user/.nav.yml") as f:
            nav = yaml.safe_load(f)["nav"]
        pages = [next(iter(item.values())) for item in nav]
        assert self.PAGE.name in pages, f"{self.PAGE.name} missing from nav"

    @pytest.mark.parametrize(
        "needle",
        [
            "nightly-sync.sh",
            "CALIBRE_HOST_PATH",
            "export-and-publish-release",
            "data-v",
            "rsync-nightly.log",
            "publish-data-release.log",
            "UTC",
        ],
    )
    def test_page_covers_each_link_of_the_chain(self, needle):
        assert needle in self.PAGE.read_text()


class TestNoStaleDataLatestTag:
    """lmelp-export publishes to data-v{ROOM_VERSION}; data-latest is obsolete."""

    @pytest.mark.parametrize(
        "path",
        [
            "docker-compose.yml",
            ".env.example",
            ".env.nas.example",
            "docs/user/export-android.md",
        ],
    )
    def test_no_data_latest_reference(self, path):
        assert "data-latest" not in Path(path).read_text(), (
            f"{path} still references the obsolete 'data-latest' release tag"
        )
