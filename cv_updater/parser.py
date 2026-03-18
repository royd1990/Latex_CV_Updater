"""Parse existing .tex files into CV data models."""

from __future__ import annotations

import re
from pathlib import Path

from .models import (
    CVData,
    DEFAULT_SECTION_ORDER,
    EducationEntry,
    EmploymentEntry,
    MiscEntry,
    PersonalInfo,
    ProjectEntry,
    RefereeEntry,
    SkillCategory,
)

PRESENT_MARKER = r"$\cdots\cdot$"


def parse_cv(cv_dir: Path) -> CVData:
    """Parse all .tex files in a CV directory into a CVData object."""
    data = CVData()

    about_path = cv_dir / "about.tex"
    if about_path.exists():
        data.about = parse_about(about_path.read_text())

    employment_path = cv_dir / "employment.tex"
    if employment_path.exists():
        data.employment = parse_employment(employment_path.read_text())

    education_path = cv_dir / "education.tex"
    if education_path.exists():
        data.education = parse_education(education_path.read_text())

    skills_path = cv_dir / "skills.tex"
    if skills_path.exists():
        data.skills = parse_skills(skills_path.read_text())

    project_highlights_path = cv_dir / "project_highlights.tex"
    if project_highlights_path.exists():
        data.project_highlights = parse_project_highlights(project_highlights_path.read_text())

    misc_path = cv_dir / "misc.tex"
    if misc_path.exists():
        data.misc = parse_misc(misc_path.read_text())

    main_path = cv_dir / "cv-llt.tex"
    if main_path.exists():
        main_text = main_path.read_text()
        data.personal = parse_personal_info(main_text)
        data.section_order = _parse_section_order(main_text, data)

    # Detect referee mode
    referee_path = cv_dir / "referee.tex"
    if referee_path.exists():
        content = referee_path.read_text()
        if "Available on Request" in content:
            data.referee_mode = "short"
        else:
            data.referee_mode = "full"

    referee_full_path = cv_dir / "referee-full.tex"
    if referee_full_path.exists():
        data.referees = parse_referees(referee_full_path.read_text())

    return data


def _parse_section_order(main_text: str, data: CVData) -> list[str]:
    """Extract the \makerubric order from cv-llt.tex, preserving user-defined section order."""
    order = []
    seen = set()
    for m in re.finditer(r"^(?!%)\s*\\makerubric\{([^}]+)\}", main_text, re.MULTILINE):
        key = m.group(1).strip()
        if key not in seen:
            order.append(key)
            seen.add(key)

    # Ensure all default built-in sections are present (add missing ones at end)
    for key in DEFAULT_SECTION_ORDER:
        if key not in seen:
            order.append(key)

    return order


def _parse_date_range(date_str: str) -> tuple[str, str]:
    """Parse a date range like '2021 -- $\\cdots\\cdot$' into (start, end)."""
    date_str = date_str.strip()
    parts = re.split(r"\s*--\s*", date_str, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return date_str, ""


def parse_about(text: str) -> str:
    """Parse about.tex content, returning the plain text body."""
    m = re.search(r"\\entry\*\[\\relax\]\s*([\s\S]*?)(?:\\end\{rubric\})", text)
    if m:
        return m.group(1).strip()
    return ""


def parse_employment(text: str) -> list[EmploymentEntry]:
    """Parse employment.tex content."""
    entries = []
    # Match \entry*[date range]% followed by content until next \entry* or \end{rubric}
    pattern = r"\\entry\*\[([^\]]+)\]%?\s*\n?\t*(.*?)(?=\\entry\*|\s*\\end\{rubric\})"
    for match in re.finditer(pattern, text, re.DOTALL):
        date_str = match.group(1)
        content = match.group(2).strip()
        # Remove comment lines
        content = re.sub(r"^%.*$", "", content, flags=re.MULTILINE).strip()

        start, end = _parse_date_range(date_str)

        # Parse: \textbf{Title,} Organization, Location
        title_match = re.match(r"\\textbf\{([^}]+)\}\s*(.*)", content, re.DOTALL)
        if title_match:
            title = title_match.group(1).rstrip(",").strip()
            rest = title_match.group(2).strip().rstrip("%").strip()
            # Split remaining by comma for org and location
            parts = [p.strip() for p in rest.split(",") if p.strip()]
            organization = parts[0] if parts else ""
            location = parts[-1] if len(parts) > 1 else ""
        else:
            title = content
            organization = ""
            location = ""

        entries.append(EmploymentEntry(
            start_year=start,
            end_year=end,
            title=title,
            organization=organization,
            location=location,
        ))
    return entries


def parse_education(text: str) -> list[EducationEntry]:
    """Parse education.tex content."""
    entries = []
    pattern = r"\\entry\*\[([^\]]+)\]%?\s*\n?\t*(.*?)(?=\\entry\*|\s*\\end\{rubric\})"
    for match in re.finditer(pattern, text, re.DOTALL):
        date_str = match.group(1)
        content = match.group(2).strip()
        content = re.sub(r"^%.*$", "", content, flags=re.MULTILINE).strip()

        start, end = _parse_date_range(date_str)

        # Extract thesis title if present
        thesis_title = ""
        thesis_match = re.search(r"Thesis title:\s*\\emph\{([^}]+)\}", content)
        if thesis_match:
            thesis_title = thesis_match.group(1)

        # Parse \textbf{Degree, Institution,} possibly with specialization
        title_match = re.match(r"\\textbf\{([^}]+)\}", content)
        degree = ""
        institution = ""
        specialization = ""
        if title_match:
            bold_text = title_match.group(1).rstrip(",").strip()
            # The bold text contains degree and institution separated by comma
            bold_parts = [p.strip() for p in bold_text.split(",") if p.strip()]
            if bold_parts:
                degree = bold_parts[0]
            if len(bold_parts) > 1:
                institution = ", ".join(bold_parts[1:])

            # Check for specialization after the bold part
            after_bold = content[title_match.end():].strip()
            # Remove \par and thesis line
            after_bold = re.sub(r"\\par\s*Thesis title:.*", "", after_bold, flags=re.DOTALL)
            after_bold = re.sub(r"\\par\s*$", "", after_bold).strip()
            if after_bold:
                spl_match = re.match(r"Spl\.?\s*in\s*(.*?)(?:\\par|$)", after_bold)
                if spl_match:
                    specialization = spl_match.group(1).strip().rstrip(".")
                elif not after_bold.startswith("\\"):
                    specialization = after_bold.strip().rstrip(".")

        entries.append(EducationEntry(
            start_year=start,
            end_year=end,
            degree=degree,
            institution=institution,
            specialization=specialization,
            thesis_title=thesis_title,
        ))
    return entries


def parse_skills(text: str) -> list[SkillCategory]:
    """Parse skills.tex content."""
    entries = []
    # Match \entry*[Label]\n\tContent
    pattern = r"\\entry\*\[([^\]]+)\]\s*\n?\t*(.*?)(?=\\entry\*|\\end\{rubric\})"
    for match in re.finditer(pattern, text, re.DOTALL):
        label = match.group(1).strip()
        # Preserve \hfill in label for round-trip fidelity
        items = match.group(2).strip()
        entries.append(SkillCategory(label=label, items=items))
    return entries


def parse_project_highlights(text: str) -> list[ProjectEntry]:
    """Parse project_highlights.tex content."""
    entries = []
    pattern = r"\\entry\*\[([^\]]+)\]%?\s*\n?\t*(.*?)(?=\\entry\*|\s*\\end\{rubric\})"
    for match in re.finditer(pattern, text, re.DOTALL):
        date_str = match.group(1)
        content = match.group(2).strip()
        content = re.sub(r"^%.*$", "", content, flags=re.MULTILINE).strip()

        start, end = _parse_date_range(date_str)

        # Parse \textbf{Title}
        title = ""
        title_match = re.match(r"\\textbf\{([^}]+)\}", content)
        if title_match:
            title = title_match.group(1).strip()
            rest = content[title_match.end():]
        else:
            rest = content

        # Extract URL if present
        url = ""
        url_match = re.search(r"\\href\{([^}]+)\}", rest)
        if url_match:
            url = url_match.group(1).strip()

        # Extract description from \par <text> (not starting with \textit)
        description = ""
        desc_match = re.search(r"\\par\s+(?!\\textit)(.*?)(?=\\par|$)", rest, re.DOTALL)
        if desc_match:
            description = desc_match.group(1).strip()

        # Extract technologies from \par \textit{Technologies:} ...
        technologies = ""
        tech_match = re.search(r"\\textit\{Technologies:\}\s*(.*?)(?=\\par|$)", rest, re.DOTALL)
        if tech_match:
            technologies = tech_match.group(1).strip()

        entries.append(ProjectEntry(
            title=title,
            start_year=start,
            end_year=end,
            description=description,
            technologies=technologies,
            url=url,
        ))
    return entries


def parse_misc(text: str) -> list[MiscEntry]:
    """Parse misc.tex content."""
    entries = []
    current_subrubric = ""

    # First, find all subrubric markers
    lines = text.split("\n")
    # Process the text to find subrubrics and entries
    subrubric_pattern = r"\\subrubric\{([^}]+)\}"
    entry_pattern = r"\\entry\*\[([^\]]+)\]\s*(.*)"

    for line in lines:
        sub_match = re.search(subrubric_pattern, line)
        if sub_match:
            current_subrubric = sub_match.group(1)
            continue

        entry_match = re.search(entry_pattern, line)
        if entry_match:
            year = entry_match.group(1).strip()
            content = entry_match.group(2).strip()

            # Parse \textbf{Title}, Description
            title = ""
            description = ""
            title_match = re.match(r"\\textbf\{([^}]+)\}[,.]?\s*(.*)", content)
            if title_match:
                title = title_match.group(1).strip()
                description = title_match.group(2).strip().rstrip(".")
            else:
                title = content

            entries.append(MiscEntry(
                year=year,
                title=title,
                description=description,
                subrubric=current_subrubric,
            ))

    return entries


def parse_personal_info(text: str) -> PersonalInfo:
    """Parse personal info from cv-llt.tex leftheader block."""
    info = PersonalInfo()

    # Name
    name_match = re.search(r"\\bfseries\\sffamily\s+([^}]+)\}", text)
    if name_match:
        info.name = name_match.group(1).strip()

    # Email
    email_match = re.search(r"mailto:([^}]+)\}", text)
    if email_match:
        info.email = email_match.group(1).strip()

    # LinkedIn
    linkedin_match = re.search(r"linkedin\.com/in/([^/}]+)", text)
    if linkedin_match:
        info.linkedin = f"https://www.linkedin.com/in/{linkedin_match.group(1).strip()}/"
    label_match = re.search(r"\\faLinkedin\}.*?\\texttt\{([^}]+)\}", text, re.DOTALL)
    if label_match:
        info.linkedin_label = label_match.group(1).strip()

    # GitHub / Globe URL
    github_match = re.search(r"\\faGlobe\}.*?\\url\{([^}]+)\}", text, re.DOTALL)
    if github_match:
        info.github = github_match.group(1).strip()

    # Photo — detect skip_photo if the fullonly block is absent or commented
    photo_match = re.search(r"\\photo\[r\]\{([^}]+)\}", text)
    if photo_match:
        info.photo = photo_match.group(1).strip()
        # Check if the fullonly block containing the photo is present (not commented out)
        fullonly_match = re.search(r"\\begin\{fullonly\}", text)
        info.skip_photo = not bool(fullonly_match)
    else:
        info.skip_photo = True

    return info


def parse_referees(text: str) -> list[RefereeEntry]:
    """Parse referee-full.tex content."""
    entries = []
    # Split by & or \\ to get individual referee blocks
    blocks = re.split(r"(?:&|\\\\)", text)
    for block in blocks:
        name_match = re.search(r"\\textbf\{([^}]+)\}", block)
        if not name_match:
            continue
        name = name_match.group(1).strip()

        # Get lines after the name (each separated by \par)
        parts = re.split(r"\\par\s*", block)
        title = ""
        institution = ""
        address = ""
        email = ""

        # First part has the name, subsequent parts have details
        detail_parts = []
        for part in parts[1:]:
            part = part.strip().rstrip(",")
            if not part or part.startswith("\\makefield"):
                continue
            detail_parts.append(part)

        if detail_parts:
            title = detail_parts[0]
        if len(detail_parts) > 1:
            institution = detail_parts[1]
        if len(detail_parts) > 2:
            address = detail_parts[2]

        email_match = re.search(r"\\url\{([^}]+)\}", block)
        if email_match:
            email = email_match.group(1).strip()

        entries.append(RefereeEntry(
            name=name,
            title=title,
            institution=institution,
            address=address,
            email=email,
        ))
    return entries
