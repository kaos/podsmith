# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import os
import subprocess
import time
from dataclasses import dataclass

import pytest
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import MaxRetryError

from .image import ImageLoader
from .manifest import get_default_namespace
from .session import Session


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "podsmith_scope(scope): Session scope for podsmith session. (Scope value used as pytest fixture scope.)",
    )


@dataclass(frozen=True)
class ClusterInfo:
    context: str
    cluster: str
    kubeconfig: str
    ephemeral: bool
    image_loader: ImageLoader | None


def get_current_cluster_info():
    tpl = '{{index . "current-context"}}|{{index . "contexts" 0 "context" "cluster" }}'
    result = subprocess.run(
        ["kubectl", "config", "view", "--minify", "-o=go-template", f"--template={tpl}"],
        capture_output=True,
        text=True,
        check=True,
    )
    context, _, cluster = result.stdout.strip().partition("|")
    return dict(context=context, cluster=cluster)


def make_cluster_info(**info):
    info.update(get_current_cluster_info())
    return ClusterInfo(
        kubeconfig=os.getenv("KUBECONFIG"),
        image_loader=ImageLoader.create(info["cluster"]),
        **info,
    )


if kubeconfig := os.getenv("KUBECONFIG"):

    @pytest.fixture(scope="session")
    def podsmith_cluster():
        """Use current cluster context as configured in kube config."""
        config.load_kube_config(config_file=kubeconfig)
        yield make_cluster_info(ephemeral=False)

else:

    @pytest.fixture(scope="session")
    def podsmith_cluster(kind_cluster):
        """Use temporary cluster managed by kind."""
        return kind_cluster


@pytest.fixture(scope="session")
def kind_cluster(tmp_path_factory):
    cluster_name = "podsmith-dev"
    tmp_dir = tmp_path_factory.mktemp("kube")
    kubeconfig_file = tmp_dir / "kubeconfig.yaml"

    # Create the kind cluster
    subprocess.run(
        ["kind", "create", "cluster", "--name", cluster_name, "--kubeconfig", str(kubeconfig_file)],
        check=True,
    )

    # Set env + load config
    os.environ["KUBECONFIG"] = str(kubeconfig_file)
    config.load_kube_config(config_file=str(kubeconfig_file))

    # Wait until API is responsive
    v1 = client.CoreV1Api()
    for attempt in range(30):  # ~30 seconds max
        try:
            v1.list_namespace()
            break
        except (ApiException, MaxRetryError):
            time.sleep(1)
    else:
        raise RuntimeError("Kubernetes cluster did not become ready in time")

    yield make_cluster_info(ephemeral=True)

    # Teardown
    subprocess.run(["kind", "delete", "cluster", "--name", cluster_name], check=True)


@pytest.fixture
def podsmith_namespace():
    return get_default_namespace("podsmith-test")


@pytest.fixture
def podsmith_session_scope(request, podsmith_sessions):
    scope = getattr(request.module, "podsmith_scope", "function")
    if (marker := request.node.get_closest_marker("podsmith_scope")) is not None:
        scope = marker.args[0]
    if not scope:
        raise Exception(
            'missing `podsmith_scope` marker or module level variable. hint: add something like `@pytest.mark.podsmith_scope("module")` to your test.'
        )
    if scope not in podsmith_sessions:
        raise ValueError(
            f"Invalid podsmith_scope: {scope!r}. Must be one of: {', '.join(podsmith_sessions)}"
        )
    return scope


@pytest.fixture
def podsmith_session(podsmith_session_scope, podsmith_sessions):
    return podsmith_sessions[podsmith_session_scope]


@pytest.fixture
def podsmith_sessions(
    podsmith_global_session,
    podsmith_pkg_session,
    podsmith_mod_session,
    podsmith_cls_session,
    podsmith_fun_session,
):
    return {
        "function": podsmith_fun_session,
        "class": podsmith_cls_session,
        "module": podsmith_mod_session,
        "package": podsmith_pkg_session,
        "session": podsmith_global_session,
    }


def _podsmith_session_fixture_factory(name, scope):
    @pytest.fixture(name=name, scope=scope)
    def _podsmith_session_fixture():
        with Session() as session:
            yield session

    return _podsmith_session_fixture


for key, scope in {
    "global": "session",
    "pkg": "package",
    "mod": "module",
    "cls": "class",
    "fun": "function",
}.items():
    name = f"podsmith_{key}_session"
    globals()[name] = _podsmith_session_fixture_factory(name, scope)
