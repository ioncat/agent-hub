"""
tests/test_cv_adapter.py — Contract tests for CVAdapter.

Mocks asyncio.create_subprocess_exec — no real subprocess needed.
Verifies: python resolution, PDF generation, all error paths.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.cv_adapter import CVAdapter, CVAdapterError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _adapter(tmp_path: Path, *, create_script: bool = True, create_venv_win: bool = False) -> CVAdapter:
    """Build CVAdapter with tmp_path as callback_cv_path."""
    if create_script:
        (tmp_path / "cv_to_pdf.py").write_text("# stub", encoding="utf-8")
    if create_venv_win:
        scripts = tmp_path / "venv" / "Scripts"
        scripts.mkdir(parents=True)
        (scripts / "python.exe").write_text("", encoding="utf-8")
    return CVAdapter(callback_cv_path=tmp_path)


def _mock_proc(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> AsyncMock:
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate.return_value = (stdout, stderr)
    return proc


# ── _resolve_python ───────────────────────────────────────────────────────────

def test_resolve_python_uses_win_venv(tmp_path):
    scripts = tmp_path / "venv" / "Scripts"
    scripts.mkdir(parents=True)
    win_python = scripts / "python.exe"
    win_python.write_text("", encoding="utf-8")
    (tmp_path / "cv_to_pdf.py").write_text("", encoding="utf-8")
    adapter = CVAdapter(callback_cv_path=tmp_path)
    assert adapter._python == str(win_python)


def test_resolve_python_uses_unix_venv(tmp_path):
    bin_dir = tmp_path / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    unix_python = bin_dir / "python"
    unix_python.write_text("", encoding="utf-8")
    (tmp_path / "cv_to_pdf.py").write_text("", encoding="utf-8")
    adapter = CVAdapter(callback_cv_path=tmp_path)
    assert adapter._python == str(unix_python)


def test_resolve_python_falls_back_to_sys_executable(tmp_path):
    (tmp_path / "cv_to_pdf.py").write_text("", encoding="utf-8")
    adapter = CVAdapter(callback_cv_path=tmp_path)
    assert adapter._python == sys.executable


# ── generate_pdf — happy path ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_pdf_returns_pdf_path(tmp_path):
    md = tmp_path / "CV.md"
    md.write_text("# CV", encoding="utf-8")
    pdf = tmp_path / "CV.pdf"
    pdf.write_bytes(b"%PDF-1.4")  # create so adapter finds it

    proc = _mock_proc(returncode=0)
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await _adapter(tmp_path).generate_pdf(md, pdf)
    assert result == pdf


@pytest.mark.asyncio
async def test_generate_pdf_default_output_path(tmp_path):
    """When pdf_path=None, output defaults to md_path.with_suffix('.pdf')."""
    md = tmp_path / "Name_CV.md"
    md.write_text("# CV", encoding="utf-8")
    expected_pdf = tmp_path / "Name_CV.pdf"
    expected_pdf.write_bytes(b"%PDF")

    proc = _mock_proc(returncode=0)
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await _adapter(tmp_path).generate_pdf(md)
    assert result == expected_pdf


@pytest.mark.asyncio
async def test_generate_pdf_calls_correct_args(tmp_path):
    md = tmp_path / "CV.md"
    md.write_text("# CV", encoding="utf-8")
    pdf = tmp_path / "CV.pdf"
    pdf.write_bytes(b"%PDF")

    proc = _mock_proc(returncode=0)
    mock_exec = AsyncMock(return_value=proc)
    with patch("asyncio.create_subprocess_exec", mock_exec):
        adapter = _adapter(tmp_path)
        await adapter.generate_pdf(md, pdf)

    call_args = mock_exec.call_args[0]
    assert call_args[0] == adapter._python
    assert str(adapter._script) in call_args
    assert str(md) in call_args
    assert str(pdf) in call_args


# ── generate_pdf — error paths ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_pdf_script_not_found_raises(tmp_path):
    adapter = CVAdapter(callback_cv_path=tmp_path)  # no cv_to_pdf.py
    md = tmp_path / "CV.md"
    md.write_text("# CV", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="cv_to_pdf.py not found"):
        await adapter.generate_pdf(md)


@pytest.mark.asyncio
async def test_generate_pdf_nonzero_exit_raises(tmp_path):
    md = tmp_path / "CV.md"
    md.write_text("# CV", encoding="utf-8")
    proc = _mock_proc(returncode=1, stderr=b"SyntaxError: invalid syntax")
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        with pytest.raises(CVAdapterError, match="exited 1"):
            await _adapter(tmp_path).generate_pdf(md)


@pytest.mark.asyncio
async def test_generate_pdf_stderr_included_in_error(tmp_path):
    md = tmp_path / "CV.md"
    md.write_text("# CV", encoding="utf-8")
    proc = _mock_proc(returncode=2, stderr=b"ImportError: No module named fpdf")
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        with pytest.raises(CVAdapterError) as exc_info:
            await _adapter(tmp_path).generate_pdf(md)
    assert "fpdf" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_pdf_timeout_raises(tmp_path):
    md = tmp_path / "CV.md"
    md.write_text("# CV", encoding="utf-8")
    proc = AsyncMock()
    proc.communicate.side_effect = asyncio.TimeoutError()
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        with pytest.raises(CVAdapterError, match="timed out"):
            await _adapter(tmp_path).generate_pdf(md)


@pytest.mark.asyncio
async def test_generate_pdf_oserror_raises(tmp_path):
    md = tmp_path / "CV.md"
    md.write_text("# CV", encoding="utf-8")
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(side_effect=OSError("python not found")),
    ):
        with pytest.raises(CVAdapterError, match="Failed to start"):
            await _adapter(tmp_path).generate_pdf(md)


@pytest.mark.asyncio
async def test_generate_pdf_exit_0_but_no_pdf_raises(tmp_path):
    """Subprocess exits 0 but PDF file was not created."""
    md = tmp_path / "CV.md"
    md.write_text("# CV", encoding="utf-8")
    pdf = tmp_path / "CV.pdf"
    # pdf intentionally NOT created
    proc = _mock_proc(returncode=0)
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        with pytest.raises(CVAdapterError, match="PDF not found"):
            await _adapter(tmp_path).generate_pdf(md, pdf)
