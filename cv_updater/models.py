"""Dataclasses representing CV sections."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmploymentEntry:
    start_year: str
    end_year: str  # Use "$\\cdots\\cdot$" for present
    title: str
    organization: str
    location: str

    @property
    def date_range(self) -> str:
        return f"{self.start_year} -- {self.end_year}"


@dataclass
class EducationEntry:
    start_year: str
    end_year: str
    degree: str
    institution: str
    specialization: str = ""
    thesis_title: str = ""

    @property
    def date_range(self) -> str:
        return f"{self.start_year} -- {self.end_year}"


@dataclass
class SkillCategory:
    label: str
    items: str  # Free-form text (comma-separated skills)


@dataclass
class MiscEntry:
    year: str
    title: str
    description: str
    subrubric: str = ""


@dataclass
class RefereeEntry:
    name: str
    title: str
    institution: str
    address: str = ""
    email: str = ""


@dataclass
class PersonalInfo:
    name: str = ""
    email: str = ""
    linkedin: str = ""
    linkedin_label: str = ""
    github: str = ""
    photo: str = ""


@dataclass
class CustomEntry:
    label: str  # Left-column label (year, date range, etc.)
    content: str  # Main content (free-form, may contain LaTeX)
    subrubric: str = ""  # Optional sub-section header


@dataclass
class CustomSection:
    title: str  # Rubric title shown in CV (e.g. "Publications")
    filename: str  # Output filename without .tex (e.g. "publications")
    entries: list[CustomEntry] = field(default_factory=list)


@dataclass
class CVData:
    personal: PersonalInfo = field(default_factory=PersonalInfo)
    employment: list[EmploymentEntry] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    skills: list[SkillCategory] = field(default_factory=list)
    misc: list[MiscEntry] = field(default_factory=list)
    referees: list[RefereeEntry] = field(default_factory=list)
    referee_mode: str = "short"  # "short" = available on request, "full" = listed
    skipped_sections: set = field(default_factory=set)  # section keys to omit entirely
    custom_sections: list[CustomSection] = field(default_factory=list)
