"""Build the wheel locally, install it in isolation, and exercise the installed package."""

import glob
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).parents[2]


def _run(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture(scope="module")
def wheel(tmp_path_factory):
    dist = tmp_path_factory.mktemp("dist")
    _run(["uv", "build", "--wheel", "-o", str(dist)], cwd=REPO_ROOT)
    return glob.glob(str(dist / "*.whl"))[0]


def test_installed_package_configures_from_parts(wheel, tmp_path):
    code = (
        "import audioclassifier\n"
        "from audioclassifier.config.detection_config import get_detection_config, set_detection_config\n"
        "err = None\n"
        "try:\n"
        "    get_detection_config()\n"
        "except RuntimeError as e:\n"
        "    err = 'guided-error' if 'No detection config' in str(e) else 'wrong-error'\n"
        "c = set_detection_config(instructions='Find X. {optional_sponsors_section}', keywords=['x'])\n"
        "print(err, c.name, len(c.keywords), callable(audioclassifier.process_episode))"
    )
    out = _run(
        ["uv", "run", "--no-project", "--with", wheel, "python", "-c", code],
        cwd=tmp_path,  # away from the repo so imports come from the wheel
    )
    err, name, keyword_count, has_api = out.stdout.split()
    assert err == "guided-error"
    assert name == "custom"
    assert keyword_count == "1"
    assert has_api == "True"


def test_installed_console_script(wheel, tmp_path):
    out = _run(
        ["uv", "run", "--no-project", "--with", wheel, "audioclassifier", "--help"],
        cwd=tmp_path,
    )
    assert "--detection" in out.stdout
