"""
Tests for docker-compose.yml configuration.

This test suite verifies that services are correctly configured,
particularly focusing on healthcheck endpoints.
"""

import yaml


class TestDockerComposeConfiguration:
    """Tests for docker-compose.yml service configurations."""

    def test_docker_compose_file_exists(self):
        """Verify that docker-compose.yml exists."""
        import os

        assert os.path.exists("docker-compose.yml"), "docker-compose.yml should exist"

    def test_backend_service_exists(self):
        """Verify that backend service is defined in docker-compose.yml."""
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)

        assert "services" in config, "docker-compose.yml should have services"
        assert "backend" in config["services"], "backend service should be defined"

    def test_backend_healthcheck_exists(self):
        """Verify that backend service has a healthcheck configured."""
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)

        backend = config["services"]["backend"]
        assert "healthcheck" in backend, "backend service should have healthcheck"
        assert "test" in backend["healthcheck"], "healthcheck should have test command"

    def test_backend_healthcheck_uses_health_endpoint(self):
        """Verify that backend healthcheck uses /health endpoint instead of /."""
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)

        backend = config["services"]["backend"]
        healthcheck_test = backend["healthcheck"]["test"]

        # The healthcheck test should be a list containing CMD, curl, -f, and the URL
        assert isinstance(healthcheck_test, list), "healthcheck test should be a list"
        assert len(healthcheck_test) >= 3, (
            "healthcheck test should have at least 3 items"
        )

        # Join the command to check the full URL
        command_str = " ".join(healthcheck_test)
        assert "/health" in command_str, (
            "backend healthcheck should use /health endpoint"
        )
        assert "http://localhost:8000/health" in command_str, (
            "backend healthcheck should use http://localhost:8000/health"
        )

    def test_backend_healthcheck_timing_parameters(self):
        """Verify that backend healthcheck has appropriate timing parameters."""
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)

        backend = config["services"]["backend"]
        healthcheck = backend["healthcheck"]

        # Check that timing parameters are present
        assert "interval" in healthcheck, "healthcheck should have interval"
        assert "timeout" in healthcheck, "healthcheck should have timeout"
        assert "retries" in healthcheck, "healthcheck should have retries"
        assert "start_period" in healthcheck, "healthcheck should have start_period"

        # Check values are reasonable (as strings with time units)
        assert healthcheck["interval"] == "30s", "interval should be 30s"
        assert healthcheck["timeout"] == "10s", "timeout should be 10s"
        assert healthcheck["retries"] == 3, "retries should be 3"
        assert healthcheck["start_period"] == "30s", "start_period should be 30s"

    def test_frontend_healthcheck_uses_health_endpoint(self):
        """Verify that frontend also uses /health endpoint (best practice check)."""
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)

        # Check if frontend service exists
        if "frontend" not in config["services"]:
            return  # Skip if frontend doesn't exist

        frontend = config["services"]["frontend"]
        if "healthcheck" not in frontend:
            return  # Skip if no healthcheck

        healthcheck_test = frontend["healthcheck"]["test"]
        command_str = " ".join(healthcheck_test)

        # Frontend should use /health endpoint (not check for root)
        assert "/health" in command_str, (
            "frontend healthcheck should use /health endpoint"
        )


class TestBabelioCacheConfiguration:
    """Tests for Babelio cache externalization in backend service."""

    def _get_backend(self):
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)
        return config["services"]["backend"]

    def _get_env_list(self, backend):
        """Return backend environment as a list of strings."""
        env = backend.get("environment", [])
        if isinstance(env, dict):
            return [f"{k}={v}" for k, v in env.items()]
        return env

    def test_backend_has_babelio_cache_dir_env(self):
        """Verify that backend defines BABELIO_CACHE_DIR environment variable."""
        backend = self._get_backend()
        env_list = self._get_env_list(backend)
        env_keys = [e.split("=")[0] for e in env_list]
        assert "BABELIO_CACHE_DIR" in env_keys, (
            "backend should define BABELIO_CACHE_DIR environment variable"
        )

    def test_backend_has_babelio_fair_sec_env(self):
        """Verify that backend defines BABELIO_FAIR_SEC environment variable."""
        backend = self._get_backend()
        env_list = self._get_env_list(backend)
        env_keys = [e.split("=")[0] for e in env_list]
        assert "BABELIO_FAIR_SEC" in env_keys, (
            "backend should define BABELIO_FAIR_SEC environment variable"
        )

    def test_backend_has_babelio_cache_day_env(self):
        """Verify that backend defines BABELIO_CACHE_DAY environment variable."""
        backend = self._get_backend()
        env_list = self._get_env_list(backend)
        env_keys = [e.split("=")[0] for e in env_list]
        assert "BABELIO_CACHE_DAY" in env_keys, (
            "backend should define BABELIO_CACHE_DAY environment variable"
        )

    def test_babelio_cache_dir_fixed_value(self):
        """Verify that BABELIO_CACHE_DIR is set to /cache/babelio (fixed path)."""
        backend = self._get_backend()
        env_list = self._get_env_list(backend)
        cache_dir_entry = next(
            (e for e in env_list if e.startswith("BABELIO_CACHE_DIR=")), None
        )
        assert cache_dir_entry is not None, "BABELIO_CACHE_DIR should be defined"
        assert cache_dir_entry == "BABELIO_CACHE_DIR=/cache/babelio", (
            "BABELIO_CACHE_DIR should be set to /cache/babelio"
        )

    def test_backend_has_babelio_cache_volume(self):
        """Verify that backend mounts an external volume for Babelio cache."""
        backend = self._get_backend()
        volumes = backend.get("volumes", [])
        has_babelio_volume = any("/cache/babelio" in str(v) for v in volumes)
        assert has_babelio_volume, "backend should mount a volume for /cache/babelio"

    def test_babelio_cache_volume_uses_env_variable(self):
        """Verify that Babelio cache volume path is configurable via BABELIO_CACHE_PATH."""
        backend = self._get_backend()
        volumes = backend.get("volumes", [])
        babelio_volume = next((v for v in volumes if "/cache/babelio" in str(v)), None)
        assert babelio_volume is not None, "Babelio cache volume should exist"
        assert "BABELIO_CACHE_PATH" in str(babelio_volume), (
            "Babelio cache volume should use BABELIO_CACHE_PATH variable"
        )


class TestLmelpExportGhTokenConfiguration:
    """Tests for GH_TOKEN provisioning on the lmelp-export service (issue #56)."""

    def _get_lmelp_export(self):
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)
        return config["services"]["lmelp-export"]

    def _get_env_list(self, service):
        """Return service environment as a list of strings."""
        env = service.get("environment", [])
        if isinstance(env, dict):
            return [f"{k}={v}" for k, v in env.items()]
        return env

    def test_lmelp_export_has_gh_token_env(self):
        """Verify that lmelp-export defines a GH_TOKEN environment variable."""
        service = self._get_lmelp_export()
        env_list = self._get_env_list(service)
        env_keys = [e.split("=")[0] for e in env_list]
        assert "GH_TOKEN" in env_keys, (
            "lmelp-export should define GH_TOKEN environment variable "
            "(required by 'export-and-publish-release' for 'gh release upload')"
        )

    def test_gh_token_uses_env_variable(self):
        """Verify that GH_TOKEN is passed through from the host .env, not hardcoded."""
        service = self._get_lmelp_export()
        env_list = self._get_env_list(service)
        gh_token_entry = next((e for e in env_list if e.startswith("GH_TOKEN=")), None)
        assert gh_token_entry is not None, "GH_TOKEN should be defined"
        assert "${GH_TOKEN" in gh_token_entry, (
            "GH_TOKEN should be passed through via the GH_TOKEN env variable, "
            "not hardcoded"
        )


class TestLmelpExportLogVolumeConfiguration:
    """Tests for lmelp-export log persistence (issue #56).

    The anacron job embedded in the ghcr.io/castorfou/lmelp-mobile-export
    image writes to /var/log/publish-data-release.log *inside* the
    container. Without a bind-mounted volume on /var/log, that log is lost
    whenever the container is recreated and never visible on the host.
    """

    def _get_lmelp_export(self):
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)
        return config["services"]["lmelp-export"]

    def test_lmelp_export_has_log_volume(self):
        """Verify that lmelp-export mounts a host volume on /var/log."""
        service = self._get_lmelp_export()
        volumes = service.get("volumes", [])
        has_log_volume = any(":/var/log" in str(v) for v in volumes)
        assert has_log_volume, (
            "lmelp-export should mount a volume on /var/log so the anacron "
            "job log (publish-data-release.log) survives container recreation"
        )

    def test_log_volume_uses_env_variable(self):
        """Verify that the log volume path is configurable via an env variable."""
        service = self._get_lmelp_export()
        volumes = service.get("volumes", [])
        log_volume = next((v for v in volumes if ":/var/log" in str(v)), None)
        assert log_volume is not None, "Log volume should exist"
        assert "LMELP_EXPORT_LOG_PATH" in str(log_volume), (
            "Log volume should be configurable via LMELP_EXPORT_LOG_PATH"
        )

    def test_log_volume_default_nested_under_lmelp_log_path(self):
        """Verify the default log host path is a subdirectory of lmelp's LOG_PATH.

        Unlike MONGO_LOG_PATH (issue #51), nesting here is safe: lmelp-export
        runs its anacron job as root (no gosu/privilege drop in
        Dockerfile.export), so lmelp's periodic chown -R of LOG_PATH cannot
        break its writes -- root ignores file ownership.
        """
        service = self._get_lmelp_export()
        volumes = service.get("volumes", [])
        log_volume = next((v for v in volumes if ":/var/log" in str(v)), None)
        assert log_volume is not None, "Log volume should exist"
        assert "./data/logs/lmelp-export" in str(log_volume), (
            "lmelp-export log path should default to a subdirectory of "
            "LOG_PATH (./data/logs/lmelp-export)"
        )


class TestPgxConfiguration:
    """Tests for PGX transcription environment variables on lmelp (issue #58).

    The lmelp image (castorfou/lmelp) drives automated transcription via a
    dedicated GPU station (PGX) reachable over SSH. Its entrypoint generates
    and persists a dedicated SSH key under PGX_SSH_KEY_PATH (on the /app/keys
    volume) at first startup -- see docs/user/transcription-pgx.md in the
    lmelp repo.
    """

    def _get_lmelp(self):
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)
        return config["services"]["lmelp"]

    def _get_env_list(self, service):
        """Return service environment as a list of strings."""
        env = service.get("environment", [])
        if isinstance(env, dict):
            return [f"{k}={v}" for k, v in env.items()]
        return env

    def test_lmelp_has_pgx_host_env(self):
        """Verify that lmelp defines a PGX_HOST environment variable."""
        service = self._get_lmelp()
        env_list = self._get_env_list(service)
        env_keys = [e.split("=")[0] for e in env_list]
        assert "PGX_HOST" in env_keys, (
            "lmelp should define PGX_HOST environment variable"
        )

    def test_lmelp_has_pgx_user_env(self):
        """Verify that lmelp defines a PGX_USER environment variable."""
        service = self._get_lmelp()
        env_list = self._get_env_list(service)
        env_keys = [e.split("=")[0] for e in env_list]
        assert "PGX_USER" in env_keys, (
            "lmelp should define PGX_USER environment variable"
        )

    def test_lmelp_has_pgx_ssh_key_path_env(self):
        """Verify PGX_SSH_KEY_PATH is fixed to the persisted key location."""
        service = self._get_lmelp()
        env_list = self._get_env_list(service)
        key_path_entry = next(
            (e for e in env_list if e.startswith("PGX_SSH_KEY_PATH=")), None
        )
        assert key_path_entry is not None, "PGX_SSH_KEY_PATH should be defined"
        assert (
            key_path_entry
            == "PGX_SSH_KEY_PATH=/app/keys/pgx_lmelp_ed25519"  # pragma: allowlist secret
        ), "PGX_SSH_KEY_PATH should be fixed to /app/keys/pgx_lmelp_ed25519"

    def test_lmelp_has_pgx_remote_audio_root_env(self):
        """Verify that lmelp defines a PGX_REMOTE_AUDIO_ROOT environment variable."""
        service = self._get_lmelp()
        env_list = self._get_env_list(service)
        env_keys = [e.split("=")[0] for e in env_list]
        assert "PGX_REMOTE_AUDIO_ROOT" in env_keys, (
            "lmelp should define PGX_REMOTE_AUDIO_ROOT environment variable"
        )

    def test_lmelp_has_pgx_remote_transcription_root_env(self):
        """Verify that lmelp defines a PGX_REMOTE_TRANSCRIPTION_ROOT env variable."""
        service = self._get_lmelp()
        env_list = self._get_env_list(service)
        env_keys = [e.split("=")[0] for e in env_list]
        assert "PGX_REMOTE_TRANSCRIPTION_ROOT" in env_keys, (
            "lmelp should define PGX_REMOTE_TRANSCRIPTION_ROOT environment variable"
        )

    def test_lmelp_has_pgx_keys_volume(self):
        """Verify that lmelp mounts a persistent volume on /app/keys."""
        service = self._get_lmelp()
        volumes = service.get("volumes", [])
        has_pgx_keys_volume = any(":/app/keys" in str(v) for v in volumes)
        assert has_pgx_keys_volume, (
            "lmelp should mount a volume for /app/keys so the dedicated PGX "
            "SSH key survives container recreation"
        )

    def test_pgx_keys_volume_uses_env_variable(self):
        """Verify that the PGX keys volume path is configurable via PGX_KEYS_PATH."""
        service = self._get_lmelp()
        volumes = service.get("volumes", [])
        pgx_keys_volume = next((v for v in volumes if ":/app/keys" in str(v)), None)
        assert pgx_keys_volume is not None, "PGX keys volume should exist"
        assert "PGX_KEYS_PATH" in str(pgx_keys_volume), (
            "PGX keys volume should be configurable via PGX_KEYS_PATH"
        )


class TestPgxKeysWatchdogConfiguration:
    """Tests for the PGX SSH key permissions watchdog (issue #61).

    The lmelp image generates the dedicated PGX SSH private key with correct
    permissions (600, via ssh-keygen) at first startup, but something external
    to both lmelp and docker-lmelp (most likely the NAS's own ACL
    synchronization) has been observed resetting it to 755 afterwards. Since
    docker-lmelp does not build the lmelp image (pulled from ghcr.io), it
    cannot inject a fix into its entrypoint -- instead a lightweight sidecar
    service periodically re-applies safe permissions, mirroring the
    self-healing ownership watchdog already used for MongoDB (issue #51).
    """

    def _get_watchdog(self):
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)
        return config["services"]["pgx-keys-watchdog"]

    def test_pgx_keys_watchdog_service_exists(self):
        """Verify that the pgx-keys-watchdog service is defined."""
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)
        assert "pgx-keys-watchdog" in config["services"], (
            "pgx-keys-watchdog service should be defined"
        )

    def test_pgx_keys_watchdog_mounts_pgx_keys_volume(self):
        """Verify that the watchdog mounts the same PGX_KEYS_PATH volume."""
        service = self._get_watchdog()
        volumes = service.get("volumes", [])
        assert volumes, "pgx-keys-watchdog should mount a volume"
        assert any("PGX_KEYS_PATH" in str(v) for v in volumes), (
            "pgx-keys-watchdog should mount the volume configured via PGX_KEYS_PATH"
        )

    def test_pgx_keys_watchdog_command_chmods_private_key_to_600(self):
        """Verify that the watchdog command restores 600 on the private key."""
        service = self._get_watchdog()
        command = service.get("command", "")
        assert "chmod 600" in command, (
            "pgx-keys-watchdog command should chmod the private key to 600"
        )
        assert "pgx_lmelp_ed25519" in command, (
            "pgx-keys-watchdog command should target the PGX private key file"
        )

    def test_pgx_keys_watchdog_has_restart_policy(self):
        """Verify that the watchdog restarts automatically."""
        service = self._get_watchdog()
        assert service.get("restart") == "unless-stopped", (
            "pgx-keys-watchdog should have restart: unless-stopped"
        )
