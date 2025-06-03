from kubernetes.client import RbacAuthorizationV1Api, V1PolicyRule, V1Role
from typing_extensions import Self

from .manifest import Manifest


class Role(Manifest[V1Role]):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rules = []

    def with_rule(self, **policy) -> Self:
        assert not self.live
        self.rules.append(V1PolicyRule(**policy))
        return self

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
