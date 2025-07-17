import logging
import os

import docker
from docker.errors import DockerException, ImageNotFound

BROWSER_IMAGE_ENV_VAR = "MAGENTIC_UI_BROWSER_IMAGE"
PYTHON_IMAGE_ENV_VAR = "MAGENTIC_UI_PYTHON_IMAGE"

DOCKER_REGISTRY = "ghcr.io/microsoft"
BROWSER_IMAGE = os.getenv(
    BROWSER_IMAGE_ENV_VAR, f"{DOCKER_REGISTRY}/magentic-ui-browser:0.0.1"
)
PYTHON_IMAGE = os.getenv(
    PYTHON_IMAGE_ENV_VAR, f"{DOCKER_REGISTRY}/magentic-ui-python-env:0.0.1"
)


def check_docker_running() -> bool:
    try:
        client = docker.from_env()
        client.ping()  # type: ignore
        return True
    except (DockerException, ConnectionError):
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
