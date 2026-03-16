"""Interactive CLI for creating and updating LaTeX CVs."""

from __future__ import annotations

import sys
from pathlib import Path

import questionary

from .compiler import check_prerequisites, compile_cv
from .generator import escape_latex, generate_cv, generate_main
from .models import (
    CVData,
    EducationEntry,
    EmploymentEntry,
    MiscEntry,
    PersonalInfo,
    RefereeEntry,
    SkillCategory,
)
from .parser import PRESENT_MARKER, parse_cv

DEFAULT_CV_DIR = Path(__file__).parent.parent / "Deba_CV"


def main() -> None:
    """Main entry point for the CV updater CLI."""
    print("\n=== LaTeX CV Updater ===\n")

    # Check LaTeX prerequisites
    issues = check_prerequisites()
    if issues:
        print("Warning: Some prerequisites are missing:")
        for issue in issues:
            print(f"  - {issue}")
        print()

    cv_dir = _ask_cv_directory()

    mode = questionary.select(
        "What would you like to do?",
        choices=["Update existing CV", "Create new CV"],
    ).ask()

    if mode is None:
        print("Cancelled.")
        return

    if mode == "Update existing CV":
        data = _update_mode(cv_dir)
    else:
        data = _create_mode()

    if data is None:
        print("Cancelled.")
        return

    # Generate files
    print("\nGenerating .tex files...")
    generated = generate_cv(data, cv_dir)
    for f in generated:
        print(f"  Written: {f.name}")

    if mode == "Create new CV":
        main_file = generate_main(data, cv_dir)
        print(f"  Written: {main_file.name}")

    # Compile
    if questionary.confirm("Compile to PDF?", default=True).ask():
        tex_path = cv_dir / "cv-llt.tex"
        if not tex_path.exists():
            print(f"Main file not found: {tex_path}")
            return
        print("\nCompiling (this may take a moment)...")
        success, message = compile_cv(tex_path)
        if success:
            print(f"\n{message}")
        else:
            print(f"\nCompilation failed:\n{message}")
    else:
        print("\nSkipping compilation. You can compile manually:")
        print(f"  cd {cv_dir} && xelatex cv-llt.tex && biber cv-llt && xelatex cv-llt.tex && xelatex cv-llt.tex")

    print("\nDone!")


def _ask_cv_directory() -> Path:
    """Ask user for CV directory path."""
    default = str(DEFAULT_CV_DIR)
    path_str = questionary.text(
        "CV directory path:",
        default=default,
    ).ask()
    if path_str is None:
        sys.exit(0)
    path = Path(path_str).resolve()
    if not path.exists():
        if questionary.confirm(f"Directory {path} does not exist. Create it?", default=True).ask():
            path.mkdir(parents=True, exist_ok=True)
        else:
            sys.exit(0)
    return path


# =============================================================================
# UPDATE MODE
# =============================================================================


def _update_mode(cv_dir: Path) -> CVData | None:
    """Interactive update of an existing CV."""
    print("\nParsing existing CV files...")
    data = parse_cv(cv_dir)

    sections = [
        ("Employment", data.employment, _edit_employment_entries),
        ("Education", data.education, _edit_education_entries),
        ("Skills", data.skills, _edit_skill_entries),
        ("Miscellaneous", data.misc, _edit_misc_entries),
    ]

    for section_name, entries, edit_fn in sections:
        print(f"\n--- {section_name} ({len(entries)} entries) ---")
        _display_entries(section_name, entries)

        action = questionary.select(
            f"What would you like to do with {section_name}?",
            choices=["Keep as is", "Add entry", "Edit entry", "Remove entry"],
        ).ask()

        if action is None:
            return None
        if action == "Keep as is":
            continue
        elif action == "Add entry":
            new_entry = edit_fn(None)
            if new_entry:
                entries.insert(0, new_entry)  # Add to top (most recent)
        elif action == "Edit entry":
            if not entries:
                print("No entries to edit.")
                continue
            idx = _pick_entry_index(entries)
            if idx is not None:
                edited = edit_fn(entries[idx])
                if edited:
                    entries[idx] = edited
        elif action == "Remove entry":
            if not entries:
                print("No entries to remove.")
                continue
            idx = _pick_entry_index(entries)
            if idx is not None:
                entries.pop(idx)
                print("Entry removed.")

    # Referee mode
    ref_mode = questionary.select(
        "Referee section:",
        choices=["Available on Request", "List referees"],
    ).ask()
    if ref_mode == "List referees":
        data.referee_mode = "full"
        if not data.referees:
            print("No referees found. Add them:")
            while True:
                ref = _collect_referee()
                if ref:
                    data.referees.append(ref)
                if not questionary.confirm("Add another referee?", default=False).ask():
                    break
    else:
        data.referee_mode = "short"

    return data


def _display_entries(section_name: str, entries: list) -> None:
    """Display numbered list of entries."""
    if not entries:
        print("  (no entries)")
        return
    for i, entry in enumerate(entries, 1):
        print(f"  {i}. {_entry_summary(entry)}")


def _entry_summary(entry) -> str:
    """One-line summary of an entry."""
    if isinstance(entry, EmploymentEntry):
        return f"[{entry.date_range}] {entry.title}, {entry.organization}"
    elif isinstance(entry, EducationEntry):
        return f"[{entry.date_range}] {entry.degree}, {entry.institution}"
    elif isinstance(entry, SkillCategory):
        return f"[{entry.label}] {entry.items[:60]}..."
    elif isinstance(entry, MiscEntry):
        return f"[{entry.year}] {entry.title} ({entry.subrubric})"
    return str(entry)


def _pick_entry_index(entries: list) -> int | None:
    """Ask user to pick an entry by number."""
    choices = [f"{i+1}. {_entry_summary(e)}" for i, e in enumerate(entries)]
    choice = questionary.select("Select entry:", choices=choices).ask()
    if choice is None:
        return None
    return int(choice.split(".")[0]) - 1


# =============================================================================
# ENTRY EDITORS (used for both Add and Edit)
# =============================================================================


def _edit_employment_entries(existing: EmploymentEntry | None) -> EmploymentEntry | None:
    """Collect or edit an employment entry."""
    defaults = existing or EmploymentEntry("", "", "", "", "")

    start = questionary.text("Start year:", default=defaults.start_year).ask()
    if start is None:
        return None

    is_current = questionary.confirm("Is this your current position?", default=(defaults.end_year == PRESENT_MARKER)).ask()
    end = PRESENT_MARKER if is_current else questionary.text("End year:", default=defaults.end_year).ask()
    if end is None:
        return None

    title = questionary.text("Job title:", default=defaults.title).ask()
    org = questionary.text("Organization:", default=defaults.organization).ask()
    location = questionary.text("Location:", default=defaults.location).ask()

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
    """Collect or edit an education entry."""
    defaults = existing or EducationEntry("", "", "", "", "", "")

    start = questionary.text("Start year:", default=defaults.start_year).ask()
    end = questionary.text("End year:", default=defaults.end_year).ask()
    degree = questionary.text("Degree:", default=defaults.degree).ask()
    institution = questionary.text("Institution:", default=defaults.institution).ask()
    specialization = questionary.text("Specialization (optional):", default=defaults.specialization).ask()
    thesis = questionary.text("Thesis title (optional):", default=defaults.thesis_title).ask()

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
    """Collect or edit a skill category."""
    defaults = existing or SkillCategory("", "")

    label = questionary.text("Category label:", default=defaults.label).ask()
    items = questionary.text("Skills (comma-separated):", default=defaults.items).ask()

    if any(v is None for v in [label, items]):
        return None

    return SkillCategory(label=escape_latex(label), items=escape_latex(items))


def _edit_misc_entries(existing: MiscEntry | None) -> MiscEntry | None:
    """Collect or edit a misc entry."""
    defaults = existing or MiscEntry("", "", "", "")

    subrubric = questionary.text("Sub-section (e.g., Awards and Achievements):", default=defaults.subrubric).ask()
    year = questionary.text("Year:", default=defaults.year).ask()
    title = questionary.text("Title:", default=defaults.title).ask()
    description = questionary.text("Description:", default=defaults.description).ask()

    if any(v is None for v in [year, title]):
        return None

    return MiscEntry(
        year=year,
        title=escape_latex(title),
        description=escape_latex(description or ""),
        subrubric=escape_latex(subrubric or ""),
    )


def _collect_referee() -> RefereeEntry | None:
    """Collect a referee entry."""
    name = questionary.text("Referee name:").ask()
    title = questionary.text("Title (e.g., Professor):").ask()
    institution = questionary.text("Institution:").ask()
    address = questionary.text("Address (optional):").ask()
    email = questionary.text("Email:").ask()

    if any(v is None for v in [name, title, institution, email]):
        return None

    return RefereeEntry(
        name=escape_latex(name),
        title=escape_latex(title),
        institution=escape_latex(institution),
        address=escape_latex(address or ""),
        email=email,  # Don't escape email
    )


# =============================================================================
# CREATE MODE
# =============================================================================


def _create_mode() -> CVData | None:
    """Interactive creation of a new CV from scratch."""
    data = CVData()

    # Personal info
    print("\n--- Personal Information ---")
    data.personal = _collect_personal_info()
    if data.personal is None:
        return None

    # Employment
    print("\n--- Employment ---")
    while True:
        if not questionary.confirm("Add an employment entry?", default=bool(not data.employment)).ask():
            break
        entry = _edit_employment_entries(None)
        if entry:
            data.employment.append(entry)

    # Education
    print("\n--- Education ---")
    while True:
        if not questionary.confirm("Add an education entry?", default=bool(not data.education)).ask():
            break
        entry = _edit_education_entries(None)
        if entry:
            data.education.append(entry)

    # Skills
    print("\n--- Skills / Expertise ---")
    while True:
        if not questionary.confirm("Add a skill category?", default=bool(not data.skills)).ask():
            break
        entry = _edit_skill_entries(None)
        if entry:
            data.skills.append(entry)

    # Misc
    print("\n--- Miscellaneous (Awards, Certifications, etc.) ---")
    while True:
        if not questionary.confirm("Add a miscellaneous entry?", default=False).ask():
            break
        entry = _edit_misc_entries(None)
        if entry:
            data.misc.append(entry)

    # Referees
    ref_mode = questionary.select(
        "Referee section:",
        choices=["Available on Request", "List referees"],
    ).ask()
    if ref_mode == "List referees":
        data.referee_mode = "full"
        while True:
            ref = _collect_referee()
            if ref:
                data.referees.append(ref)
            if not questionary.confirm("Add another referee?", default=False).ask():
                break
    else:
        data.referee_mode = "short"

    return data


def _collect_personal_info() -> PersonalInfo | None:
    """Collect personal information for the CV header."""
    name = questionary.text("Full name (e.g., John Doe, Ph.D.):").ask()
    email = questionary.text("Email:").ask()
    linkedin = questionary.text("LinkedIn URL (optional):").ask()
    linkedin_label = ""
    if linkedin:
        linkedin_label = questionary.text("LinkedIn display label:", default=linkedin.rstrip("/").split("/")[-1]).ask()
    github = questionary.text("Website/GitHub URL (optional):").ask()
    photo = questionary.text("Photo filename (without extension, optional):", default="photo").ask()

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
