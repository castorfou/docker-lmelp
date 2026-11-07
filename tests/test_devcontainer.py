"""
Tests for the devcontainer Docker-in-Docker setup (issue #83).

dockerd must start in the devcontainer on hosts whose kernel no longer ships the
legacy ``ip_tables`` module (Ubuntu 7.0 kernels): only nftables works there.

The ``docker-in-docker:2`` feature tag is frozen at 2.17.0, which picks
``iptables-legacy`` at image build time, so dockerd fails with
"can't initialize iptables table `nat'". Version 4.0.0 and later pick the iptables
alternative at container start (``iptablesSwitchAtRuntime``, true by default):
legacy only when ``ip_tables`` is loaded, nft otherwise.

Docker-in-Docker comes from the PyFoundry template (``docker_in_docker`` in
``.cruft.json``, castorfou/PyFoundry#117), never from a hand-made addition.
"""

import json
import re
from pathlib import Path

import pytest


DEVCONTAINER = Path(".devcontainer/devcontainer.json")
LOCK = Path(".devcontainer/devcontainer-lock.json")
CRUFT = Path(".cruft.json")

DIND_FEATURE = re.compile(
    r"^ghcr\.io/devcontainers/features/docker-in-docker:(?P<major>\d+)$"
)
# First docker-in-docker release that selects iptables at container start.
MIN_DIND_VERSION = (4, 0, 0)


def strip_jsonc_comments(text: str) -> str:
    """Remove ``//`` and ``/* */`` comments that sit outside JSON strings."""
    out: list[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
        elif c == '"':
            in_string = True
            out.append(c)
            i += 1
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end == -1 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def load_jsonc(path: Path) -> dict:
    return json.loads(strip_jsonc_comments(path.read_text(encoding="utf-8")))


def parse_version(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


@pytest.fixture(scope="module")
def devcontainer() -> dict:
    return load_jsonc(DEVCONTAINER)


@pytest.fixture(scope="module")
def lock() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))


def dind_entries(features: dict) -> list[tuple[str, int]]:
    return [
        (key, int(match["major"]))
        for key in features
        if (match := DIND_FEATURE.match(key))
    ]


class TestJsoncReader:
    def test_keeps_double_slashes_inside_strings(self):
        text = '{"url": "https://example.org/a//b"} // trailing'
        assert json.loads(strip_jsonc_comments(text)) == {
            "url": "https://example.org/a//b"
        }

    def test_strips_line_and_block_comments(self):
        text = '{\n  // line\n  "a": 1, /* block\n */ "b": "x\\"//y"\n}'
        assert json.loads(strip_jsonc_comments(text)) == {"a": 1, "b": 'x"//y'}

    def test_reads_the_real_devcontainer(self, devcontainer):
        assert "features" in devcontainer


class TestDockerInDockerFromTemplate:
    def test_cruft_context_enables_docker_in_docker(self):
        context = json.loads(CRUFT.read_text(encoding="utf-8"))["context"]
        assert context["cookiecutter"]["docker_in_docker"] == "y", (
            "Docker-in-Docker must come from the PyFoundry template "
            "(docker_in_docker=y in .cruft.json), not from a hand-made addition"
        )

    def test_single_docker_in_docker_feature(self, devcontainer):
        assert len(dind_entries(devcontainer["features"])) == 1

    def test_docker_in_docker_feature_major_at_least_4(self, devcontainer):
        [(key, major)] = dind_entries(devcontainer["features"])
        assert major >= MIN_DIND_VERSION[0], (
            f"{key}: majors below 4 select iptables at build time; "
            "dockerd then fails on kernels without ip_tables (tag :2 is frozen "
            "at 2.17.0)"
        )

    def test_iptables_switch_at_runtime_not_disabled(self, devcontainer):
        [(key, _)] = dind_entries(devcontainer["features"])
        options = devcontainer["features"][key]
        assert options.get("iptablesSwitchAtRuntime", True) is True

    def test_host_docker_socket_not_mounted(self, devcontainer):
        mounts = devcontainer.get("mounts", [])
        offending = [m for m in mounts if "/var/run/docker.sock" in m]
        assert offending == [], (
            "docker-in-docker runs its own daemon and never reads the host socket; "
            f"mounting it only grants root access to the host Docker: {offending}"
        )


class TestDevcontainerLock:
    def test_lock_matches_devcontainer_features(self, devcontainer, lock):
        assert set(lock["features"]) == set(devcontainer["features"]), (
            "devcontainer-lock.json is out of date: regenerate it with "
            "`npx @devcontainers/cli upgrade --workspace-folder .`"
        )

    def test_lock_docker_in_docker_version_selects_iptables_at_runtime(
        self, devcontainer, lock
    ):
        [(key, major)] = dind_entries(devcontainer["features"])
        entry = lock["features"].get(key)
        assert entry is not None, f"{key} missing from devcontainer-lock.json"
        version = parse_version(entry["version"])
        assert version >= MIN_DIND_VERSION
        assert version[0] == major
        assert entry["resolved"].endswith(entry["integrity"])
