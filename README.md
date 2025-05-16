# Podsmith

**Podsmith** is a Python toolkit for managing Kubernetes-based test dependencies, enabling dynamic or pre-provisioned environments for integration testing.

Inspired by [Testcontainers](https://www.testcontainers.org/), Podsmith lets you define service dependencies as code and run your tests locally or remotely, with full control over whether resources are deployed on-the-fly or expected to be pre-provisioned.

---

## ✨ (Planned) Features

- 🛠  Deploy Kubernetes resources from Python definitions
- 🔍 Optionally reuse existing resources
- ⏳ Built-in support for readiness checks (e.g., pod status, HTTP, service endpoints)
- 📦 Snapshot current test environment for reusable kubernetes manifests
- 🧪 Integrates with `pytest`
- 🚀 Works with local clusters (e.g., `k3s`, `kind`) or remote CI (e.g., [Testkube](https://testkube.io))

---

## 🔧 Installation

```bash
pip install podsmith
```

---

## 🚀 Quickstart

### WIP -- AI generated example, not accurate.

```python
from podsmith import KubeResource

with KubeResource("redis", manifest="manifests/redis.yaml", mode="deploy") as redis:
    redis.wait_until_ready()
    url = redis.service_url(port=6379)
    # Use redis service in your test
```

Set the mode via environment variable:
```bash
export PODSMITH_MODE=deploy  # or "reuse"
```

---

## 📸 Snapshot Test Manifests

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

## 📚 Documentation

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
