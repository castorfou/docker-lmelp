"""Tests du package docker_lmelp."""

import docker_lmelp as package


def test_package_importable() -> None:
    """Le package s'importe depuis src/."""
    assert package.__name__ == "docker_lmelp"
