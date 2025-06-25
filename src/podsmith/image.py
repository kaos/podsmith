# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

import os
import subprocess
from typing import Protocol

import docker


class ImageLoader(Protocol):
    def load_image(self, image: str) -> None: ...

    @staticmethod
    def default_preloader(cluster_name: str) -> str | None:
        if cluster_name.startswith("kind-"):
            return "kind"
        return None

    @classmethod
    def create(cls, cluster_name: str) -> ImageLoader:
        match os.getenv("PODSMITH_PRELOAD_IMAGES", cls.default_preloader(cluster_name)):
            case "kind":
                return KindImageLoader(cluster_name)
            case "" | None:
                return None
            case value:
                raise ValueError(f"PODSMITH_PRELOAD_IMAGES={value!r} is not supported.")


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
