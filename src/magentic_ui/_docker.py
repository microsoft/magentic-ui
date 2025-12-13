import logging
import os
from pathlib import Path

import docker
from docker.errors import DockerException, ImageNotFound

BROWSER_IMAGE_ENV_VAR = "MAGENTIC_UI_BROWSER_IMAGE"
PYTHON_IMAGE_ENV_VAR = "MAGENTIC_UI_PYTHON_IMAGE"

DOCKER_REGISTRY = "ghcr.io/microsoft"
BROWSER_IMAGE = os.getenv(
    BROWSER_IMAGE_ENV_VAR, f"{DOCKER_REGISTRY}/magentic-ui-browser:0.0.2"
)
PYTHON_IMAGE = os.getenv(
    PYTHON_IMAGE_ENV_VAR, f"{DOCKER_REGISTRY}/magentic-ui-python-env:0.0.1"
)


def _get_docker_socket_paths() -> list[str]:
    """Get list of common Docker socket paths to try."""
    home = Path.home()
    return [
        # Docker Desktop on macOS (newer versions)
        f"unix://{home}/.docker/run/docker.sock",
        # Docker Desktop on macOS (alternative location)
        "unix:///var/run/docker.sock",
        # Colima on macOS
        f"unix://{home}/.colima/default/docker.sock",
        # Podman on macOS
        f"unix://{home}/.local/share/containers/podman/machine/podman.sock",
        # Rancher Desktop
        f"unix://{home}/.rd/docker.sock",
    ]


def _try_docker_connection(docker_host: str | None = None) -> docker.DockerClient | None:
    """Try to connect to Docker with given host, return client if successful."""
    try:
        if docker_host:
            client = docker.DockerClient(base_url=docker_host)
        else:
            client = docker.from_env()
        client.ping()  # type: ignore
        return client
    except (DockerException, ConnectionError):
        return None


def check_docker_running() -> bool:
    """Check if Docker is running, trying multiple socket paths if needed."""
    # First try the default (respects DOCKER_HOST env var)
    if _try_docker_connection() is not None:
        return True

    # If default fails and DOCKER_HOST is not set, try common socket paths
    if not os.environ.get("DOCKER_HOST"):
        for socket_path in _get_docker_socket_paths():
            client = _try_docker_connection(socket_path)
            if client is not None:
                # Set DOCKER_HOST so subsequent docker.from_env() calls work
                os.environ["DOCKER_HOST"] = socket_path
                logging.info(f"Docker found at {socket_path}")
                return True

    return False


def check_docker_image(image_name: str, client: docker.DockerClient) -> bool:
    try:
        client.images.get(image_name)
        return True
    except ImageNotFound:
        return False


def split_docker_repository_and_tag(image_name: str):
    if ":" in image_name:
        return image_name.rsplit(":", 1)
    return image_name, "latest"


def pull_browser_image(client: docker.DockerClient | None = None) -> None:
    client = client or docker.from_env()
    repo, tag = split_docker_repository_and_tag(BROWSER_IMAGE)
    client.images.pull(repo, tag)


def pull_python_image(client: docker.DockerClient | None = None) -> None:
    client = client or docker.from_env()
    repo, tag = split_docker_repository_and_tag(PYTHON_IMAGE)
    client.images.pull(repo, tag)


def check_docker_access():
    try:
        client = docker.from_env()
        client.ping()  # type: ignore
        return True
    except DockerException as e:
        logging.error(
            f"Error {e}: Cannot access Docker. Please refer to the TROUBLESHOOTING.md document for possible solutions."
        )
        return False


def check_browser_image(client: docker.DockerClient | None = None) -> bool:
    if not check_docker_access():
        return False
    client = client or docker.from_env()
    return check_docker_image(BROWSER_IMAGE, client)


def check_python_image(client: docker.DockerClient | None = None) -> bool:
    if not check_docker_access():
        return False
    client = client or docker.from_env()
    return check_docker_image(PYTHON_IMAGE, client)
