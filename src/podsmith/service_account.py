# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from kubernetes.client import CoreV1Api, V1ServiceAccount

from .manifest import Manifest


class ServiceAccount(Manifest[V1ServiceAccount]):
    def _create(self) -> V1ServiceAccount:
        return CoreV1Api(self.client).create_namespaced_service_account(
            self.namespace, self.manifest
        )

    def _delete(self) -> None:
        CoreV1Api(self.client).delete_namespaced_service_account(self.name, self.namespace)

    def _new_manifest(self) -> V1ServiceAccount:
        return V1ServiceAccount(metadata=self.metadata)

    def _get_manifest(self) -> V1ServiceAccount:
        return CoreV1Api(self.client).read_namespaced_service_account(self.name, self.namespace)
