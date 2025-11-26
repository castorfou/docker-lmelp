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
