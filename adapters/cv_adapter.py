"""
adapters/cv_adapter.py — CVAdapter: subprocess wrapper for callback-cv tools.

Wraps `cv_to_pdf.py` from the callback-cv repo.
Uses the callback-cv virtualenv Python when available; falls back to sys.executable.

Usage:
    adapter = CVAdapter(callback_cv_path=Path("../callback-cv"))
    pdf_path = await adapter.generate_pdf(Path("vacancies/djinni/2026-05/job/Name_CV.md"))
"""

import asyncio
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)


class CVAdapterError(Exception):
    """Raised when cv_to_pdf subprocess fails."""


class CVAdapter:
    """Async wrapper for cv_to_pdf.py subprocess.

    Args:
        callback_cv_path: Path to the callback-cv repo root.
    """

    def __init__(self, callback_cv_path: Path) -> None:
        self._cv_path = Path(callback_cv_path)
        self._script = self._cv_path / "cv_to_pdf.py"
        self._python = self._resolve_python()

    def _resolve_python(self) -> str:
        """Find the Python executable to use for cv_to_pdf.py.

        Prefer callback-cv venv (has fpdf); fall back to current interpreter.
        """
        win = self._cv_path / "venv" / "Scripts" / "python.exe"
        unix = self._cv_path / "venv" / "bin" / "python"
        if win.exists():
            return str(win)
        if unix.exists():
            return str(unix)
        log.warning(
            "CVAdapter: venv not found at %s — using %s (fpdf may be missing)",
            self._cv_path / "venv",
            sys.executable,
        )
        return sys.executable

    async def generate_pdf(self, md_path: Path, pdf_path: Path | None = None) -> Path:
        """Generate PDF from a CV markdown file.

        Runs: `python cv_to_pdf.py <md_path> <pdf_path>`

        Args:
            md_path:  Path to the input CV markdown file.
            pdf_path: Output PDF path. Defaults to md_path with .pdf extension.

        Returns:
            Path to the generated PDF file.

        Raises:
            CVAdapterError: Subprocess failed or PDF not created.
            FileNotFoundError: cv_to_pdf.py script not found.
        """
        md_path = Path(md_path)
        if pdf_path is None:
            pdf_path = md_path.with_suffix(".pdf")

        if not self._script.exists():
            raise FileNotFoundError(f"cv_to_pdf.py not found at {self._script}")

        log.info("CVAdapter: generating PDF %s → %s", md_path, pdf_path)

        try:
            proc = await asyncio.create_subprocess_exec(
                self._python,
                str(self._script),
                str(md_path),
                str(pdf_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError as exc:
            raise CVAdapterError("cv_to_pdf.py timed out after 30s") from exc
        except OSError as exc:
            raise CVAdapterError(f"Failed to start subprocess: {exc}") from exc

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            raise CVAdapterError(
                f"cv_to_pdf.py exited {proc.returncode}: {err}"
            )

        if not pdf_path.exists():
            raise CVAdapterError(
                f"cv_to_pdf.py exited 0 but PDF not found at {pdf_path}"
            )

        log.info("CVAdapter: PDF generated → %s", pdf_path)
        return pdf_path
