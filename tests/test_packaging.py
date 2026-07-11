from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "PrismaFunction.spec"
BUILD_SCRIPT = ROOT / "build.bat"
REQUIREMENTS = ROOT / "requirements.txt"


def test_spec_configures_windows_gui_application():
    assert SPEC.is_file()
    content = SPEC.read_text(encoding="utf-8")

    assert '["app.py"]' in content
    assert 'name="PrismaFunction"' in content
    assert "console=False" in content
    assert 'collect_submodules("playwright")' in content
    assert "COLLECT(" in content


def test_pyinstaller_is_a_pinned_dependency():
    requirements = REQUIREMENTS.read_text(encoding="utf-8").splitlines()

    assert any(line.lower().startswith("pyinstaller==") for line in requirements)


def test_build_script_invokes_pyinstaller_with_spec():
    content = BUILD_SCRIPT.read_text(encoding="utf-8").lower()

    assert "-m pyinstaller" in content
    assert "prismafunction.spec" in content
    assert 'cd /d "%~dp0"' in content
    assert 'rmdir /s /q "build"' in content
    assert 'rmdir /s /q "dist"' in content
    assert ".venv\\scripts\\python.exe" not in content
    assert "if errorlevel 1 exit /b %errorlevel%" in content
