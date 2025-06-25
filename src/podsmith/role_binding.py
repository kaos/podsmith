# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from kubernetes.client import (
    RbacAuthorizationV1Api,
    RbacV1Subject,
    V1ClusterRoleBinding,
    V1RoleBinding,
    V1RoleRef,
)
from typing_extensions import Self

from .manifest import ClusterManifest, Manifest
from .role import Role
from .service_account import ServiceAccount

# Currently not defined.
User = None
Group = None


class RoleBindingBase:
    def __init__(self, *args, role: Role, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.role = role
        self.subjects = []

    def with_subject(self, subject: ServiceAccount | User | Group) -> Self:
        assert not self.live
        self.subjects.append(
            RbacV1Subject(
                kind=type(subject).__name__,
                name=subject.name,
                namespace=subject.namespace,
            )
        )
        return self


class ClusterRoleBinding(RoleBindingBase, ClusterManifest[V1ClusterRoleBinding]):
    def _create(self) -> V1ClusterRoleBinding:
        return RbacAuthorizationV1Api(self.client).create_cluster_role_binding(self.manifest)

    def _delete(self) -> None:
        RbacAuthorizationV1Api(self.client).delete_cluster_role_binding(self.name)

    def _new_manifest(self) -> V1ClusterRoleBinding:
        return V1ClusterRoleBinding(
            metadata=self.metadata,
            role_ref=V1RoleRef(
                api_group="rbac.authorization.k8s.io",
                kind="ClusterRole",
                name=self.role.name,
            ),
            subjects=self.subjects,
        )

    def _get_manifest(self) -> V1ClusterRoleBinding:
        return RbacAuthorizationV1Api(self.client).read_cluster_role_binding(self.name)


class RoleBinding(RoleBindingBase, Manifest[V1RoleBinding]):
    def _create(self) -> V1RoleBinding:
        return RbacAuthorizationV1Api(self.client).create_namespaced_role_binding(
            self.namespace, self.manifest
        )

    def _delete(self) -> None:
        RbacAuthorizationV1Api(self.client).delete_namespaced_role_binding(
            self.name, self.namespace
        )

    def _new_manifest(self) -> V1RoleBinding:
        return V1RoleBinding(
            metadata=self.metadata,
            role_ref=V1RoleRef(
                api_group="rbac.authorization.k8s.io",
                kind="Role",
                name=self.role.name,
            ),
            subjects=self.subjects,
        )

    def _get_manifest(self) -> V1RoleBinding:
        return RbacAuthorizationV1Api(self.client).read_namespaced_role_binding(
            self.name, self.namespace
        )
