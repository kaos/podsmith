# Podsmith

**Podsmith** is a Python toolkit for managing Kubernetes-based test dependencies, enabling dynamic or pre-provisioned environments for integration testing.

Inspired by (and supports using) [Testcontainers](https://www.testcontainers.org/), Podsmith lets you define service dependencies as code and run your tests locally or remotely, with full control over whether resources are deployed on-the-fly or expected to be pre-provisioned.

---

## ✨ Features

- 🛠  Deploy Kubernetes resources from Python definitions
- 🔍 Optionally reuse existing resources
- ⏳ Built-in support for readiness checks (e.g., pod status, HTTP, service endpoints)
- 🧪 Integrates with `pytest`
- 🚀 Works with local clusters (e.g., `k3s`, `kind`) or remote (using `kubectl`)

## ✨ Planned Features

- 📦 Snapshot current test environment for reusable kubernetes manifests
- 🐳 Pre-build test images locally for publishing to pre-populate a docker registry.

---

## 🔧 Installation

```bash
pip install podsmith
```

---

## 🚀 Quickstart

Simple example to deploy a redis testcontainer as a Kubernetes Pod.

```python
from podsmith import Pod
from testcontainers.redis import RedisContainer

redis_container = RedisContainer()

with Pod("redis").with_testcontainer(redis_container, service_port_map={redis_container.port: "redis"}) as redis:
    # Port-forward from k8s cluster to localhost, only needed if test needs to connect to the service directly.
    with redis.port_forward("redis") as port:
        url = f"redis://127.0.0.1:{port}"
        # Use redis service in your test
```

This example deploys a `redis` pod using a testcontainer as template, and register a Service manifest for the `redis` service port. When the context manager exits, the pod is deleted.

---

## 📸 (Planned) Snapshot Test Manifests

### WIP -- AI generated example, not accurate.

Generate a manifest snapshot of your test environment:

```bash
podsmith snapshot --namespace test-env --output ./snapshots/
```

Apply in CI:
```bash
kubectl apply -f ./snapshots/
```

---

## 📚 (Wishful thinking) Documentation

- [Getting Started](docs/getting-started.md)
- [API Reference](docs/api.md)
- [Usage with pytest](docs/pytest.md)
- [Snapshotting](docs/snapshotting.md)

---

## 📝 License

MIT License

---

## 🤝 Contributing

Contributions, ideas, and bug reports are welcome! Please open an issue or PR on GitHub.
