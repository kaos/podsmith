# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import time

from kubernetes.client import ApiClient, CoreV1Api, V1Namespace, V1ObjectMeta, V1Pod
from kubernetes.client.exceptions import ApiException
from kubernetes.watch import Watch


class KubePod:
    def __init__(self, pod: V1Pod, /, client: ApiClient | None = None) -> None:
        self.client = client
        self.pod = pod
        self.created_pod = False
        self.wait_for_condition = "Ready"
        self.timeout = 60

    @property
    def namespace(self):
        return self.pod.metadata.namespace or "default"

    @property
    def name(self):
        return self.pod.metadata.name

    def get_pod(self):
        return CoreV1Api(self.client).read_namespaced_pod(self.name, self.namespace)

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
