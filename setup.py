import os
from setuptools import setup

setup(
    use_scm_version={
        "version_scheme": "release-branch-semver",
        "local_scheme": os.getenv("SCM_LOCAL_SCHEME", "node-and-date"),
    }
)
