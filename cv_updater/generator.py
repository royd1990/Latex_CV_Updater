"""Generate .tex files from CV data models using Jinja2 templates."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .models import CVData

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _get_env() -> Environment:
    """Create Jinja2 environment with LaTeX-friendly settings."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        block_start_string="<%",
        block_end_string="%>",
        variable_start_string="<<",
        variable_end_string=">>",
        comment_start_string="<#",
        comment_end_string="#>",
        keep_trailing_newline=True,
    )
    return env


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in user input."""
    if not text:
        return text
    # Don't escape if the text already contains LaTeX commands
    if "\\" in text and any(cmd in text for cmd in ["\\textbf", "\\emph", "\\par", "\\cdots"]):
        return text
    replacements = [
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _backup(filepath: Path) -> None:
    """Create a .bak backup of a file if it exists."""
    if filepath.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = filepath.with_suffix(f".tex.bak.{timestamp}")
        shutil.copy2(filepath, backup_path)


def generate_cv(data: CVData, output_dir: Path) -> list[Path]:
    """Generate all .tex files from CV data. Returns list of generated file paths."""
    env = _get_env()
    generated = []

    files_to_generate = [
        ("employment.tex.j2", "employment.tex", {"entries": data.employment}),
        ("education.tex.j2", "education.tex", {"entries": data.education}),
        ("skills.tex.j2", "skills.tex", {"entries": data.skills}),
        ("misc.tex.j2", "misc.tex", {"entries": data.misc}),
        ("referee.tex.j2", "referee.tex", {
            "mode": data.referee_mode,
            "referees": data.referees,
        }),
    ]

    for template_name, output_name, context in files_to_generate:
        output_path = output_dir / output_name
        _backup(output_path)
        template = env.get_template(template_name)
        content = template.render(**context)
        output_path.write_text(content)
        generated.append(output_path)

    return generated


def generate_main(data: CVData, output_dir: Path) -> Path:
    """Generate the main cv-llt.tex file."""
    env = _get_env()
    output_path = output_dir / "cv-llt.tex"
    _backup(output_path)
    template = env.get_template("cv_main.tex.j2")
    content = template.render(personal=data.personal)
    output_path.write_text(content)
    return output_path
