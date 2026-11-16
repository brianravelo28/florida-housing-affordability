"""
Project configuration: dependency bounds, the Python versions CI covers, Dependabot, and the host's Python version.
"""

import glob
import os
import re

import pytest
from packaging.requirements import Requirement

import acs_config as cfg

ROOT = cfg.ROOT
SUPPORTED_PYTHONS = ['3.12', '3.13', '3.14']   # NumPy 2.5 needs 3.12 or newer; the full requirements install as wheels on all three


def read(*parts):
    return open(os.path.join(ROOT, *parts), encoding='utf-8').read()


def requirement_lines():
    for path in sorted(glob.glob(os.path.join(ROOT, 'requirements*.txt'))):
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith(('#', '-r')):
                yield os.path.basename(path), Requirement(line)


@pytest.mark.parametrize('file,req', list(requirement_lines()), ids=lambda x: x if isinstance(x, str) else x.name)
def test_every_package_has_a_minimum_and_a_cap_at_the_next_major_version(file, req):
    ops = {spec.operator for spec in req.specifier}
    assert '>=' in ops and '<' in ops, f"{req.name} in {file} needs a minimum and an upper bound"


def test_the_host_python_version_is_a_full_version_inside_the_supported_range():
    version = read('.python-version').strip()
    assert version.count('.') == 2, "Render needs a full x.y.z version"
    assert '.'.join(version.split('.')[:2]) in SUPPORTED_PYTHONS


def test_ci_runs_every_supported_python_version():
    workflow = read('.github', 'workflows', 'tests.yml')
    versions = re.search(r'python-version:\s*\[([^\]]*)\]', workflow).group(1)
    assert [v.strip().strip('"') for v in versions.split(',')] == SUPPORTED_PYTHONS
    assert 'matrix.python-version' in workflow and 'fail-fast: false' in workflow


def test_dependabot_covers_packages_and_actions_weekly():
    config = read('.github', 'dependabot.yml')
    for ecosystem in ('pip', 'github-actions'):
        block = config.split(f'package-ecosystem: {ecosystem}')[1].split('package-ecosystem:')[0]
        assert 'interval: weekly' in block, ecosystem


def test_the_readme_names_the_supported_python_versions():
    assert 'Python 3.12 or newer' in read('README.md')
