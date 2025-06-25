# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from contextlib import ExitStack

from typing_extensions import Self

from .manifest import Manifest


class Session:
    def __init__(self):
        self._stack = ExitStack()
        self._resources = defaultdict(dict)

    @property
    def default_namespace(self) -> str | None:
        for namespace in self._resources.keys():
            return namespace
        return None

    def resources(self, namespace: str | None = None) -> Iterable[Manifest]:
        return self._resources[namespace].values()

    def load(self, *resources: Manifest) -> tuple[Manifest, ...]:
        return tuple(map(self.load_resource, resources))

    def load_resource(self, resource: Manifest) -> Manifest:
        key = f"{type(resource).__name__}::{resource.name}"
        if key in self._resources[resource.namespace]:
            resource = self._resources[resource.namespace][key]
        else:
            self._resources[resource.namespace][key] = resource
            resource = self._stack.enter_context(resource)
        return resource

    def unload_all(self) -> None:
        self._stack.close()
        self._resources.clear()

    def pop_all(self) -> Session:
        new_session = type(self)()
        new_session._stack = self._stack
        new_session._resources = self._resources
        self._stack = ExitStack()
        self._resources = defaultdict(dict)
        return new_session

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_details):
        return self._stack.__exit__(*exc_details)
