# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from enum import Enum

from kubernetes.client import ApiClient, CoreV1Api, V1Pod, V1Service, V1ServicePort, V1ServiceSpec
from typing_extensions import Self

from .manifest import Manifest

APP_LABEL = "app.kubernetes.io/name"


class Service(Manifest[V1Service]):
    class PortType(str, Enum):
        ExternalName = "ExternalName"
        ClusterIP = "ClusterIP"
        NodePort = "NodePort"
        LoadBalancer = "LoadBalancer"

    def __init__(
        self,
        pod: Manifest[V1Pod],
        *,
        name: str | None = None,
        client: ApiClient = None,
        port_type: PortType = PortType.ClusterIP,
        **metadata,
    ):
        super().__init__(
            name=name or f"{pod.name}-service", namespace=pod.namespace, client=client, **metadata
        )
        if not isinstance(port_type, Service.PortType):
            port_type = Service.PortType(port_type)
        self.port_type = port_type
        self.pod = pod

    def _new_manifest(self) -> V1Service:
        assert APP_LABEL in self.pod.metadata.labels
        return V1Service(
            metadata=self.metadata,
            spec=V1ServiceSpec(
                type=self.port_type.value,
                selector={APP_LABEL: self.pod.metadata.labels[APP_LABEL]},
                ports=[],
            ),
        )

    def _get_manifest(self) -> V1Service:
        return CoreV1Api(self.client).read_namespaced_service(self.name, self.namespace)

    def _create(self) -> V1Service:
        return CoreV1Api(self.client).create_namespaced_service(self.namespace, self.manifest)

    def _delete(self) -> None:
        CoreV1Api(self.client).delete_namespaced_service(self.name, self.namespace)

    def add_port(self, port: int, **kwargs) -> Self:
        assert not self.live
        self.manifest.spec.ports.append(V1ServicePort(port=port, **kwargs))
        return self
