"""
Tests for MongoDB custom image configuration.

This test suite verifies that the lmelp-mongo image is correctly configured
with both log rotation and backup using anacron.
"""

import subprocess
import time

import pytest


class TestMongoDBImageBuild:
    """Tests for MongoDB Docker image build."""

    def test_dockerfile_exists(self):
        """Verify that mongodb.Dockerfile exists."""
        import os

        assert os.path.exists("mongodb.Dockerfile"), "mongodb.Dockerfile should exist"

    def test_image_can_be_built(self):
        """Verify that the MongoDB image can be built successfully."""
        result = subprocess.run(
            [
                "docker",
                "build",
                "-f",
                "mongodb.Dockerfile",
                "-t",
                "lmelp-mongo:test",
                ".",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, f"Image build failed: {result.stderr}"


class TestMongoDBEntrypointOwnership:
    """Tests for issue #48: anacron-spawned jobs must run as `mongodb`, not
    root, so backup/log-rotation files created on bind-mounted host volumes
    are not owned by root."""

    def test_entrypoint_runs_anacron_loop_as_mongodb_user(self):
        """The anacron loop in the custom entrypoint must invoke anacron via
        `gosu mongodb`, not as root, otherwise every job it spawns
        (backup_mongodb.sh, rotate_mongodb_logs.sh) writes root-owned files
        on bind-mounted volumes such as /backups and /var/log/mongodb."""
        with open("mongodb.Dockerfile") as f:
            content = f.read()

        anacron_loop_lines = [
            line
            for line in content.splitlines()
            if "while true" in line and "anacron -d" in line
        ]
        assert anacron_loop_lines, (
            "Could not find the anacron background loop line in mongodb.Dockerfile"
        )
        assert "gosu mongodb anacron -d" in anacron_loop_lines[0], (
            "The anacron loop must run 'gosu mongodb anacron -d' instead of "
            "'anacron -d' as root, otherwise backup/log-rotation jobs it "
            "spawns create root-owned files on bind-mounted volumes"
        )

    def test_entrypoint_anacron_loop_interval_is_configurable(self):
        """The anacron loop's sleep interval must be configurable via
        ANACRON_LOOP_INTERVAL (default 3600)."""
        with open("mongodb.Dockerfile") as f:
            content = f.read()

        anacron_loop_lines = [
            line
            for line in content.splitlines()
            if "while true" in line and "anacron -d" in line
        ]
        assert anacron_loop_lines
        assert 'sleep "${ANACRON_LOOP_INTERVAL:-3600}"' in anacron_loop_lines[0], (
            "The anacron loop sleep interval must be configurable via "
            "ANACRON_LOOP_INTERVAL (default 3600)"
        )

    def test_entrypoint_has_ownership_watchdog_loop(self):
        """A dedicated loop, independent of the anacron loop, must
        periodically re-chown /backups and /var/log/mongodb to mongodb.
        Issue #51: a sibling service (lmelp) sharing an overlapping
        bind-mounted parent directory can recursively re-own
        /var/log/mongodb after the container started (PUID/PGID migration
        chown, castorfou/lmelp#105) — this watchdog must self-heal within
        a short, configurable interval instead of staying broken. It must
        be kept separate from the anacron loop: `anacron -d` blocks for
        each job's configured anacrontab delay (several minutes) before
        running it, which would make re-chowning far too infrequent if
        interleaved with that call."""
        with open("mongodb.Dockerfile") as f:
            content = f.read()

        watchdog_loop_lines = [
            line
            for line in content.splitlines()
            if "while true" in line
            and "chown -R mongodb:mongodb /backups /var/log/mongodb" in line
            and "anacron -d" not in line
        ]
        assert watchdog_loop_lines, (
            "Could not find a dedicated ownership-watchdog loop (re-chowning "
            "/backups and /var/log/mongodb) separate from the anacron loop "
            "in mongodb.Dockerfile"
        )
        assert 'sleep "${CHOWN_WATCHDOG_INTERVAL:-300}"' in watchdog_loop_lines[0], (
            "The ownership watchdog's sleep interval must be configurable "
            "via CHOWN_WATCHDOG_INTERVAL (default 300) so tests can exercise "
            "the self-healing behaviour quickly"
        )


class TestDockerComposeLogPathSeparation:
    """Issue #51: MONGO_LOG_PATH must not be nested under LOG_PATH.

    lmelp's entrypoint recursively chowns its own LOG_PATH bind mount at
    every startup (PUID/PGID migration, castorfou/lmelp#105/PR#106). If
    MONGO_LOG_PATH lives under LOG_PATH's tree, that chown silently
    re-owns mongo's log files to lmelp's PUID/PGID, breaking the anacron
    backup/log-rotation jobs which then can't write there as `mongodb`."""

    def test_mongo_log_path_default_is_not_nested_under_lmelp_log_path(self):
        import re

        with open("docker-compose.yml") as f:
            content = f.read()

        log_path_match = re.search(r"\$\{LOG_PATH:-([^}]+)\}", content)
        mongo_log_path_match = re.search(r"\$\{MONGO_LOG_PATH:-([^}]+)\}", content)
        assert log_path_match, "Could not find LOG_PATH default in docker-compose.yml"
        assert mongo_log_path_match, (
            "Could not find MONGO_LOG_PATH default in docker-compose.yml"
        )

        log_path = log_path_match.group(1).rstrip("/")
        mongo_log_path = mongo_log_path_match.group(1).rstrip("/")

        assert not mongo_log_path.startswith(log_path + "/"), (
            f"MONGO_LOG_PATH default ({mongo_log_path!r}) must not be nested "
            f"under LOG_PATH default ({log_path!r}) — lmelp's entrypoint "
            "recursively chowns its own LOG_PATH mount and would silently "
            "re-own mongo's log files (issue #51)"
        )


class TestMongoDBScriptSelfDefense:
    """Tests that backup_mongodb.sh and rotate_mongodb_logs.sh always run as
    the mongodb user, even when invoked directly as root (e.g. a manual
    `docker exec` without --user) — not just when triggered via anacron."""

    @pytest.mark.parametrize(
        "script_path",
        ["scripts/backup_mongodb.sh", "scripts/rotate_mongodb_logs.sh"],
    )
    def test_script_re_execs_as_mongodb_when_run_as_root(self, script_path):
        """Each script must detect a root UID and re-exec itself via
        `gosu mongodb`, before doing anything else, so files it creates on
        bind-mounted volumes are never owned by root regardless of how the
        script was invoked."""
        with open(script_path) as f:
            content = f.read()

        assert "id -u" in content and 'gosu mongodb "$0"' in content, (
            f'{script_path} must re-exec itself via \'gosu mongodb "$0" "$@"\' '
            "when running as root (uid 0), so manual invocations (e.g. "
            "`docker exec` without --user) don't create root-owned files"
        )

        # The guard must appear before the script does any real work
        # (before the MONGO_HOST configuration block), not buried after
        # other logic has already run as root.
        guard_index = content.index('gosu mongodb "$0"')
        config_index = content.index("MONGO_HOST=")
        assert guard_index < config_index, (
            f"{script_path}: the root re-exec guard should run near the top "
            "of the script, before any other logic executes as root"
        )

    @pytest.mark.parametrize(
        "script_path",
        ["scripts/backup_mongodb.sh", "scripts/rotate_mongodb_logs.sh"],
    )
    def test_script_exports_home_for_current_user(self, script_path):
        """Issue #54: gosu does not reset $HOME like `su -` would, so after
        the root re-exec guard, $HOME still points at /root (inherited from
        the original root process) even though the script now runs as
        mongodb (UID 999). Tools invoked afterwards that need a writable
        HOME for their own local config/cache (e.g. mongosh in
        rotate_mongodb_logs.sh, which tries to create
        /root/.mongodb/mongosh) fail with an EACCES permission warning on
        every run unless HOME is explicitly corrected."""
        with open(script_path) as f:
            content = f.read()

        assert 'export HOME="$(getent passwd "$(id -u)" | cut -d: -f6)"' in content, (
            f"{script_path} must export HOME to the current user's real "
            "home directory after the root re-exec guard, so tools like "
            "mongosh don't try to write their config/cache under /root"
        )


class TestMongoDBImageContent:
    """Tests for MongoDB image content and configuration."""

    @pytest.fixture(scope="class", autouse=True)
    def build_image(self):
        """Build the image once for all tests in this class."""
        subprocess.run(
            [
                "docker",
                "build",
                "-f",
                "mongodb.Dockerfile",
                "-t",
                "lmelp-mongo:test",
                ".",
            ],
            check=True,
            capture_output=True,
            timeout=300,
        )
        yield
        # Cleanup: remove test image after tests
        subprocess.run(
            ["docker", "rmi", "lmelp-mongo:test"],
            capture_output=True,
        )

    def test_anacron_is_installed(self):
        """Verify that anacron is installed in the image."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "lmelp-mongo:test",
                "which",
                "anacron",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "anacron should be installed"
        assert "/usr/sbin/anacron" in result.stdout

    def test_backup_script_exists(self):
        """Verify that backup script exists in the image."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "lmelp-mongo:test",
                "test",
                "-f",
                "/scripts/backup_mongodb.sh",
            ],
            capture_output=True,
        )
        assert result.returncode == 0, "Backup script should exist in /scripts/"

    def test_backup_script_is_executable(self):
        """Verify that backup script is executable."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "lmelp-mongo:test",
                "test",
                "-x",
                "/scripts/backup_mongodb.sh",
            ],
            capture_output=True,
        )
        assert result.returncode == 0, "Backup script should be executable"

    def test_rotate_script_exists(self):
        """Verify that log rotation script exists in the image."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "lmelp-mongo:test",
                "test",
                "-f",
                "/scripts/rotate_mongodb_logs.sh",
            ],
            capture_output=True,
        )
        assert result.returncode == 0, "Rotate script should exist in /scripts/"

    def test_anacrontab_contains_logrotate_job(self):
        """Verify that anacrontab contains the log rotation job."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "lmelp-mongo:test",
                "cat",
                "/etc/anacrontab",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "mongodb-logrotate" in result.stdout, (
            "anacrontab should contain logrotate job"
        )

    def test_anacrontab_contains_backup_job(self):
        """Verify that anacrontab contains the backup job."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "lmelp-mongo:test",
                "cat",
                "/etc/anacrontab",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "mongodb-backup" in result.stdout, "anacrontab should contain backup job"

    def test_anacron_daily_backup_script_exists(self):
        """Verify that the daily backup anacron script exists."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "lmelp-mongo:test",
                "test",
                "-f",
                "/etc/anacron.weekly/mongodb-backup",
            ],
            capture_output=True,
        )
        assert result.returncode == 0, (
            "Backup anacron script should exist in /etc/anacron.weekly/"
        )

    def test_anacron_daily_backup_script_is_executable(self):
        """Verify that the backup anacron script is executable."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "lmelp-mongo:test",
                "test",
                "-x",
                "/etc/anacron.weekly/mongodb-backup",
            ],
            capture_output=True,
        )
        assert result.returncode == 0, "Backup anacron script should be executable"

    def test_entrypoint_chowns_backups_and_logs_to_mongodb(self, tmp_path):
        """Verify that, at container startup, the entrypoint chowns /backups
        and /var/log/mongodb to the mongodb user (UID 999) — recursively, so
        that files already present before startup (owned by some unrelated
        host UID, as observed in production) are also fixed, not just new
        ones created afterwards."""
        backups_dir = tmp_path / "backups"
        stale_backup = backups_dir / "backup_2026-01-01_00-00-00"
        stale_backup.mkdir(parents=True)
        stale_file = stale_backup / "dummy.bson"
        stale_file.write_text("dummy")
        # Owned by whatever UID runs this test (not 999/mongodb), simulating
        # the real-world case of pre-existing files owned by an unrelated
        # host user.

        container_name = "lmelp-mongo-test-ownership"
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        try:
            run_result = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    container_name,
                    "-v",
                    f"{backups_dir}:/backups",
                    "lmelp-mongo:test",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert run_result.returncode == 0, (
                f"Failed to start container: {run_result.stderr}"
            )

            owner_backups = None
            owner_stale_file = None
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                stat_backups = subprocess.run(
                    ["docker", "exec", container_name, "stat", "-c", "%u", "/backups"],
                    capture_output=True,
                    text=True,
                )
                stat_file = subprocess.run(
                    [
                        "docker",
                        "exec",
                        container_name,
                        "stat",
                        "-c",
                        "%u",
                        "/backups/backup_2026-01-01_00-00-00/dummy.bson",
                    ],
                    capture_output=True,
                    text=True,
                )
                if stat_backups.returncode == 0 and stat_file.returncode == 0:
                    owner_backups = stat_backups.stdout.strip()
                    owner_stale_file = stat_file.stdout.strip()
                    if owner_backups == "999" and owner_stale_file == "999":
                        break
                time.sleep(1)

            assert owner_backups == "999", (
                "/backups should be owned by mongodb (UID 999) after entrypoint "
                f"startup, got UID {owner_backups!r}"
            )
            assert owner_stale_file == "999", (
                "Pre-existing files under /backups should be chowned to "
                f"mongodb (UID 999) on startup too, got UID {owner_stale_file!r}"
            )
        finally:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

    def test_backup_script_creates_mongodb_owned_files_when_run_as_root(self, tmp_path):
        """A manual `docker exec` invocation of backup_mongodb.sh as root
        (the container's default exec user, since no USER is set in the
        image) must still produce files owned by mongodb (UID 999), not
        root — the script re-execs itself via gosu when it detects it is
        running as root."""
        backups_dir = tmp_path / "backups"
        backups_dir.mkdir()

        container_name = "lmelp-mongo-test-script-selfdefense"
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        try:
            run_result = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    container_name,
                    "-v",
                    f"{backups_dir}:/backups",
                    "lmelp-mongo:test",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert run_result.returncode == 0, (
                f"Failed to start container: {run_result.stderr}"
            )

            # Wait for mongod to accept connections before triggering a backup
            deadline = time.monotonic() + 30
            mongod_ready = False
            while time.monotonic() < deadline:
                ping = subprocess.run(
                    [
                        "docker",
                        "exec",
                        container_name,
                        "mongosh",
                        "--quiet",
                        "--eval",
                        "db.adminCommand('ping')",
                    ],
                    capture_output=True,
                )
                if ping.returncode == 0:
                    mongod_ready = True
                    break
                time.sleep(1)
            assert mongod_ready, "mongod did not become ready in time"

            # Seed a document so mongodump has something to dump — an empty
            # database produces no output directory at all, which would
            # make the ownership check below meaningless.
            seed = subprocess.run(
                [
                    "docker",
                    "exec",
                    container_name,
                    "mongosh",
                    "--quiet",
                    "masque_et_la_plume",
                    "--eval",
                    "db.testcol.insertOne({x: 1})",
                ],
                capture_output=True,
                text=True,
            )
            assert seed.returncode == 0, f"Failed to seed test data: {seed.stderr}"

            # Explicitly run as root (default docker exec user for this
            # image) to reproduce the manual-invocation scenario.
            backup_result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "--user",
                    "root",
                    "-e",
                    "FORCE_BACKUP=1",
                    container_name,
                    "/scripts/backup_mongodb.sh",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert backup_result.returncode == 0, (
                f"backup_mongodb.sh failed: {backup_result.stderr}"
            )

            owner = subprocess.run(
                [
                    "docker",
                    "exec",
                    container_name,
                    "bash",
                    "-c",
                    "stat -c '%u' /backups/backup_*/",
                ],
                capture_output=True,
                text=True,
            )
            assert owner.returncode == 0, f"stat failed: {owner.stderr}"
            assert owner.stdout.strip() == "999", (
                "Backup files created via a root docker exec should still "
                f"be owned by mongodb (UID 999), got UID {owner.stdout.strip()!r}"
            )
        finally:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

    def test_ownership_watchdog_self_heals_var_log_mongodb(self, tmp_path):
        """Issue #51: if something external re-owns /var/log/mongodb while
        the container is already running (e.g. a sibling service like
        lmelp recursively chowning an overlapping bind-mounted parent
        directory during its own PUID/PGID migration), the dedicated
        ownership watchdog loop must self-heal it back to mongodb within
        a short interval — not require a manual chown or a full container
        recreate to recover. Deliberately independent of the anacron loop
        (ANACRON_LOOP_INTERVAL): `anacron -d` blocks for each job's
        configured anacrontab delay (minutes) before running it, so tying
        the re-chown to that loop would make it far too slow to verify
        (or to actually self-heal in practice)."""
        log_dir = tmp_path / "mongo-logs"
        log_dir.mkdir()

        container_name = "lmelp-mongo-test-selfheal"
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        try:
            run_result = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    container_name,
                    "-e",
                    "CHOWN_WATCHDOG_INTERVAL=2",
                    "-v",
                    f"{log_dir}:/var/log/mongodb",
                    "lmelp-mongo:test",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert run_result.returncode == 0, (
                f"Failed to start container: {run_result.stderr}"
            )

            def stat_owner():
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        container_name,
                        "stat",
                        "-c",
                        "%u",
                        "/var/log/mongodb",
                    ],
                    capture_output=True,
                    text=True,
                )
                return result.stdout.strip() if result.returncode == 0 else None

            # Wait for the initial (pre-loop) chown to apply.
            owner = None
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                owner = stat_owner()
                if owner == "999":
                    break
                time.sleep(1)
            assert owner == "999", (
                f"Initial chown of /var/log/mongodb did not apply, got UID {owner!r}"
            )

            # Simulate the ownership drift observed in production (issue #51).
            corrupt = subprocess.run(
                [
                    "docker",
                    "exec",
                    "--user",
                    "root",
                    container_name,
                    "chown",
                    "-R",
                    "1000:1000",
                    "/var/log/mongodb",
                ],
                capture_output=True,
                text=True,
            )
            assert corrupt.returncode == 0, (
                f"Failed to corrupt ownership: {corrupt.stderr}"
            )
            assert stat_owner() == "1000", "Corruption setup did not apply"

            # The loop (interval=2s) should self-heal within a few iterations.
            healed = False
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if stat_owner() == "999":
                    healed = True
                    break
                time.sleep(1)
            assert healed, (
                "Ownership watchdog did not self-heal /var/log/mongodb "
                "back to mongodb (UID 999) after external corruption"
            )
        finally:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
