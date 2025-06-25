# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

import re
import socket
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial

import backoff
from kubernetes.client import (
    ApiClient,
    CoreV1Api,
    V1Container,
    V1ContainerPort,
    V1EnvVar,
    V1ExecAction,
    V1Lifecycle,
    V1LifecycleHandler,
    V1Pod,
    V1PodSpec,
    V1ServicePort,
)
from kubernetes.watch import Watch
from testcontainers.core.container import DockerContainer
from typing_extensions import Self

from .image import ImageLoader
from .manifest import Manifest
from .role import ClusterRole, Role, RoleBase
from .role_binding import ClusterRoleBinding, RoleBinding, RoleBindingBase
from .service import APP_LABEL, Service
from .service_account import ServiceAccount


class Pod(Manifest[V1Pod]):
    @dataclass
    class Rbac:
        role: RoleBase
        binding: RoleBindingBase

        @classmethod
        def new(cls, pod: Pod) -> Pod.Rbac:
            role = Role(f"{pod.name}-role", pod.namespace)
            return cls(
                role,
                RoleBinding(f"{pod.name}-role-binding", pod.namespace, role=role).with_subject(
                    pod.service_account
                ),
            )

        @classmethod
        def cluster_new(cls, pod: Pod) -> Pod.Rbac:
            role = ClusterRole(f"{pod.namespace}-{pod.name}-cluster-role")
            return cls(
                role,
                ClusterRoleBinding(
                    f"{pod.namespace}-{pod.name}-cluster-role-binding", role=role
                ).with_subject(pod.service_account),
            )

        def create(self) -> None:
            self.role.create()
            self.binding.create()

        def destroy(self) -> None:
            self.binding.destroy()
            self.role.destroy()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.wait_for_condition = "Ready"
        self.timeout = 60
        self.services = {}
        self._service_account = None
        self._rbac = None
        self._cluster_rbac = None

    @classmethod
    def from_pod(cls, pod: V1Pod, *, client: ApiClient | None = None) -> Pod:
        self = cls(pod.metadata.name, pod.metadata.namespace, client=client)
        self.manifest = pod
        return self

    @property
    def service_account(self) -> ServiceAccount | None:
        if self._service_account is None and self.manifest.spec.service_account_name is None:
            assert not self.live
            self._service_account = ServiceAccount(f"{self.name}-account", self.namespace)
            self.manifest.spec.service_account_name = self._service_account.name
        return self._service_account

    @property
    def rbac(self) -> Pod.Rbac:
        if self._rbac is None:
            self._rbac = Pod.Rbac.new(self)
        return self._rbac

    @property
    def cluster_rbac(self) -> Pod.Rbac:
        if self._cluster_rbac is None:
            self._cluster_rbac = Pod.Rbac.cluster_new(self)
        return self._cluster_rbac

    def _new_manifest(self) -> V1Pod:
        self.metadata.labels.setdefault(APP_LABEL, self.name)
        return V1Pod(
            metadata=self.metadata,
            spec=V1PodSpec(containers=[]),
        )

    def _get_manifest(self) -> V1Pod:
        return CoreV1Api(self.client).read_namespaced_pod(self.name, self.namespace)

    def _create(self) -> V1Pod:
        return CoreV1Api(self.client).create_namespaced_pod(self.namespace, self.manifest)

    def _delete(self) -> None:
        CoreV1Api(self.client).delete_namespaced_pod(namespace=self.namespace, name=self.name)

    def create(self) -> Self:
        self.create_auth()
        super().create()
        namespace = self.namespace
        api = CoreV1Api(self.client)
        w = Watch()
        stream = w.stream(
            api.list_namespaced_pod,
            namespace=namespace,
            field_selector=f"metadata.name={self.name}",
            resource_version=self.manifest.metadata.resource_version,
            timeout_seconds=self.timeout,
        )

        if self.wait_until_condition(stream, self.wait_for_condition):
            w.stop()
            for svc in self.services.values():
                svc.create()
        else:
            try:
                pod_status = self.refresh().manifest.status
                pod_name = self.name

                # Collect conditions
                cond_lines = []
                for cond in sorted(
                    pod_status.conditions or [],
                    key=lambda c: c.last_transition_time or "",
                ):
                    cond_lines.append(
                        f"- {cond.type} = {cond.status} @ {cond.last_transition_time} "
                        f"(reason: {cond.reason}, message: {cond.message})"
                    )

                # Collect logs from all containers (if possible)
                log_lines = []
                for container in self.manifest.spec.containers:
                    try:
                        logs = self.get_logs(container.name, tail_lines=20)
                        log_lines.append(f"--- Logs from container '{container.name}' ---\n{logs}")
                    except Exception as e:
                        log_lines.append(
                            f"--- Logs from container '{container.name}' unavailable: {e} ---"
                        )

                raise TimeoutError(
                    f"{namespace}/{pod_name}: timeout waiting for pod to become {self.wait_for_condition}\n"
                    f"Pod phase: {pod_status.phase}\n"
                    f"Conditions:\n" + "\n".join(cond_lines) + "\n\n" + "\n\n".join(log_lines)
                )
            finally:
                self.destroy()
                # no return

        return self.refresh()

    def destroy(self):
        for svc in self.services.values():
            svc.destroy()
        super().destroy()
        self.destroy_auth()

    def create_auth(self) -> None:
        if self._service_account is not None:
            self.service_account.create()
        if self._rbac is not None:
            self.rbac.create()
        if self._cluster_rbac is not None:
            self.cluster_rbac.create()

    def destroy_auth(self) -> None:
        if self._rbac is not None:
            self.rbac.destroy()
        if self._cluster_rbac is not None:
            self.cluster_rbac.destroy()
        if self._service_account is not None:
            self.service_account.destroy()

    def wait_until_condition(self, stream, type: str):
        condition_met = False
        for event in stream:
            pod = event["object"]
            phase = pod.status.phase
            print(f"→ [{self}] Pod phase: {phase}")
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

    def create_services(self, container: V1Container) -> Self:
        for port in container.ports:
            if not port.name:
                continue
            self.with_service(
                dict(
                    name=port.name,
                    protocol=port.protocol,
                    port=port.container_port,
                    # target_port=port.container_port,
                    # node_port=port.host_port,
                ),
                name=port.name,
                port_type=(
                    Service.PortType.NodePort if port.host_port else Service.PortType.ClusterIP
                ),
            )
        return self

    def with_service(self, *ports: dict, **kwargs) -> Self:
        svc = Service(pod=self, **kwargs)
        svc = self.services.setdefault(svc.name, svc)
        for port_spec in ports:
            svc.add_port(**port_spec)
        return self

    def with_containers(self, *containers: V1Container, service: bool = True) -> Self:
        assert not self.live
        self.manifest.spec.containers.extend(containers)
        if service:
            for container in containers:
                self.create_services(container)
        return self

    def with_container(self, container: V1Container, *, service: bool = True) -> Self:
        assert not self.live
        self.manifest.spec.containers.append(container)
        if service:
            self.create_services(container)
        return self

    def with_testcontainers(
        self, *containers: DockerContainer, service_ports_map: dict[int, str] | None = None
    ) -> Self:
        convert_testcontainer = partial(
            self.convert_testcontainer, service_ports_map=service_ports_map or {}
        )
        return self.with_containers(
            *map(convert_testcontainer, containers), service=bool(service_ports_map)
        )

    def with_testcontainer(
        self, container: DockerContainer, *, service_ports_map: dict[int, str] | None = None
    ) -> Self:
        convert_testcontainer = partial(
            self.convert_testcontainer, service_ports_map=service_ports_map or {}
        )
        return self.with_container(
            convert_testcontainer(container), service=bool(service_ports_map)
        )

    def convert_testcontainer(
        self, container: DockerContainer, service_ports_map: dict[int, str]
    ) -> V1Container:
        def parse_port_mapping(c_port):
            port, _, proto = (
                c_port.partition("/") if isinstance(c_port, str) else (c_port, None, None)
            )
            port = int(port)
            return dict(
                name=service_ports_map.get(port),
                container_port=port,
                protocol=proto or None,
            )

        return V1Container(
            args=container._command,
            command=container._kwargs.get("entrypoint"),
            env=[V1EnvVar(name=name, value=value) for name, value in container.env.items()],
            image=container.image,
            name=container._name or f"{self.name}-{len(self.manifest.spec.containers)}",
            ports=[
                V1ContainerPort(host_port=h_port, **parse_port_mapping(c_port))
                for c_port, h_port in container.ports.items()
            ],
            working_dir=container._kwargs.get("working_dir"),
        )

    def get_logs(self, container: str | None = None, tail_lines: int | None = None) -> str:
        api = CoreV1Api(self.client)
        return api.read_namespaced_pod_log(
            name=self.name,
            namespace=self.namespace,
            container=container,
            tail_lines=tail_lines,
        ).strip()

    def missing_logs(self, opts):
        pattern = opts["args"][0]
        print(f"{self}: missing log pattern {pattern.pattern!r}")

    def await_logs(
        self,
        log_pattern: str,
        container: str | None = None,
        max_time=30,
        max_value=5,
        **backoff_opts,
    ):
        @backoff.on_predicate(
            backoff.fibo,
            on_giveup=self.missing_logs,
            max_time=max_time,
            max_value=max_value,
            **backoff_opts,
        )
        def check_logs(pattern):
            print(f"{self}: awaiting log pattern {pattern.pattern!r}")
            return pattern.search(self.get_logs(container), re.MULTILINE)

        return check_logs(re.compile(log_pattern))

    def preload_images(self, loader: ImageLoader | None) -> Self:
        if loader is not None:
            for container in self.manifest.spec.containers:
                loader.load_image(container.image)
        return self

    def get_port(self, name: str) -> V1ServicePort:
        svc = self.services.get(name)
        ports = [] if svc is None else svc.manifest.spec.ports
        for port in ports:
            if port.name == name:
                return port
        raise ValueError(f"{self.namespace}/{self.name}: no service port found with name: {name}")

    def with_auth_rule(self, **policy) -> Self:
        self.rbac.role.with_rule(**policy)
        return self

    def with_auth_cluster_rule(self, **policy) -> Self:
        self.cluster_rbac.role.with_rule(**policy)
        return self

    def with_post_start_command(self, container_name: str, *command: str) -> Self:
        for container in self.manifest.spec.containers:
            if container.name != container_name:
                continue
            if container.lifecycle is None:
                container.lifecycle = V1Lifecycle()
            action = V1ExecAction(command=command)
            handler = V1LifecycleHandler(_exec=action)
            container.lifecycle.post_start = handler
            break
        else:
            raise ValueError(
                f"{container_name}: no such container found in pod {self.namespace}/{self.name}"
            )
        return self

    @contextmanager
    def port_forward(self, service_name: str) -> int:
        port = self.get_port(service_name).port
        proc = subprocess.Popen(
            ["kubectl", "port-forward", "-n", self.namespace, f"service/{service_name}", str(port)]
        )
        try:
            self.await_serverport(port)
            yield port
        finally:
            proc.terminate()

    @staticmethod
    @backoff.on_predicate(backoff.fibo, max_time=10)
    def await_serverport(port: int, host: str = "127.0.0.1") -> bool:
        addr_info_list = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        for family, socktype, proto, _canonname, sockaddr in addr_info_list:
            try:
                with socket.socket(family, socktype, proto) as sock:
                    sock.settimeout(1)
                    if sock.connect_ex(sockaddr) == 0:
                        return True
            except Exception:
                continue
        return False
