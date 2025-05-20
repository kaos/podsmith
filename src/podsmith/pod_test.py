# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import pytest
from kubernetes import client

# import yaml
from kubernetes.client import V1Container, V1ObjectMeta, V1Pod, V1PodSpec
from testcontainers.mongodb import MongoDbContainer

from .pod import Pod

# from testcontainers.k3s import K3SContainer


@pytest.fixture
def podsmith_cluster(kind_cluster):
    """Cluster indirection to allow different implementations based on ENV vars etc."""


# @pytest.fixture(scope="session")
# def client():
#     k3s_args = [
#         "server",
#         "--kubelet-arg=cgroup-driver=systemd@server:*"
#     ]
#     with K3SContainer().with_command(k3s_args) as k3s:
#         kubernetes.config.load_kube_config_from_dict(yaml.safe_load(k3s.config_yaml()))
#         yield kubernetes.client


# def test_client(client):
#     pods = client.CoreV1Api().list_pod_for_all_namespaces()
#     assert len(pods.items) > 0
#     # for pod in pods.items:
#     #     m = pod.metadata
#     #     print(f"{pod.kind} {m.namespace}::{m.name} {pod.status.message!r}")


def test_kube_pod(podsmith_cluster):
    mongo = V1Pod(
        metadata=V1ObjectMeta(namespace="test", name="mongo"),
        spec=V1PodSpec(
            containers=[
                V1Container(
                    name="mongo",
                    image="mongo",
                ),
            ],
        ),
    )
    with Pod.from_pod(mongo) as res:
        assert res.refresh().pod.status.phase == "Running"
        # from pprint import pprint

        # pprint(res.refresh().pod.to_dict())

    # assert False


def test_kube_pod_from_testcontainer(podsmith_cluster):
    mongo = MongoDbContainer("mongo:7.0.12")
    with Pod("mongo", namespace="test").with_testcontainer(mongo) as res:
        assert res.refresh().pod.status.phase == "Running"
