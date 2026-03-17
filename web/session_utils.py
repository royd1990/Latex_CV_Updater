"""CVData <-> JSON dict serialization for Flask session storage."""

from __future__ import annotations

from dataclasses import asdict

from cv_updater.models import (
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


def cvdata_to_dict(data: CVData) -> dict:
    """Serialize CVData to a JSON-compatible dict."""
    d = asdict(data)
    # Convert set to list for JSON serialization
    d["skipped_sections"] = list(data.skipped_sections)
    return d


def dict_to_cvdata(d: dict) -> CVData:
    """Deserialize a dict back into CVData."""
    personal = PersonalInfo(**d.get("personal", {}))
    employment = [EmploymentEntry(**e) for e in d.get("employment", [])]
    education = [EducationEntry(**e) for e in d.get("education", [])]
    skills = [SkillCategory(**s) for s in d.get("skills", [])]
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
    return CVData(
        personal=personal,
        employment=employment,
        education=education,
        skills=skills,
        misc=misc,
        referees=referees,
        referee_mode=d.get("referee_mode", "short"),
        skipped_sections=set(d.get("skipped_sections", [])),
        custom_sections=custom_sections,
    )


def get_cv(session) -> CVData:
    """Load CVData from the Flask session."""
    return dict_to_cvdata(session.get("cv", {}))


def save_cv(session, data: CVData) -> None:
    """Save CVData to the Flask session."""
    session["cv"] = cvdata_to_dict(data)
    session.modified = True
