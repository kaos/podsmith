python_distribution(
    name="dist",
    provides=python_artifact(name="podsmith"),
    dependencies=[":dist-files", "src/podsmith"],
    sdist=False,
    repositories=["@pypi"],
    entry_points={
        "pytest11": {
            "podsmith": "podsmith.pytest_plugin",
        }
    },
)

resources(
    name="dist-files",
    sources=[
        "pyproject.toml",
        "LICENSE",
        "README.md",
    ],
)
