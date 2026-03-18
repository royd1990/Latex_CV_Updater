"""CVData <-> JSON dict serialization for Flask session storage."""

from __future__ import annotations

from dataclasses import asdict

from cv_updater.models import (
    CVData,
    CustomEntry,
    CustomSection,
    DEFAULT_SECTION_ORDER,
    EducationEntry,
    EmploymentEntry,
    MiscEntry,
    PersonalInfo,
    ProjectEntry,
    RefereeEntry,
    SkillCategory,
)


def cvdata_to_dict(data: CVData) -> dict:
    """Serialize CVData to a JSON-compatible dict."""
    d = asdict(data)
    # Convert set to list for JSON serialization
    d["skipped_sections"] = list(data.skipped_sections)
    return d


def dict_to_cvdata(d: dict) -> CVData:
    """Deserialize a dict back into CVData."""
    personal_dict = d.get("personal", {})
    # PersonalInfo has skip_photo with default=False; handle old sessions that lack it
    personal = PersonalInfo(
        name=personal_dict.get("name", ""),
        email=personal_dict.get("email", ""),
        linkedin=personal_dict.get("linkedin", ""),
        linkedin_label=personal_dict.get("linkedin_label", ""),
        github=personal_dict.get("github", ""),
        photo=personal_dict.get("photo", ""),
        skip_photo=personal_dict.get("skip_photo", False),
    )
    employment = [EmploymentEntry(**e) for e in d.get("employment", [])]
    education = [EducationEntry(**e) for e in d.get("education", [])]
    skills = [SkillCategory(**s) for s in d.get("skills", [])]
    project_highlights = [ProjectEntry(**p) for p in d.get("project_highlights", [])]
    misc = [MiscEntry(**m) for m in d.get("misc", [])]
    referees = [RefereeEntry(**r) for r in d.get("referees", [])]
    custom_sections = []
    for cs in d.get("custom_sections", []):
        entries = [CustomEntry(**e) for e in cs.get("entries", [])]
        custom_sections.append(
            CustomSection(
                title=cs["title"],
                filename=cs["filename"],
                entries=entries,
            )
        )

    # section_order: use stored value if present, else fall back to default
    section_order = d.get("section_order")
    if not section_order:
        section_order = list(DEFAULT_SECTION_ORDER)
    else:
        # Ensure all default built-in sections exist in the order
        for key in DEFAULT_SECTION_ORDER:
            if key not in section_order:
                section_order.append(key)

    return CVData(
        personal=personal,
        about=d.get("about", ""),
        employment=employment,
        education=education,
        skills=skills,
        project_highlights=project_highlights,
        misc=misc,
        referees=referees,
        referee_mode=d.get("referee_mode", "short"),
        skipped_sections=set(d.get("skipped_sections", [])),
        custom_sections=custom_sections,
        section_order=section_order,
        prefix_marker=d.get("prefix_marker", ""),
    )


def get_cv(session) -> CVData:
    """Load CVData from the Flask session."""
    return dict_to_cvdata(session.get("cv", {}))


def save_cv(session, data: CVData) -> None:
    """Save CVData to the Flask session."""
    session["cv"] = cvdata_to_dict(data)
    session.modified = True
