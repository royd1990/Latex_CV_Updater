"""Generate .tex files from CV data models using Jinja2 templates."""

from __future__ import annotations

import re
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


_ALL_SECTIONS = ["employment", "education", "skills", "misc", "referee"]

_SUPPORT_FILES = ["settings.sty", "own-bib.bib", "photo.jpg"]


def copy_support_files(source_dir: Path, dest_dir: Path) -> list[str]:
    """Copy required LaTeX support files from source to dest if missing. Returns list of copied filenames."""
    copied = []
    for filename in _SUPPORT_FILES:
        src = source_dir / filename
        dst = dest_dir / filename
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            copied.append(filename)
    return copied


def _insert_custom_makerubrics(main_tex: Path, custom_sections: list) -> None:
    """Insert \makerubric{} lines for custom sections before \end{document}."""
    if not main_tex.exists() or not custom_sections:
        return
    content = main_tex.read_text()
    for section in custom_sections:
        rubric_line = f"\\makerubric{{{section.filename}}}"
        if rubric_line not in content:
            content = content.replace("\\end{document}", f"{rubric_line}\n\\end{{document}}")
    main_tex.write_text(content)


def _update_makerubric_lines(main_tex: Path, skipped_sections: set) -> None:
    """Comment out \makerubric{} for skipped sections, uncomment for active ones."""
    if not main_tex.exists():
        return
    content = main_tex.read_text()
    for section in _ALL_SECTIONS:
        if section in skipped_sections:
            # Comment out active line
            content = re.sub(
                rf'^(\\makerubric\{{{section}\}})',
                r'% \1',
                content, flags=re.MULTILINE,
            )
        else:
            # Uncomment if previously commented out
            content = re.sub(
                rf'^%\s*(\\makerubric\{{{section}\}})',
                r'\1',
                content, flags=re.MULTILINE,
            )
    main_tex.write_text(content)


def generate_cv(data: CVData, output_dir: Path) -> list[Path]:
    """Generate all .tex files from CV data. Returns list of generated file paths."""
    env = _get_env()
    generated = []

    files_to_generate = [
        ("employment", "employment.tex.j2", "employment.tex", {"entries": data.employment}),
        ("education", "education.tex.j2", "education.tex", {"entries": data.education}),
        ("skills", "skills.tex.j2", "skills.tex", {"entries": data.skills}),
        ("misc", "misc.tex.j2", "misc.tex", {"entries": data.misc}),
        ("referee", "referee.tex.j2", "referee.tex", {
            "mode": data.referee_mode,
            "referees": data.referees,
        }),
    ]

    for section_key, template_name, output_name, context in files_to_generate:
        if section_key in data.skipped_sections:
            continue
        output_path = output_dir / output_name
        _backup(output_path)
        template = env.get_template(template_name)
        content = template.render(**context)
        output_path.write_text(content)
        generated.append(output_path)

    # Generate custom sections
    custom_template = env.get_template("custom_section.tex.j2")
    for section in data.custom_sections:
        output_path = output_dir / f"{section.filename}.tex"
        _backup(output_path)
        content = custom_template.render(section_title=section.title, entries=section.entries)
        output_path.write_text(content)
        generated.append(output_path)

    _update_makerubric_lines(output_dir / "cv-llt.tex", data.skipped_sections)
    _insert_custom_makerubrics(output_dir / "cv-llt.tex", data.custom_sections)

    return generated


def _compute_mynames(name: str) -> str:
    """Convert a full name like 'John Doe, Ph.D.' to biblatex format 'Doe/John'."""
    # Strip suffixes after comma (e.g. ", Ph.D.", ", Jr.")
    base = name.split(",")[0].strip()
    parts = base.split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    last = parts[-1]
    first = " ".join(parts[:-1])
    return f"{last}/{first}"


def generate_main(data: CVData, output_dir: Path) -> Path:
    """Generate the main cv-llt.tex file."""
    env = _get_env()
    output_path = output_dir / "cv-llt.tex"
    _backup(output_path)
    template = env.get_template("cv_main.tex.j2")
    content = template.render(
        personal=data.personal,
        skipped_sections=data.skipped_sections,
        custom_sections=data.custom_sections,
        mynames=_compute_mynames(data.personal.name),
    )
    output_path.write_text(content)
    return output_path
