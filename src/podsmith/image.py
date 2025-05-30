import subprocess
from typing import Protocol

import docker


class ImageLoader(Protocol):
    def load_image(self, image: str) -> None: ...


class KindImageLoader:
    def __init__(self, cluster: str) -> None:
        self.cluster = cluster.removeprefix("kind-")
        ctx = docker.ContextAPI.get_current_context()
        self.docker_client = docker.DockerClient(base_url=ctx.Host)

    def load_image(self, image: str) -> None:
        try:
            self.docker_client.images.get(image)
            subprocess.run(
                ["kind", "load", "docker-image", image, "--name", self.cluster],
                check=True,
            )
        except docker.errors.ImageNotFound:
            pass
