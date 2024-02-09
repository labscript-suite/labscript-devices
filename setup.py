import os
from setuptools import setup

setup(
    use_scm_version={
        "version_scheme": os.getevn("SCM_VERSION_SCHEME", "release-branch-semver"),
        "local_scheme": os.getenv("SCM_LOCAL_SCHEME", "node-and-date"),
    }
)
