"""Generate .tex files from CV data models using Jinja2 templates."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .models import CVData

TEMPLATES_DIR = Path(__file__).parent / "templates"
COMPACT_TEMPLATES_DIR = TEMPLATES_DIR / "compact"


def _get_env(template_style: str = "standard") -> Environment:
    """Create Jinja2 environment with LaTeX-friendly settings.

    When template_style is 'compact', the compact/ subdirectory is searched
    first, falling back to the standard templates directory.
    """
    if template_style == "compact":
        search_path = [str(COMPACT_TEMPLATES_DIR), str(TEMPLATES_DIR)]
    else:
        search_path = [str(TEMPLATES_DIR)]
    env = Environment(
        loader=FileSystemLoader(search_path),
        block_start_string="<%",
        block_end_string="%>",
        variable_start_string="<<",
        variable_end_string=">>",
        comment_start_string="<#",
        comment_end_string="#>",
        keep_trailing_newline=True,
    )
    env.filters["escape_latex"] = escape_latex
    return env


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters, avoiding double-escaping.

    Handles both fresh user input and content parsed from existing .tex files
    that may already contain LaTeX commands or escaped characters.
    """
    if not text:
        return text
    # Replace each special character only when NOT already preceded by a backslash.
    # Uses a negative lookbehind (?<!\\) to skip already-escaped characters.
    for char, replacement in [
        ("&", r"\&"),
        ("%", r"\%"),
        (r"$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
    ]:
        text = re.sub(r"(?<!\\)" + re.escape(char), replacement, text)
    # Only escape braces if the text contains no LaTeX commands.
    # Content with commands like \textbf{...} or \begin{...} needs braces intact.
    if not re.search(r"\\[a-zA-Z]", text):
        text = re.sub(r"(?<!\\)\{", r"\\{", text)
        text = re.sub(r"(?<!\\)\}", r"\\}", text)
        text = text.replace("~", r"\textasciitilde{}")
        text = text.replace("^", r"\textasciicircum{}")
    return text


def _backup(filepath: Path) -> None:
    """Create a .bak backup of a file if it exists."""
    if filepath.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = filepath.with_suffix(f".tex.bak.{timestamp}")
        shutil.copy2(filepath, backup_path)


_ALL_SECTIONS = ["about", "employment", "education", "skills", "project_highlights", "misc", "referee"]

_SUPPORT_FILES = ["settings.sty", "own-bib.bib"]


def copy_support_files(source_dir: Path, dest_dir: Path, template_style: str = "standard") -> list[str]:
    """Copy required LaTeX support files from source to dest if missing. Returns list of copied filenames.

    When template_style is 'compact', the compact settings.sty is used instead of the standard one.
    """
    copied = []
    for filename in _SUPPORT_FILES:
        dst = dest_dir / filename
        if dst.exists():
            continue
        # For settings.sty, prefer the compact version when appropriate
        if filename == "settings.sty" and template_style == "compact":
            compact_src = COMPACT_TEMPLATES_DIR / "settings.sty"
            if compact_src.exists():
                shutil.copy2(compact_src, dst)
                copied.append(filename)
                continue
        src = source_dir / filename
        if src.exists():
            shutil.copy2(src, dst)
            copied.append(filename)
    # Copy any image files (jpg, png) for photo
    for pattern in ["*.jpg", "*.jpeg", "*.png"]:
        for src in source_dir.glob(pattern):
            dst = dest_dir / src.name
            if src.exists() and not dst.exists():
                shutil.copy2(src, dst)
                copied.append(src.name)
    return copied


def copy_photo_file(photo_path: Path, dest_dir: Path) -> str:
    """Copy a photo file to the destination directory. Returns the stem (filename without extension)."""
    if not photo_path.exists():
        return ""
    dst = dest_dir / photo_path.name
    if not dst.exists():
        shutil.copy2(photo_path, dst)
    return photo_path.stem


def _copy_compact_settings(output_dir: Path) -> None:
    """Copy the compact settings.sty to the output directory, overwriting any existing one."""
    src = COMPACT_TEMPLATES_DIR / "settings.sty"
    if src.exists():
        shutil.copy2(src, output_dir / "settings.sty")


def generate_cv(data: CVData, output_dir: Path) -> list[Path]:
    """Generate all .tex files from CV data. Returns list of generated file paths."""
    env = _get_env(data.template_style)
    generated = []

    files_to_generate = [
        ("about", "about.tex.j2", "about.tex", {"about_text": data.about}),
        ("employment", "employment.tex.j2", "employment.tex", {"entries": data.employment}),
        ("education", "education.tex.j2", "education.tex", {"entries": data.education}),
        ("skills", "skills.tex.j2", "skills.tex", {"entries": data.skills}),
        ("project_highlights", "project_highlights.tex.j2", "project_highlights.tex", {
            "entries": data.project_highlights,
        }),
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


def _build_section_order(data: CVData) -> list[str]:
    """Return the effective section order, ensuring all custom sections are included."""
    order = list(data.section_order)
    # Append any custom sections that aren't already in the order
    for section in data.custom_sections:
        if section.filename not in order:
            order.append(section.filename)
    return order


def generate_main(data: CVData, output_dir: Path) -> Path:
    """Generate the main cv-llt.tex file."""
    env = _get_env(data.template_style)

    # When using compact template, ensure the compact settings.sty is in place
    if data.template_style == "compact":
        _copy_compact_settings(output_dir)
    output_path = output_dir / "cv-llt.tex"
    _backup(output_path)
    template = env.get_template("cv_main.tex.j2")
    section_order = _build_section_order(data)
    content = template.render(
        personal=data.personal,
        skipped_sections=data.skipped_sections,
        custom_sections=data.custom_sections,
        section_order=section_order,
        mynames=_compute_mynames(data.personal.name),
        prefix_marker=data.prefix_marker,
    )
    output_path.write_text(content)
    return output_path
