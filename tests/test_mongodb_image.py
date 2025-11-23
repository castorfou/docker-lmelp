"""
Tests for MongoDB custom image configuration.

This test suite verifies that the lmelp-mongo image is correctly configured
with both log rotation and backup using anacron.
"""

import subprocess

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
