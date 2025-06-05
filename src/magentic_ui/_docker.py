import docker
import os
import sys
from docker.errors import DockerException, ImageNotFound
import logging

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
VNC_BROWSER_IMAGE = "magentic-ui-vnc-browser"
PYTHON_IMAGE = "magentic-ui-python-env"

VNC_BROWSER_BUILD_CONTEXT = "magentic-ui-browser-docker"
PYTHON_BUILD_CONTEXT = "magentic-ui-python-env"


def check_docker_running() -> bool:
    try:
        client = docker.from_env()
        client.ping()  # type: ignore
        return True
    except (DockerException, ConnectionError):
        return False


def build_image(
    image_name: str, build_context: str, client: docker.DockerClient
) -> None:
    for segment in client.api.build(
        path=build_context,
        dockerfile="Dockerfile",
        rm=True,
        tag=image_name,
        decode=True,
    ):
        if "stream" in segment:
            lines = segment["stream"].splitlines()
            for line in lines:
                if line:
                    sys.stdout.write(line + "\n")
                    sys.stdout.flush()


def check_docker_image(image_name: str, client: docker.DockerClient) -> bool:
    try:
        client.images.get(image_name)
        return True
    except ImageNotFound:
        return False


def build_browser_image(client: docker.DockerClient | None = None) -> None:
    if client is None:
        client = docker.from_env()
    client = docker.from_env()
    build_image(
        VNC_BROWSER_IMAGE + ":latest",
        os.path.join(_PACKAGE_DIR, "docker", VNC_BROWSER_BUILD_CONTEXT),
        client,
    )


def build_python_image(client: docker.DockerClient | None = None) -> None:
    if client is None:
        client = docker.from_env()
    client = docker.from_env()
    build_image(
        PYTHON_IMAGE + ":latest",
        os.path.join(_PACKAGE_DIR, "docker", PYTHON_BUILD_CONTEXT),
        client,
    )


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
    if client is None:
        client = docker.from_env()
    client = docker.from_env()
    return check_docker_image(VNC_BROWSER_IMAGE, client)


def check_python_image(client: docker.DockerClient | None = None) -> bool:
    if not check_docker_access():
        return False
    if client is None:
        client = docker.from_env()
    client = docker.from_env()
    return check_docker_image(PYTHON_IMAGE, client)
