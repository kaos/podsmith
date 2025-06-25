# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from kubernetes.client import CoreV1Api, V1ConfigMap
from typing_extensions import Self

from .manifest import Manifest


class ConfigMap(Manifest[V1ConfigMap]):
    def _create(self) -> V1ConfigMap:
        return CoreV1Api(self.client).create_namespaced_config_map(self.namespace, self.manifest)

    def _delete(self) -> None:
        CoreV1Api(self.client).delete_namespaced_config_map(self.name, self.namespace)

    def _new_manifest(self) -> V1ConfigMap:
        return V1ConfigMap(metadata=self.metadata)

    def _get_manifest(self) -> V1ConfigMap:
        return CoreV1Api(self.client).read_namespaced_config_map(self.name, self.namespace)

    def with_data(self, data: dict[str, str]) -> Self:
        assert not self.live
        self.manifest.data = data
        return self

    def with_data_values(self, **values) -> Self:
        assert not self.live
        self.manifest.data.update(values)
        return self

    def with_binary_data(self, binary_data: dict[str, str]) -> Self:
        assert not self.live
        self.manifest.binary_data = binary_data
        return self

    def with_binary_data_values(self, **values) -> Self:
        assert not self.live
        self.manifest.binary_data.update(values)
        return self

    def with_immutable(self, immutable: bool = True) -> Self:
        assert not self.live
        self.manifest.immutable = immutable
        return self
