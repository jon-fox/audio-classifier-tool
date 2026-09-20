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


def test_installed_package_imports_with_bundled_config(wheel, tmp_path):
    code = (
        "import audioclassifier; "
        "from audioclassifier.config.detection_config import get_detection_config; "
        "c = get_detection_config(); "
        "print(c.name, len(c.keywords), callable(audioclassifier.process_episode))"
    )
    out = _run(
        ["uv", "run", "--no-project", "--with", wheel, "python", "-c", code],
        cwd=tmp_path,  # away from the repo so imports come from the wheel
    )
    name, keyword_count, has_api = out.stdout.split()
    assert name == "ads"
    assert int(keyword_count) > 100
    assert has_api == "True"


def test_installed_console_script(wheel, tmp_path):
    out = _run(
        ["uv", "run", "--no-project", "--with", wheel, "audioclassifier", "--help"],
        cwd=tmp_path,
    )
    assert "--detection" in out.stdout
