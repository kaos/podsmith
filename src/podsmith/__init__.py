# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
"""**Podsmith** is a Python toolkit for managing Kubernetes-based test dependencies, enabling dynamic or pre-provisioned environments for integration testing."""

__version__ = "0.3"

from .config_map import ConfigMap
from .manifest import random_text
from .pod import Pod
from .role import ClusterRole, Role
from .role_binding import ClusterRoleBinding, RoleBinding
from .service import Service
from .service_account import ServiceAccount
from .session import Session

__all__ = [
    "ClusterRole",
    "ClusterRoleBinding",
    "ConfigMap",
    "Pod",
    "Role",
    "RoleBinding",
    "Service",
    "ServiceAccount",
    "Session",
    "random_text",
]
