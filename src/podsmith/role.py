# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from kubernetes.client import RbacAuthorizationV1Api, V1ClusterRole, V1PolicyRule, V1Role
from typing_extensions import Self

from .manifest import ClusterManifest, Manifest


class RoleBase:
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rules = []

    def with_rule(self, **policy) -> Self:
        assert not self.live
        self.rules.append(V1PolicyRule(**policy))
        return self


class ClusterRole(RoleBase, ClusterManifest[V1ClusterRole]):
    def _create(self) -> V1ClusterRole:
        return RbacAuthorizationV1Api(self.client).create_cluster_role(self.manifest)

    def _delete(self) -> None:
        RbacAuthorizationV1Api(self.client).delete_cluster_role(self.name)

    def _new_manifest(self) -> V1ClusterRole:
        return V1ClusterRole(metadata=self.metadata, rules=self.rules)

    def _get_manifest(self) -> V1ClusterRole:
        return RbacAuthorizationV1Api(self.client).read_cluster_role(self.name)


class Role(RoleBase, Manifest[V1Role]):
    def _create(self) -> V1Role:
        return RbacAuthorizationV1Api(self.client).create_namespaced_role(
            self.namespace, self.manifest
        )

    def _delete(self) -> None:
        RbacAuthorizationV1Api(self.client).delete_namespaced_role(self.name, self.namespace)

    def _new_manifest(self) -> V1Role:
        return V1Role(metadata=self.metadata, rules=self.rules)

    def _get_manifest(self) -> V1Role:
        return RbacAuthorizationV1Api(self.client).read_namespaced_role(self.name, self.namespace)
