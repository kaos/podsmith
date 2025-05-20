# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

import time
from copy import deepcopy

from kubernetes.client import (
    ApiClient,
    CoreV1Api,
    V1Container,
    V1ContainerPort,
    V1EnvVar,
    V1Namespace,
    V1ObjectMeta,
    V1Pod,
    V1PodSpec,
)
from kubernetes.client.exceptions import ApiException
from kubernetes.watch import Watch
from testcontainers.core.container import DockerContainer
from typing_extensions import Self


class Pod:
    def __init__(
        self,
        name: str,
        namespace: str | None = None,
        *,
        client: ApiClient | None = None,
        **metadata,
    ) -> None:
        self._pod = None
        self._name = name
        self._namespace = namespace or "default"
        self._metadata = metadata
        self.client = client
        self.created_pod = False
        self.existing_pod = False
        self.wait_for_condition = "Ready"
        self.timeout = 60

    @classmethod
    def from_pod(cls, pod: V1Pod, *, client: ApiClient | None = None) -> KubePod:
        self = cls(pod.metadata.name, pod.metadata.namespace, client=client)
        self.pod = pod
        return self

    @property
    def live(self) -> bool:
        return self.created_pod or self.existing_pod

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value) -> None:
        assert self._pod is None
        self._name = value

    @property
    def namespace(self) -> str:
        return self._namespace

    @namespace.setter
    def namespace(self, value) -> None:
        assert self._pod is None
        self._namespace = value

    @property
    def pod(self) -> V1Pod:
        if self._pod is None:
            self._pod = V1Pod(
                metadata=V1ObjectMeta(
                    namespace=self.namespace,
                    name=self.name,
                    **self._metadata,
                ),
                spec=V1PodSpec(containers=[]),
            )
        return self._pod

    @pod.setter
    def pod(self, value: V1Pod) -> None:
        assert not self.live
        self._pod = deepcopy(value)
        self._pod.metadata.name = self._name
        self._pod.metadata.namespace = self._namespace

    def refresh(self) -> Self:
        assert self.live
        self._pod = CoreV1Api(self.client).read_namespaced_pod(self.name, self.namespace)
        return self

    def with_testcontainer(self, container: DockerContainer) -> Self:
        def parse_port_mapping(c_port):
            port, _, proto = (
                c_port.partition("/") if isinstance(c_port, str) else (c_port, None, None)
            )
            return dict(container_port=int(port), protocol=proto or None)

        c = V1Container(
            args=container._command,
            command=container._kwargs.get("entrypoint"),
            env=[V1EnvVar(name=name, value=value) for name, value in container.env.items()],
            image=container.image,
            name=container._name or f"{self.name}-{len(self.pod.spec.containers)}",
            ports=[
                V1ContainerPort(host_port=h_port, **parse_port_mapping(c_port))
                for c_port, h_port in container.ports.items()
            ],
            working_dir=container._kwargs.get("working_dir"),
        )
        return self.with_container(c)

    def with_container(self, container: V1Container) -> Self:
        assert not self.live
        self.pod.spec.containers.append(container)
        return self

    def __enter__(self):
        namespace = self.ensure_namespace()
        api = CoreV1Api(self.client)
        created_pod = api.create_namespaced_pod(namespace, self.pod)
        self.created_pod = True

        w = Watch()
        stream = w.stream(
            api.list_namespaced_pod,
            namespace=namespace,
            field_selector=f"metadata.name={self.name}",
            resource_version=created_pod.metadata.resource_version,
            timeout_seconds=self.timeout,
        )

        if self.wait_until_condition(stream, self.wait_for_condition):
            w.stop()
        else:
            raise TimeoutError(
                f"{namespace}/{self.name}: timeout waiting for pod to become {self.wait_for_condition}"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.created_pod:
            api = CoreV1Api(self.client)
            api.delete_namespaced_pod(namespace=self.namespace, name=self.name)
            self.created_pod = False

    def wait_until_condition(self, stream, type: str):
        condition_met = False
        for event in stream:
            pod = event["object"]
            phase = pod.status.phase
            print(f"→ [{self.namespace}/{self.name}] Pod phase: {phase}")
            conditions = pod.status.conditions or []
            sorted_conditions = sorted(
                (c for c in conditions if c.status == "True"),
                key=lambda c: (c.last_transition_time or "", -len(c.type)),
            )
            for cond in sorted_conditions:
                message = f": {cond.message}" if cond.message else ""
                print(f"  ✓ {cond.type}{': ' if message else ''}{message}")
                condition_met |= cond.type == type

            if condition_met:
                return True

        return False

    def ensure_namespace(self) -> str:
        namespace = self.namespace
        api = CoreV1Api(self.client)

        # Ensure namespace exists
        try:
            api.read_namespace(namespace)
        except ApiException as e:
            if e.status == 404:
                print(f"→ Creating namespace: {namespace}")
                api.create_namespace(V1Namespace(metadata=V1ObjectMeta(name=namespace)))
            else:
                raise

        # Wait for default service account
        for _ in range(10):
            try:
                api.read_namespaced_service_account("default", namespace)
                break
            except ApiException as e:
                if e.status == 404:
                    time.sleep(1)
                else:
                    raise
        else:
            raise TimeoutError(f"Default service account not available in namespace '{namespace}'")

        return namespace
