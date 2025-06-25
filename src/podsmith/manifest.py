# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

import random
import string
import time
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Generic, TypeVar

from kubernetes.client import ApiClient, CoreV1Api, V1Namespace, V1ObjectMeta
from kubernetes.client.exceptions import ApiException
from typing_extensions import Self


def random_text(length) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def get_default_namespace(create_new_with_prefix: str | None = None, suffix_len: int = 4) -> str:
    global DEFAULT_NAMESPACE
    if not (create_new_with_prefix or DEFAULT_NAMESPACE):
        create_new_with_prefix = "podsmith-test"
    if create_new_with_prefix:
        set_default_namespace(f"{create_new_with_prefix}-{random_text(suffix_len)}")
    return DEFAULT_NAMESPACE


def set_default_namespace(namespace: str) -> None:
    global DEFAULT_NAMESPACE
    DEFAULT_NAMESPACE = namespace


DEFAULT_NAMESPACE = "podsmith-test"
T = TypeVar("T")


class Manifest(ABC, Generic[T]):
    def __init__(
        self,
        name: str,
        namespace: str | None = None,
        *,
        client: ApiClient | None = None,
        **metadata,
    ) -> None:
        metadata.setdefault("annotations", {})
        metadata.setdefault("labels", {})
        self.client = client
        self.created = False
        self.existing = False
        self.created_namespace = False
        self._manifest = None
        self._name = name
        self._namespace = namespace or get_default_namespace()
        self._metadata = metadata

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.namespace}/{self.name}>"

    @property
    def live(self) -> bool:
        return self.created or self.existing

    @property
    def name(self) -> str:
        if self._manifest is None:
            return self._name
        else:
            return self._manifest.metadata.name

    @name.setter
    def name(self, value) -> None:
        assert not self.live
        self._name = value
        if self._manifest is not None:
            self._manifest.metadata.name = value

    @property
    def namespace(self) -> str:
        if self._manifest is None:
            return self._namespace
        else:
            return self._manifest.metadata.namespace

    @namespace.setter
    def namespace(self, value) -> None:
        assert not self.live
        self._namespace = value
        if self._manifest is not None:
            self._manifest.metadata.namespace = value

    @property
    def metadata(self) -> V1ObjectMeta:
        if self._manifest:
            return self._manifest.metadata
        else:
            return V1ObjectMeta(
                namespace=self.namespace,
                name=self.name,
                **self._metadata,
            )

    @property
    def manifest(self) -> T:
        if self._manifest is None:
            self._manifest = self._new_manifest()
        return self._manifest

    @manifest.setter
    def manifest(self, value: T) -> None:
        assert not self.live
        self._manifest = deepcopy(value)
        self._manifest.metadata.name = self._name
        self._manifest.metadata.namespace = self._namespace

    def refresh(self) -> Self:
        assert self.live
        self._manifest = self._get_manifest()
        return self

    def create(self) -> Self:
        api = CoreV1Api(self.client)
        self.ensure_namespace(api)
        print(f"creating {self}...")
        self._manifest = self._create()
        self.created = True
        return self

    def destroy(self):
        if self.created:
            print(f"deleting {self}...")
            self._delete()
            self.created = False
        if self.created_namespace:
            print(f"deleting namespace {self.namespace}...")
            CoreV1Api(self.client).delete_namespace(self.namespace)

    def __enter__(self):
        try:
            return self.create()
        except:
            self.destroy()
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.destroy()

    def ensure_namespace(self, api: CoreV1Api) -> None:
        namespace = self.namespace
        if not namespace:
            return

        # Ensure namespace exists
        try:
            api.read_namespace(namespace)
        except ApiException as e:
            if e.status == 404:
                print(f"→ Creating namespace: {namespace}")
                api.create_namespace(V1Namespace(metadata=V1ObjectMeta(name=namespace)))
                self.created_namespace = True
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

    def with_spec(self, **kwargs) -> Self:
        assert not self.live
        for attr, value in kwargs.items():
            setattr(self.manifest.spec, attr, value)
        return self

    @abstractmethod
    def _create(self) -> T:
        """Create the resource in the cluster."""

    @abstractmethod
    def _delete(self) -> None:
        """Delete the resources from the cluster."""

    @abstractmethod
    def _new_manifest(self) -> T:
        """Create object instance.

        This is a in-memory object only.
        """

    @abstractmethod
    def _get_manifest(self) -> T:
        """Read the resource from the cluster."""


class ClusterManifest(Manifest[T]):
    def __init__(self, name: str, namespace: str | None = None, **kwargs) -> None:
        assert not namespace
        super().__init__(name, **kwargs)
        self._namespace = None

    @property
    def namespace(self) -> None:
        return None
