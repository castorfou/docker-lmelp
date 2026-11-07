"""
Tests for the weekly mongo:8 kernel watch (issue #81).

mongodb.Dockerfile is pinned on mongo:8.2: mongod 8.0.21+, 8.3 and 9.0 refuse to
start on Ubuntu 7.0 kernels (SERVER-136848). The mongo-kernel-watch workflow runs
scripts/check_mongo_kernel_fix.sh every week on an ubuntu-24.04 runner. The day
mongo:8 starts there, the script opens a single switch-back issue and sends one
ntfy notification. The ntfy topic acts as a password: it must never be printed.
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml


SCRIPT = Path("scripts/check_mongo_kernel_fix.sh")
WORKFLOW = Path(".github/workflows/mongo-kernel-watch.yml")

ISSUE_TITLE = "Revenir à mongo:8 : SERVER-136848 corrigé"
NTFY_TITLE = "docker-lmelp - mongo:8 démarre sur noyau Ubuntu 7.0"
ISSUE_URL = "https://github.com/castorfou/docker-lmelp/issues/999"
TOPIC = "secret-topic-a1b2c3"
NTFY_SERVER = "https://ntfy.example.org"
KERNEL = "7.0.0-1017-azure"

BLOCKED_OUTPUT = (
    "MongoDB cannot start: Linux kernel versions 6.19 and newer has a known "
    "incompatibility with this version of MongoDB."
)
FIXED_OUTPUT = 'db version v8.3.20\nBuild Info: {\n    "version": "8.3.20"\n}'


class TestScriptStatic:
    def test_script_exists(self):
        assert SCRIPT.is_file()

    def test_script_is_executable(self):
        assert SCRIPT.stat().st_mode & stat.S_IXUSR

    def test_script_has_valid_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr

    def test_script_never_traces_commands(self):
        """set -x would print the ntfy URL, hence the topic, in the run logs."""
        code = [
            line
            for line in SCRIPT.read_text().splitlines()
            if not line.lstrip().startswith("#")
        ]
        assert not [line for line in code if "set -" in line and "x" in line]

    def test_script_runs_mongo_8_version(self):
        content = SCRIPT.read_text()
        assert (
            "docker run --rm --pull always --entrypoint mongod mongo:8 --version"
            in (content)
        )


class TestWorkflow:
    @pytest.fixture(scope="class")
    def workflow(self):
        return yaml.safe_load(WORKFLOW.read_text())

    @staticmethod
    def _triggers(workflow):
        # PyYAML reads the bare `on:` key as the boolean True.
        return workflow.get("on", workflow.get(True))

    def test_triggers_are_weekly_schedule_and_manual(self, workflow):
        triggers = self._triggers(workflow)
        assert set(triggers) == {"schedule", "workflow_dispatch"}
        crons = [entry["cron"] for entry in triggers["schedule"]]
        assert len(crons) == 1
        minute, hour, dom, month, dow = crons[0].split()
        assert (dom, month) == ("*", "*")
        assert dow != "*", "the watch should run once a week"

    def test_single_job_on_ubuntu_24_04(self, workflow):
        jobs = list(workflow["jobs"].values())
        assert len(jobs) == 1
        assert jobs[0]["runs-on"] == "ubuntu-24.04"

    def test_minimal_permissions(self, workflow):
        assert workflow["permissions"] == {"issues": "write", "contents": "read"}

    def test_kernel_is_printed(self, workflow):
        runs = [
            s.get("run", "") for s in next(iter(workflow["jobs"].values()))["steps"]
        ]
        assert any("uname -r" in run for run in runs)

    def test_logic_lives_in_the_script(self, workflow):
        steps = next(iter(workflow["jobs"].values()))["steps"]
        step = next(s for s in steps if str(SCRIPT) in s.get("run", ""))
        assert step["run"].strip() == str(SCRIPT)
        env = step["env"]
        assert env["GH_TOKEN"] == "${{ github.token }}"
        assert env["NTFY_SERVER_URL"] == "${{ secrets.NTFY_SERVER_URL }}"
        assert env["NTFY_TOPIC"] == "${{ secrets.NTFY_TOPIC }}"


class TestScriptBehaviour:
    """Run the script with stubbed docker / gh / curl / uname binaries."""

    @staticmethod
    def _stub(bin_dir: Path, name: str, body: str) -> None:
        path = bin_dir / name
        path.write_text(
            f'#!/bin/bash\nprintf "%s\\n" "{name} $*" >> "$CALLS_LOG"\n{body}\n'
        )
        path.chmod(0o755)

    def _run(
        self,
        tmp_path: Path,
        docker_output: str,
        docker_exit: int,
        existing_issues: int = 0,
        curl_exit: int = 0,
        ntfy: bool = True,
    ):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (tmp_path / "docker_output").write_text(docker_output)
        self._stub(
            bin_dir,
            "docker",
            f'cat "{tmp_path / "docker_output"}"\nexit {docker_exit}',
        )
        self._stub(
            bin_dir,
            "gh",
            'case "$1 $2" in\n'
            f'  "issue list") echo {existing_issues} ;;\n'
            f'  "issue create") echo "{ISSUE_URL}" ;;\n'
            "esac",
        )
        self._stub(bin_dir, "curl", f"exit {curl_exit}")
        self._stub(bin_dir, "uname", f"echo {KERNEL}")

        calls_log = tmp_path / "calls.log"
        calls_log.touch()
        env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "CALLS_LOG": str(calls_log),
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REPOSITORY": "castorfou/docker-lmelp",
            "GITHUB_RUN_ID": "4242",
        }
        env.pop("NTFY_SERVER_URL", None)
        env.pop("NTFY_TOPIC", None)
        if ntfy:
            env["NTFY_SERVER_URL"] = NTFY_SERVER
            env["NTFY_TOPIC"] = TOPIC
        result = subprocess.run(
            ["bash", str(SCRIPT)], env=env, capture_output=True, text=True
        )
        return result, calls_log.read_text()

    @staticmethod
    def _issue_created(calls: str) -> bool:
        return "gh issue create" in calls

    @staticmethod
    def _curl_called(calls: str) -> bool:
        return any(line.startswith("curl ") for line in calls.splitlines())

    # --- the three outcomes of the mongo:8 test --------------------------------

    def test_still_blocked_succeeds_without_issue_nor_notification(self, tmp_path):
        result, calls = self._run(tmp_path, BLOCKED_OUTPUT, docker_exit=62)
        assert result.returncode == 0, result.stdout + result.stderr
        assert not self._issue_created(calls)
        assert not self._curl_called(calls)

    def test_unknown_failure_fails_and_shows_output(self, tmp_path):
        output = "Error response from daemon: pull access denied for mongo"
        result, calls = self._run(tmp_path, output, docker_exit=125)
        assert result.returncode != 0
        assert output in result.stdout + result.stderr
        assert not self._issue_created(calls)
        assert not self._curl_called(calls)

    def test_exit_zero_with_old_series_fails(self, tmp_path):
        """mongo:8 resolving to a series without the kernel check is not the fix."""
        result, calls = self._run(tmp_path, "db version v8.2.5\n", docker_exit=0)
        assert result.returncode != 0
        assert not self._issue_created(calls)
        assert not self._curl_called(calls)

    @pytest.mark.parametrize("version", ["v8.3.20", "v9.0.1", "v10.0.0"])
    def test_fixed_opens_issue_and_notifies(self, tmp_path, version):
        result, calls = self._run(tmp_path, f"db version {version}\n", docker_exit=0)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "gh label create mongo-kernel-watch" in calls
        assert self._issue_created(calls)
        create = calls[calls.index("gh issue create") : calls.index("curl ")]
        assert ISSUE_TITLE in create
        assert "--label mongo-kernel-watch" in create
        assert version in create
        assert KERNEL in create
        assert "https://github.com/castorfou/docker-lmelp/actions/runs/4242" in create
        assert "- [ ] `mongodb.Dockerfile`" in create
        assert "mongo-kernel-watch.yml" in create
        assert TOPIC not in create

        curl = next(line for line in calls.splitlines() if line.startswith("curl "))
        assert f"{NTFY_SERVER}/{TOPIC}" in curl
        assert f"Title: {NTFY_TITLE}" in curl
        assert f"Click: {ISSUE_URL}" in curl
        assert "Priority: default" in curl
        assert ISSUE_URL in calls[calls.index("curl ") :]

    def test_fixed_never_prints_topic(self, tmp_path):
        result, _ = self._run(tmp_path, FIXED_OUTPUT, docker_exit=0)
        assert result.returncode == 0
        assert TOPIC not in result.stdout + result.stderr

    # --- duplicates and ntfy edge cases ----------------------------------------

    def test_existing_issue_does_nothing(self, tmp_path):
        result, calls = self._run(
            tmp_path, FIXED_OUTPUT, docker_exit=0, existing_issues=1
        )
        assert result.returncode == 0
        assert "gh issue list" in calls
        assert "--state all" in calls
        assert not self._issue_created(calls)
        assert not self._curl_called(calls)

    def test_missing_ntfy_secrets_warns_and_still_opens_issue(self, tmp_path):
        result, calls = self._run(tmp_path, FIXED_OUTPUT, docker_exit=0, ntfy=False)
        assert result.returncode == 0
        assert self._issue_created(calls)
        assert not self._curl_called(calls)
        assert "NTFY" in result.stdout + result.stderr

    def test_ntfy_failure_fails_after_issue_creation(self, tmp_path):
        result, calls = self._run(tmp_path, FIXED_OUTPUT, docker_exit=0, curl_exit=22)
        assert result.returncode != 0
        assert calls.index("gh issue create") < calls.index("curl ")
        assert TOPIC not in result.stdout + result.stderr
