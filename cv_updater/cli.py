"""Interactive CLI for creating and updating LaTeX CVs."""

from __future__ import annotations

import sys
from pathlib import Path

import questionary
from questionary import Style as QStyle
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from .compiler import check_prerequisites, compile_cv
from .generator import copy_support_files, escape_latex, generate_cv, generate_main
from .models import (
    CVData,
    CustomEntry,
    CustomSection,
    EducationEntry,
    EmploymentEntry,
    MiscEntry,
    PersonalInfo,
    RefereeEntry,
    SkillCategory,
)
from .parser import PRESENT_MARKER, parse_cv

DEFAULT_CV_DIR = Path(__file__).parent.parent / "Deba_CV"

# ─── Theme ────────────────────────────────────────────────────────────────────

_THEME = Theme(
    {
        "primary": "bold #7aa2f7",
        "secondary": "#9ece6a",
        "accent": "#e0af68",
        "muted": "#565f89",
        "success": "bold #9ece6a",
        "warning": "bold #e0af68",
        "error": "bold #f7768e",
        "info": "#7dcfff",
        "header": "bold #bb9af7",
        "dim_text": "#a9b1d6",
        "border": "#3b4261",
    }
)

console = Console(theme=_THEME, highlight=False)

_Q_STYLE = QStyle(
    [
        ("qmark", "fg:#7aa2f7 bold"),
        ("question", "fg:#c0caf5 bold"),
        ("answer", "fg:#9ece6a bold"),
        ("pointer", "fg:#7aa2f7 bold"),
        ("highlighted", "fg:#7aa2f7 bold"),
        ("selected", "fg:#9ece6a"),
        ("separator", "fg:#565f89"),
        ("instruction", "fg:#565f89 italic"),
        ("text", "fg:#c0caf5"),
        ("disabled", "fg:#565f89 italic"),
    ]
)


def _ask(fn, *args, **kwargs):
    """Run a questionary prompt with the app style."""
    kwargs.setdefault("style", _Q_STYLE)
    return fn(*args, **kwargs).ask()


# ─── Display helpers ──────────────────────────────────────────────────────────


def _banner() -> None:
    title = Text()
    title.append("LaTeX ", style="bold #7aa2f7")
    title.append("CV", style="bold #bb9af7")
    title.append(" Updater", style="bold #7aa2f7")
    subtitle = Text(
        "Interactive editor for the curve document class",
        style="#565f89",
        justify="center",
    )
    console.print(
        Panel(
            Text.assemble(title, "\n", subtitle, justify="center"),
            box=box.DOUBLE_EDGE,
            border_style="border",
            padding=(1, 6),
        )
    )
    console.print()


def _section_rule(title: str, count: int | None = None) -> None:
    label = Text(f" {title.upper()} ", style="header")
    if count is not None:
        label.append(
            f"· {count} {'entry' if count == 1 else 'entries'} ",
            style="muted",
        )
    console.print(Rule(title=label, style="border"))


def _ok(msg: str) -> None:
    console.print(f"  [success]✓[/success]  [dim_text]{msg}[/dim_text]")


def _warn(msg: str) -> None:
    console.print(f"  [warning]![/warning]  [dim_text]{msg}[/dim_text]")


def _info(msg: str) -> None:
    console.print(f"  [info]→[/info]  [dim_text]{msg}[/dim_text]")


def _err(msg: str) -> None:
    console.print(f"  [error]✗[/error]  [dim_text]{msg}[/dim_text]")


def _display_personal(p: PersonalInfo) -> None:
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), border_style="border")
    table.add_column("Field", style="accent", min_width=12)
    table.add_column("Value", style="dim_text")
    table.add_row("Name", p.name or "(not set)")
    table.add_row("Email", p.email or "(not set)")
    table.add_row("LinkedIn", p.linkedin or "(not set)")
    table.add_row("Website", p.github or "(not set)")
    console.print(table)


def _display_entries(section_name: str, entries: list) -> None:
    if not entries:
        console.print("  [muted](no entries)[/muted]")
        console.print()
        return
    console.print(_build_entry_table(section_name, entries))
    console.print()


def _build_entry_table(section_name: str, entries: list) -> Table:
    table = Table(
        box=box.ROUNDED,
        border_style="border",
        header_style="bold #7aa2f7",
        show_edge=True,
        padding=(0, 1),
    )
    if section_name == "Employment":
        table.add_column("#", style="muted", width=3, justify="right")
        table.add_column("Period", style="accent", min_width=14)
        table.add_column("Position", style="dim_text")
        table.add_column("Organisation", style="secondary")
        for i, e in enumerate(entries, 1):
            table.add_row(str(i), e.date_range, e.title, e.organization)
    elif section_name == "Education":
        table.add_column("#", style="muted", width=3, justify="right")
        table.add_column("Period", style="accent", min_width=14)
        table.add_column("Degree", style="dim_text")
        table.add_column("Institution", style="secondary")
        for i, e in enumerate(entries, 1):
            table.add_row(str(i), e.date_range, e.degree, e.institution)
    elif section_name == "Skills":
        table.add_column("#", style="muted", width=3, justify="right")
        table.add_column("Category", style="accent", min_width=16)
        table.add_column("Items", style="dim_text")
        for i, e in enumerate(entries, 1):
            table.add_row(str(i), e.label, e.items[:90])
    elif section_name == "Miscellaneous":
        table.add_column("#", style="muted", width=3, justify="right")
        table.add_column("Year", style="accent", min_width=6)
        table.add_column("Sub-section", style="info", min_width=18)
        table.add_column("Title", style="dim_text")
        for i, e in enumerate(entries, 1):
            table.add_row(str(i), e.year, e.subrubric, e.title)
    else:
        table.add_column("#", style="muted", width=3, justify="right")
        table.add_column("Label", style="accent", min_width=14)
        table.add_column("Content", style="dim_text")
        for i, e in enumerate(entries, 1):
            table.add_row(str(i), e.label, e.content[:90])
    return table


# ─── Entry summary (one-liner used in pick lists) ─────────────────────────────


def _entry_summary(entry) -> str:
    if isinstance(entry, EmploymentEntry):
        return f"[{entry.date_range}]  {entry.title} · {entry.organization}"
    elif isinstance(entry, EducationEntry):
        return f"[{entry.date_range}]  {entry.degree} · {entry.institution}"
    elif isinstance(entry, SkillCategory):
        preview = entry.items[:55] + ("…" if len(entry.items) > 55 else "")
        return f"[{entry.label}]  {preview}"
    elif isinstance(entry, MiscEntry):
        return f"[{entry.year}]  {entry.title}  ({entry.subrubric})"
    elif isinstance(entry, CustomEntry):
        preview = entry.content[:55] + ("…" if len(entry.content) > 55 else "")
        return f"[{entry.label}]  {preview}"
    return str(entry)


def _pick_entry_index(entries: list) -> int | None:
    choices = [f"{i+1}.  {_entry_summary(e)}" for i, e in enumerate(entries)]
    choice = _ask(questionary.select, "Select entry:", choices=choices)
    if choice is None:
        return None
    return int(choice.split(".")[0]) - 1


# ─── Main entry point ─────────────────────────────────────────────────────────


def main() -> None:
    _banner()

    issues = check_prerequisites()
    if issues:
        console.print(
            Panel(
                "\n".join(f"  [warning]![/warning] {i}" for i in issues),
                title="[warning]Missing Prerequisites[/warning]",
                border_style="warning",
                padding=(0, 1),
            )
        )
        console.print()

    cv_dir = _ask_cv_directory()

    mode = _ask(
        questionary.select,
        "What would you like to do?",
        choices=["Update existing CV", "Create new CV"],
    )
    if mode is None:
        _info("Cancelled.")
        return

    console.print()

    if mode == "Update existing CV":
        data = _update_mode(cv_dir)
    else:
        data = _create_mode()

    if data is None:
        _info("Cancelled.")
        return

    # Generate files
    console.print()
    _section_rule("Generating Files")
    generated = generate_cv(data, cv_dir)
    for f in generated:
        _ok(f"Written  {f.name}")

    if mode == "Create new CV":
        main_file = generate_main(data, cv_dir)
        _ok(f"Written  {main_file.name}")
        copied = copy_support_files(DEFAULT_CV_DIR, cv_dir)
        for f in copied:
            _ok(f"Copied   {f}")

    console.print()

    if _ask(questionary.confirm, "Compile to PDF now?", default=True):
        tex_path = cv_dir / "cv-llt.tex"
        if not tex_path.exists():
            _err(f"Main file not found: {tex_path}")
            return
        _info("Compiling — this may take a moment…")
        console.print()
        success, message = compile_cv(tex_path)
        if success:
            _ok(message)
        else:
            console.print(
                Panel(
                    message,
                    title="[error]Compilation Failed[/error]",
                    border_style="error",
                    padding=(0, 1),
                )
            )
    else:
        _info("Skipping compilation.  Run manually:")
        console.print(
            f"  [muted]cd {cv_dir} && xelatex cv-llt.tex && biber cv-llt && xelatex cv-llt.tex && xelatex cv-llt.tex[/muted]"
        )

    console.print()
    console.print(Rule(style="border"))
    console.print(Text("  Done!", style="success"))
    console.print()


def _ask_cv_directory() -> Path:
    default = str(DEFAULT_CV_DIR)
    path_str = _ask(questionary.text, "CV directory path:", default=default)
    if path_str is None:
        sys.exit(0)
    path = Path(path_str).resolve()
    if not path.exists():
        if _ask(questionary.confirm, f"Directory {path} does not exist.  Create it?", default=True):
            path.mkdir(parents=True, exist_ok=True)
        else:
            sys.exit(0)
    return path


# ─── Update mode ──────────────────────────────────────────────────────────────

_SECTION_KEYS = {
    "Employment": "employment",
    "Education": "education",
    "Skills": "skills",
    "Miscellaneous": "misc",
}

_SECTION_ACTIONS = [
    "Keep as is",
    "Add entry",
    "Edit entry",
    "Remove entry",
    "Skip section",
    "Go back",
]


def _edit_personal_info(existing: PersonalInfo) -> PersonalInfo | None:
    name = _ask(questionary.text, "Full name:", default=existing.name)
    if name is None:
        return None
    email = _ask(questionary.text, "Email:", default=existing.email)
    if email is None:
        return None
    linkedin = _ask(questionary.text, "LinkedIn URL (optional):", default=existing.linkedin)
    if linkedin is None:
        return None
    linkedin_label = existing.linkedin_label
    if linkedin:
        linkedin_label = (
            _ask(
                questionary.text,
                "LinkedIn display label:",
                default=existing.linkedin_label or linkedin.rstrip("/").split("/")[-1],
            )
            or ""
        )
    github = _ask(questionary.text, "Website / GitHub URL (optional):", default=existing.github)
    if github is None:
        return None
    photo = _ask(questionary.text, "Photo filename (without extension):", default=existing.photo or "photo")
    if photo is None:
        return None
    return PersonalInfo(
        name=name,
        email=email,
        linkedin=linkedin,
        linkedin_label=linkedin_label,
        github=github,
        photo=photo,
    )


def _update_mode(cv_dir: Path) -> CVData | None:
    _info("Parsing existing CV files…")
    data = parse_cv(cv_dir)
    console.print()

    # Personal info
    _section_rule("Personal Info")
    _display_personal(data.personal)
    if _ask(questionary.confirm, "Edit personal info?", default=False):
        updated = _edit_personal_info(data.personal)
        if updated is None:
            return None
        data.personal = updated

    sections = [
        ("Employment", data.employment, _edit_employment_entries),
        ("Education", data.education, _edit_education_entries),
        ("Skills", data.skills, _edit_skill_entries),
        ("Miscellaneous", data.misc, _edit_misc_entries),
    ]

    i = 0
    while i < len(sections):
        section_name, entries, edit_fn = sections[i]
        console.print()
        _section_rule(section_name, len(entries))
        _display_entries(section_name, entries)

        action = _ask(
            questionary.select,
            f"What would you like to do with {section_name}?",
            choices=_SECTION_ACTIONS,
        )
        if action is None:
            return None

        if action == "Go back":
            if i == 0:
                console.print()
                _section_rule("Personal Info")
                _display_personal(data.personal)
                if _ask(questionary.confirm, "Edit personal info?", default=False):
                    updated = _edit_personal_info(data.personal)
                    if updated is None:
                        return None
                    data.personal = updated
            else:
                i -= 1
            continue

        if action == "Skip section":
            data.skipped_sections.add(_SECTION_KEYS[section_name])
        elif action == "Keep as is":
            data.skipped_sections.discard(_SECTION_KEYS[section_name])
        elif action == "Add entry":
            new_entry = edit_fn(None)
            if new_entry:
                entries.insert(0, new_entry)
                _ok("Entry added.")
        elif action == "Edit entry":
            if not entries:
                _warn("No entries to edit.")
            else:
                idx = _pick_entry_index(entries)
                if idx is not None:
                    edited = edit_fn(entries[idx])
                    if edited:
                        entries[idx] = edited
                        _ok("Entry updated.")
        elif action == "Remove entry":
            if not entries:
                _warn("No entries to remove.")
            else:
                idx = _pick_entry_index(entries)
                if idx is not None:
                    entries.pop(idx)
                    _ok("Entry removed.")

        i += 1

    # Referee section
    console.print()
    _section_rule("Referees")
    while True:
        ref_mode = _ask(
            questionary.select,
            "Referee section:",
            choices=["Available on Request", "List referees", "Skip section", "Go back"],
        )
        if ref_mode == "Go back":
            last_name, last_entries, last_fn = sections[-1]
            console.print()
            _section_rule(last_name, len(last_entries))
            _display_entries(last_name, last_entries)
            action = _ask(
                questionary.select,
                f"What would you like to do with {last_name}?",
                choices=["Keep as is", "Add entry", "Edit entry", "Remove entry", "Skip section"],
            )
            if action is None:
                return None
            if action == "Add entry":
                new_entry = last_fn(None)
                if new_entry:
                    last_entries.insert(0, new_entry)
                    _ok("Entry added.")
            elif action == "Edit entry":
                if not last_entries:
                    _warn("No entries to edit.")
                else:
                    idx = _pick_entry_index(last_entries)
                    if idx is not None:
                        edited = last_fn(last_entries[idx])
                        if edited:
                            last_entries[idx] = edited
                            _ok("Entry updated.")
            elif action == "Remove entry":
                if not last_entries:
                    _warn("No entries to remove.")
                else:
                    idx = _pick_entry_index(last_entries)
                    if idx is not None:
                        last_entries.pop(idx)
                        _ok("Entry removed.")
            console.print()
            _section_rule("Referees")
            continue

        if ref_mode == "List referees":
            data.referee_mode = "full"
            data.skipped_sections.discard("referee")
            if not data.referees:
                _info("No referees found.  Add them:")
                while True:
                    ref = _collect_referee()
                    if ref:
                        data.referees.append(ref)
                    if not _ask(questionary.confirm, "Add another referee?", default=False):
                        break
        elif ref_mode == "Skip section":
            data.skipped_sections.add("referee")
        else:
            data.referee_mode = "short"
            data.skipped_sections.discard("referee")
        break

    # Custom sections
    console.print()
    if _ask(questionary.confirm, "Add custom sections (e.g. Publications, Awards)?", default=False):
        _manage_custom_sections(data)

    return data


# ─── Entry editors ────────────────────────────────────────────────────────────


def _edit_employment_entries(existing: EmploymentEntry | None) -> EmploymentEntry | None:
    defaults = existing or EmploymentEntry("", "", "", "", "")

    start = _ask(questionary.text, "Start year:", default=defaults.start_year)
    if start is None:
        return None

    is_current = _ask(
        questionary.confirm,
        "Is this your current position?",
        default=(defaults.end_year == PRESENT_MARKER),
    )
    end = PRESENT_MARKER if is_current else _ask(questionary.text, "End year:", default=defaults.end_year)
    if end is None:
        return None

    title = _ask(questionary.text, "Job title:", default=defaults.title)
    org = _ask(questionary.text, "Organisation:", default=defaults.organization)
    location = _ask(questionary.text, "Location:", default=defaults.location)

    if any(v is None for v in [title, org, location]):
        return None

    return EmploymentEntry(
        start_year=start,
        end_year=end,
        title=escape_latex(title),
        organization=escape_latex(org),
        location=escape_latex(location),
    )


def _edit_education_entries(existing: EducationEntry | None) -> EducationEntry | None:
    defaults = existing or EducationEntry("", "", "", "", "", "")

    start = _ask(questionary.text, "Start year:", default=defaults.start_year)
    end = _ask(questionary.text, "End year:", default=defaults.end_year)
    degree = _ask(questionary.text, "Degree:", default=defaults.degree)
    institution = _ask(questionary.text, "Institution:", default=defaults.institution)
    specialization = _ask(questionary.text, "Specialization (optional):", default=defaults.specialization)
    thesis = _ask(questionary.text, "Thesis title (optional):", default=defaults.thesis_title)

    if any(v is None for v in [start, end, degree, institution]):
        return None

    return EducationEntry(
        start_year=start,
        end_year=end,
        degree=escape_latex(degree),
        institution=escape_latex(institution),
        specialization=escape_latex(specialization or ""),
        thesis_title=escape_latex(thesis or ""),
    )


def _edit_skill_entries(existing: SkillCategory | None) -> SkillCategory | None:
    defaults = existing or SkillCategory("", "")

    label = _ask(questionary.text, "Category label:", default=defaults.label)
    items = _ask(questionary.text, "Skills (comma-separated):", default=defaults.items)

    if any(v is None for v in [label, items]):
        return None

    return SkillCategory(label=escape_latex(label), items=escape_latex(items))


def _edit_misc_entries(existing: MiscEntry | None) -> MiscEntry | None:
    defaults = existing or MiscEntry("", "", "", "")

    subrubric = _ask(
        questionary.text,
        "Sub-section (e.g. Awards and Achievements):",
        default=defaults.subrubric,
    )
    year = _ask(questionary.text, "Year:", default=defaults.year)
    title = _ask(questionary.text, "Title:", default=defaults.title)
    description = _ask(questionary.text, "Description:", default=defaults.description)

    if any(v is None for v in [year, title]):
        return None

    return MiscEntry(
        year=year,
        title=escape_latex(title),
        description=escape_latex(description or ""),
        subrubric=escape_latex(subrubric or ""),
    )


def _collect_referee() -> RefereeEntry | None:
    name = _ask(questionary.text, "Referee name:")
    title = _ask(questionary.text, "Title (e.g. Professor):")
    institution = _ask(questionary.text, "Institution:")
    address = _ask(questionary.text, "Address (optional):")
    email = _ask(questionary.text, "Email:")

    if any(v is None for v in [name, title, institution, email]):
        return None

    return RefereeEntry(
        name=escape_latex(name),
        title=escape_latex(title),
        institution=escape_latex(institution),
        address=escape_latex(address or ""),
        email=email,
    )


# ─── Custom sections ──────────────────────────────────────────────────────────

import re as _re


def _sanitize_filename(title: str) -> str:
    slug = title.lower().strip()
    slug = _re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_") or "custom_section"


def _edit_custom_entry(existing: CustomEntry | None) -> CustomEntry | None:
    defaults = existing or CustomEntry("", "")

    subrubric = _ask(
        questionary.text,
        "Sub-section header (leave blank for none):",
        default=defaults.subrubric,
    )
    if subrubric is None:
        return None

    label = _ask(questionary.text, "Left-column label (e.g. year, date range):", default=defaults.label)
    if label is None:
        return None

    content = _ask(questionary.text, "Entry content (LaTeX allowed):", default=defaults.content)
    if content is None:
        return None

    return CustomEntry(
        label=escape_latex(label) if "\\" not in label else label,
        content=content,
        subrubric=escape_latex(subrubric) if subrubric and "\\" not in subrubric else subrubric,
    )


def _edit_custom_section(existing: CustomSection | None) -> CustomSection | None:
    default_title = existing.title if existing else ""
    title = _ask(questionary.text, "Section title (e.g. Publications, Awards):", default=default_title)
    if not title:
        return None

    default_filename = existing.filename if existing else _sanitize_filename(title)
    filename = _ask(questionary.text, "Output filename (without .tex):", default=default_filename)
    if not filename:
        return None

    section = CustomSection(
        title=escape_latex(title) if "\\" not in title else title,
        filename=filename,
    )
    if existing:
        section.entries = list(existing.entries)

    _info(f"Adding entries to '{title}':")
    while True:
        action = _ask(
            questionary.select,
            "Entry action:",
            choices=["Add entry", "Done adding entries"],
        )
        if action is None or action == "Done adding entries":
            break
        entry = _edit_custom_entry(None)
        if entry:
            section.entries.append(entry)

    return section


def _manage_custom_sections(data: CVData) -> None:
    while True:
        console.print()
        _section_rule("Custom Sections", len(data.custom_sections))
        for i, s in enumerate(data.custom_sections, 1):
            console.print(
                f"  [muted]{i}.[/muted]  [accent]{s.title!r}[/accent]  "
                f"[muted]→[/muted]  [dim_text]{s.filename}.tex[/dim_text]  "
                f"[muted]({len(s.entries)} entries)[/muted]"
            )
        if data.custom_sections:
            console.print()

        base = ["Add new custom section", "Done"]
        if data.custom_sections:
            base = ["Add new custom section", "Edit custom section", "Remove custom section", "Done"]

        action = _ask(questionary.select, "Custom sections:", choices=base)
        if action is None or action == "Done":
            break
        elif action == "Add new custom section":
            section = _edit_custom_section(None)
            if section:
                data.custom_sections.append(section)
                _ok(f"Section '{section.title}' added.")
        elif action == "Edit custom section":
            names = [f"{i+1}.  {s.title}" for i, s in enumerate(data.custom_sections)]
            pick = _ask(questionary.select, "Select section to edit:", choices=names)
            if pick:
                idx = int(pick.split(".")[0]) - 1
                edited = _edit_custom_section(data.custom_sections[idx])
                if edited:
                    data.custom_sections[idx] = edited
                    _ok("Section updated.")
        elif action == "Remove custom section":
            names = [f"{i+1}.  {s.title}" for i, s in enumerate(data.custom_sections)]
            pick = _ask(questionary.select, "Select section to remove:", choices=names)
            if pick:
                idx = int(pick.split(".")[0]) - 1
                data.custom_sections.pop(idx)
                _ok("Section removed.")


# ─── Create mode ──────────────────────────────────────────────────────────────


def _create_mode() -> CVData | None:
    data = CVData()

    _section_rule("Personal Information")
    data.personal = _collect_personal_info()
    if data.personal is None:
        return None

    _section_rule("Employment")
    while True:
        if not _ask(questionary.confirm, "Add an employment entry?", default=bool(not data.employment)):
            break
        entry = _edit_employment_entries(None)
        if entry:
            data.employment.append(entry)
            _ok("Entry added.")

    console.print()
    _section_rule("Education")
    while True:
        if not _ask(questionary.confirm, "Add an education entry?", default=bool(not data.education)):
            break
        entry = _edit_education_entries(None)
        if entry:
            data.education.append(entry)
            _ok("Entry added.")

    console.print()
    _section_rule("Skills / Expertise")
    while True:
        if not _ask(questionary.confirm, "Add a skill category?", default=bool(not data.skills)):
            break
        entry = _edit_skill_entries(None)
        if entry:
            data.skills.append(entry)
            _ok("Category added.")

    console.print()
    _section_rule("Miscellaneous")
    misc_choice = _ask(
        questionary.select,
        "Miscellaneous section:",
        choices=["Add entries", "Skip section"],
    )
    if misc_choice is None:
        return None
    if misc_choice == "Skip section":
        data.skipped_sections.add("misc")
    else:
        while True:
            entry = _edit_misc_entries(None)
            if entry:
                data.misc.append(entry)
                _ok("Entry added.")
            if not _ask(questionary.confirm, "Add another miscellaneous entry?", default=False):
                break

    console.print()
    _section_rule("Referees")
    ref_mode = _ask(
        questionary.select,
        "Referee section:",
        choices=["Available on Request", "List referees", "Skip section"],
    )
    if ref_mode == "List referees":
        data.referee_mode = "full"
        while True:
            ref = _collect_referee()
            if ref:
                data.referees.append(ref)
                _ok("Referee added.")
            if not _ask(questionary.confirm, "Add another referee?", default=False):
                break
    elif ref_mode == "Skip section":
        data.skipped_sections.add("referee")
    else:
        data.referee_mode = "short"

    console.print()
    if _ask(questionary.confirm, "Add custom sections (e.g. Publications, Awards)?", default=False):
        _manage_custom_sections(data)

    return data


def _collect_personal_info() -> PersonalInfo | None:
    name = _ask(questionary.text, "Full name (e.g. John Doe, Ph.D.):")
    email = _ask(questionary.text, "Email:")
    linkedin = _ask(questionary.text, "LinkedIn URL (optional):")
    linkedin_label = ""
    if linkedin:
        linkedin_label = (
            _ask(
                questionary.text,
                "LinkedIn display label:",
                default=linkedin.rstrip("/").split("/")[-1],
            )
            or ""
        )
    github = _ask(questionary.text, "Website / GitHub URL (optional):")
    photo = _ask(questionary.text, "Photo filename (without extension, optional):", default="photo")

    if any(v is None for v in [name, email]):
        return None

    return PersonalInfo(
        name=name,
        email=email,
        linkedin=linkedin or "",
        linkedin_label=linkedin_label or "",
        github=github or "",
        photo=photo or "photo",
    )


if __name__ == "__main__":
    main()
