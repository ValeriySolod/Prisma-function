import logging
from pathlib import Path

import runtime_logging


def reset_logger():
    logger = logging.getLogger(runtime_logging.LOGGER_NAME)
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    return logger


def test_log_initialization_in_source_mode(tmp_path, monkeypatch):
    reset_logger()
    target = tmp_path / "Local App Data" / "PrismaFunction" / "logs" / "prisma-function.log"
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local App Data"))
    monkeypatch.delattr(runtime_logging.sys, "frozen", raising=False)
    monkeypatch.delattr(runtime_logging.sys, "_MEIPASS", raising=False)

    logger, path = runtime_logging.initialize_runtime_logging()
    for handler in logger.handlers:
        handler.flush()

    assert path == target.resolve()
    text = target.read_text(encoding="utf-8")
    assert "mode=source" in text
    assert "python=" in text and "windows=" in text
    assert "executable=" in text and "application_path=" in text
    assert f"log_file={target.resolve()}" in text
    reset_logger()


def test_log_initialization_in_simulated_packaged_mode(tmp_path, monkeypatch):
    reset_logger()
    executable = tmp_path / "Program Files" / "Prisma Function" / "PrismaFunction.exe"
    bundle = executable.parent / "_internal"
    monkeypatch.setattr(runtime_logging.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_logging.sys, "executable", str(executable))
    monkeypatch.setattr(runtime_logging.sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user data"))

    logger, path = runtime_logging.initialize_runtime_logging()
    for handler in logger.handlers:
        handler.flush()
    text = path.read_text(encoding="utf-8")

    assert "mode=packaged" in text
    assert f"application_path={executable.parent.resolve()}" in text
    assert f"package_path={bundle.resolve()}" in text
    reset_logger()


def test_log_initialization_falls_back_to_temp(tmp_path, monkeypatch):
    reset_logger()
    preferred = tmp_path / "blocked" / "prisma-function.log"
    fallback = tmp_path / "fallback" / "prisma-function.log"
    real_create = runtime_logging._create_handler
    monkeypatch.setattr(runtime_logging, "preferred_log_path", lambda: preferred)
    monkeypatch.setattr(runtime_logging, "fallback_log_path", lambda: fallback)

    def create(path):
        if path == preferred:
            raise PermissionError("blocked")
        return real_create(path)

    monkeypatch.setattr(runtime_logging, "_create_handler", create)
    logger, path = runtime_logging.initialize_runtime_logging()

    assert path == fallback.resolve()
    assert fallback.exists()
    reset_logger()


def test_total_logging_failure_uses_null_handler(monkeypatch):
    logger = reset_logger()
    monkeypatch.setattr(
        runtime_logging, "_create_handler", lambda path: (_ for _ in ()).throw(OSError())
    )

    configured, path = runtime_logging.initialize_runtime_logging()

    assert configured is logger
    assert path is None
    assert any(isinstance(handler, logging.NullHandler) for handler in logger.handlers)
    reset_logger()
