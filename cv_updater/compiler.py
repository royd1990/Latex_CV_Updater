"""LaTeX compilation orchestration."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def detect_engine() -> str | None:
    """Detect available LaTeX engine. Prefers xelatex > lualatex > pdflatex."""
    for engine in ("xelatex", "lualatex", "pdflatex"):
        if shutil.which(engine):
            return engine
    return None


def detect_biber() -> bool:
    """Check if biber is available."""
    return shutil.which("biber") is not None


def check_prerequisites() -> list[str]:
    """Check for required tools and return list of issues."""
    issues = []
    engine = detect_engine()
    if engine is None:
        issues.append(
            "No LaTeX engine found (xelatex, lualatex, or pdflatex).\n"
            "Install MacTeX: brew install --cask mactex\n"
            "Or install BasicTeX: brew install --cask basictex"
        )
    if not detect_biber():
        issues.append(
            "biber not found (needed for bibliography).\n"
            "It is included with MacTeX. For BasicTeX: sudo tlmgr install biber biblatex"
        )
    return issues


def compile_cv(tex_path: Path, engine: str | None = None) -> tuple[bool, str]:
    """Compile a .tex file to PDF.

    Runs: engine → biber → engine → engine

    Returns (success, message).
    """
    if engine is None:
        engine = detect_engine()
    if engine is None:
        return False, (
            "No LaTeX engine found.\n"
            "Install MacTeX: brew install --cask mactex"
        )

    tex_dir = tex_path.parent
    tex_name = tex_path.stem

    def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            cwd=str(tex_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )

    engine_cmd = [engine, "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
    biber_cmd = ["biber", tex_name]

    steps = [
        (engine_cmd, f"{engine} (pass 1)"),
        (biber_cmd, "biber"),
        (engine_cmd, f"{engine} (pass 2)"),
        (engine_cmd, f"{engine} (pass 3)"),
    ]

    for cmd, step_name in steps:
        # Skip biber if not available
        if cmd[0] == "biber" and not detect_biber():
            continue
        try:
            result = run_cmd(cmd)
        except subprocess.TimeoutExpired:
            return False, f"Timeout during {step_name}"
        except FileNotFoundError:
            return False, f"Command not found: {cmd[0]}"

        if result.returncode != 0:
            error_msg = _parse_log_error(tex_dir / f"{tex_name}.log")
            if not error_msg:
                error_msg = result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
            return False, f"Failed at {step_name}:\n{error_msg}"

    pdf_path = tex_dir / f"{tex_name}.pdf"
    if pdf_path.exists():
        return True, f"PDF generated: {pdf_path}"
    return False, "Compilation completed but no PDF was generated."


def _parse_log_error(log_path: Path) -> str:
    """Extract the first error from a .log file."""
    if not log_path.exists():
        return ""
    try:
        content = log_path.read_text(errors="replace")
    except Exception:
        return ""

    # Find first error line
    error_match = re.search(r"^!(.*?)(?=^!|\Z)", content, re.MULTILINE | re.DOTALL)
    if error_match:
        error_text = error_match.group(0).strip()
        # Limit to first few lines
        lines = error_text.split("\n")[:10]
        return "\n".join(lines)
    return ""
