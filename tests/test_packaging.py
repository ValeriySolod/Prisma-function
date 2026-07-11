from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "PrismaFunction.spec"
BUILD_SCRIPT = ROOT / "build.bat"


def test_spec_configures_windows_gui_application():
    assert SPEC.is_file()
    content = SPEC.read_text(encoding="utf-8")

    assert '["app.py"]' in content
    assert 'name="PrismaFunction"' in content
    assert "console=False" in content
    assert 'collect_submodules("playwright")' in content


def test_build_script_invokes_pyinstaller_with_spec():
    content = BUILD_SCRIPT.read_text(encoding="utf-8").lower()

    assert "-m pyinstaller" in content
    assert "prismafunction.spec" in content
