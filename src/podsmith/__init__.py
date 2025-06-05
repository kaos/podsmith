# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
"""**Podsmith** is a Python toolkit for managing Kubernetes-based test dependencies, enabling dynamic or pre-provisioned environments for integration testing."""

__version__ = "1.0.0"

from .manifest import random_text
from .pod import Pod
from .role import ClusterRole, Role
from .role_binding import ClusterRoleBinding, RoleBinding
from .service import Service
from .service_account import ServiceAccount

__all__ = [
    "ClusterRole",
    "ClusterRoleBinding",
    "Pod",
    "Role",
    "RoleBinding",
    "Service",
    "ServiceAccount",
    "random_text",
]
