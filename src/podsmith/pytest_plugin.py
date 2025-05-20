# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import os
import subprocess
import time

import pytest
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import MaxRetryError

if kubeconfig := os.getenv("KUBECONFIG"):

    @pytest.fixture
    def podsmith_cluster():
        """Use current cluster context as configured in kube config."""
        config.load_kube_config(config_file=kubeconfig)

else:

    @pytest.fixture
    def podsmith_cluster(kind_cluster):
        """Use temporary cluster managed by kind."""


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

    yield {
        "name": cluster_name,
        "kubeconfig": str(kubeconfig_file),
    }

    # Teardown
    subprocess.run(["kind", "delete", "cluster", "--name", cluster_name], check=True)
