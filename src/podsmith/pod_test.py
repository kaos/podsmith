# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.

from kubernetes.client import V1Container, V1ObjectMeta, V1Pod, V1PodSpec
from testcontainers.mongodb import MongoDbContainer

from .pod import Pod


def test_kube_pod(podsmith_cluster):
    mongo = V1Pod(
        metadata=V1ObjectMeta(namespace="test1", name="mongo"),
        spec=V1PodSpec(
            containers=[
                V1Container(
                    name="mongo",
                    image="mongo",
                ),
            ],
        ),
    )
    with Pod.from_pod(mongo) as pod:
        assert pod.manifest.status.phase == "Running"


def test_kube_pod_from_testcontainer(podsmith_cluster):
    mongo = MongoDbContainer("mongo:7.0.12")
    with Pod("mongo", namespace="test2").with_testcontainer(mongo) as pod:
        assert pod.manifest.status.phase == "Running"
