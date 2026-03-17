"""Flask web app for LaTeX CV Updater — TUI aesthetic."""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from flask import (
    Flask,
    after_this_request,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from cv_updater.compiler import check_prerequisites, compile_cv
from cv_updater.generator import copy_support_files, generate_cv, generate_main
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
from cv_updater.parser import parse_cv

from .session_utils import get_cv, save_cv

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

# Fallback directory for LaTeX support files (settings.sty, own-bib.bib, photo.jpg)
_PROJECT_ROOT = Path(__file__).parent.parent
SUPPORT_FILE_FALLBACK_DIRS: list[Path] = [
    _PROJECT_ROOT / "Deba_CV",
    _PROJECT_ROOT / "Deba_CV_2",
]

app = Flask(__name__)
app.secret_key = os.environ.get("CV_SECRET_KEY", "dev-secret-cv-updater-2024")
app.config["SESSION_COOKIE_SIZE_LIMIT"] = None  # allow large cookies

# Use filesystem session so we can store large CV data
try:
    from flask_session import Session  # type: ignore

    _session_dir = Path(tempfile.gettempdir()) / "cv_flask_sessions"
    _session_dir.mkdir(exist_ok=True)
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = str(_session_dir)
    app.config["SESSION_PERMANENT"] = False
    Session(app)
except ImportError:
    pass  # Fall back to cookie sessions (limited to ~4KB)

WIZARD_STEPS = [
    "personal",
    "employment",
    "education",
    "skills",
    "misc",
    "referee",
    "custom",
    "download",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _copy_support_files(out_dir: Path) -> None:
    """Copy settings.sty, own-bib.bib, photo.jpg into out_dir.

    Tries upload_dir first, then each SUPPORT_FILE_FALLBACK_DIRS entry.
    copy_support_files() is a no-op if the file already exists in dest.
    """
    upload_dir = session.get("upload_dir")
    if upload_dir:
        copy_support_files(Path(upload_dir), out_dir)
    for fallback in SUPPORT_FILE_FALLBACK_DIRS:
        if fallback.exists():
            copy_support_files(fallback, out_dir)


def _parse_indexed(form, prefix: str, fields: list[str]) -> list[dict]:
    """Parse form fields like prefix[0][field] into a list of dicts."""
    entries = []
    i = 0
    while f"{prefix}[{i}][{fields[0]}]" in form:
        entry = {f: form.get(f"{prefix}[{i}][{f}]", "").strip() for f in fields}
        entries.append(entry)
        i += 1
    return entries


def _mark_visited(step: str) -> None:
    visited = session.get("visited", [])
    if step not in visited:
        visited.append(step)
        session["visited"] = visited
        session.modified = True


def _require_cv():
    """Return CVData or None; redirects to / if session is empty."""
    if "cv" not in session:
        return None
    return get_cv(session)


def _next_step(current: str) -> str:
    idx = WIZARD_STEPS.index(current)
    if idx + 1 < len(WIZARD_STEPS):
        return WIZARD_STEPS[idx + 1]
    return "download"


def _prev_step(current: str) -> str:
    idx = WIZARD_STEPS.index(current)
    if idx > 0:
        return WIZARD_STEPS[idx - 1]
    return "personal"


# ---------------------------------------------------------------------------
# Index / landing
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    issues = check_prerequisites()
    return render_template(
        "index.html",
        page_title="Home",
        issues=issues,
        wizard_steps=WIZARD_STEPS,
    )


# ---------------------------------------------------------------------------
# Start: create
# ---------------------------------------------------------------------------


@app.route("/start/create", methods=["POST"])
def start_create():
    session.clear()
    session["mode"] = "create"
    session["visited"] = []
    save_cv(session, CVData())
    return redirect(url_for("edit_personal"))


# ---------------------------------------------------------------------------
# Start: upload
# ---------------------------------------------------------------------------


@app.route("/start/upload", methods=["GET", "POST"])
def start_upload():
    if request.method == "GET":
        return render_template(
            "upload.html",
            page_title="Upload CV Files",
            wizard_steps=WIZARD_STEPS,
        )

    # POST: save files to tmpdir, parse, store in session
    upload_dir = Path(tempfile.mkdtemp(prefix="cv_web_"))
    saved_any = False

    file_fields = [
        "cv_main",
        "employment",
        "education",
        "skills",
        "misc",
        "referee",
        "referee_full",
    ]
    field_to_filename = {
        "cv_main": "cv-llt.tex",
        "employment": "employment.tex",
        "education": "education.tex",
        "skills": "skills.tex",
        "misc": "misc.tex",
        "referee": "referee.tex",
        "referee_full": "referee-full.tex",
    }

    for field in file_fields:
        f = request.files.get(field)
        if f and f.filename:
            dest = upload_dir / field_to_filename[field]
            f.save(str(dest))
            saved_any = True

    if not saved_any:
        flash("No files uploaded. Please select at least one .tex file.", "error")
        return redirect(url_for("start_upload"))

    try:
        data = parse_cv(upload_dir)
    except Exception as exc:
        shutil.rmtree(upload_dir, ignore_errors=True)
        flash(f"Failed to parse CV files: {exc}", "error")
        return redirect(url_for("start_upload"))

    session.clear()
    session["mode"] = "update"
    session["upload_dir"] = str(upload_dir)
    session["visited"] = []
    save_cv(session, data)
    flash("CV files parsed successfully.", "success")
    return redirect(url_for("edit_personal"))


# ---------------------------------------------------------------------------
# Edit: personal
# ---------------------------------------------------------------------------


@app.route("/edit/personal", methods=["GET", "POST"])
def edit_personal():
    cv = _require_cv()
    if cv is None:
        return redirect(url_for("index"))

    if request.method == "POST":
        action = request.form.get("action", "next")
        cv.personal = PersonalInfo(
            name=request.form.get("name", "").strip(),
            email=request.form.get("email", "").strip(),
            linkedin=request.form.get("linkedin", "").strip(),
            linkedin_label=request.form.get("linkedin_label", "").strip(),
            github=request.form.get("github", "").strip(),
            photo=request.form.get("photo", "").strip(),
        )
        save_cv(session, cv)
        _mark_visited("personal")
        if action == "next":
            return redirect(url_for("edit_employment"))
        return redirect(url_for("edit_personal"))

    _mark_visited("personal")
    return render_template(
        "personal.html",
        page_title="Personal Info",
        cv=cv,
        wizard_steps=WIZARD_STEPS,
        current_step="personal",
        visited=session.get("visited", []),
    )


# ---------------------------------------------------------------------------
# Edit: employment
# ---------------------------------------------------------------------------


@app.route("/edit/employment", methods=["GET", "POST"])
def edit_employment():
    cv = _require_cv()
    if cv is None:
        return redirect(url_for("index"))

    if request.method == "POST":
        action = request.form.get("action", "next")
        rows = _parse_indexed(
            request.form,
            "employment",
            ["start_year", "end_year", "title", "organization", "location"],
        )
        cv.employment = [
            EmploymentEntry(
                start_year=r["start_year"],
                end_year=r["end_year"],
                title=r["title"],
                organization=r["organization"],
                location=r["location"],
            )
            for r in rows
            if any(r.values())
        ]
        save_cv(session, cv)
        _mark_visited("employment")
        if action == "prev":
            return redirect(url_for("edit_personal"))
        if action == "next":
            return redirect(url_for("edit_education"))
        return redirect(url_for("edit_employment"))

    _mark_visited("employment")
    return render_template(
        "employment.html",
        page_title="Employment",
        cv=cv,
        wizard_steps=WIZARD_STEPS,
        current_step="employment",
        visited=session.get("visited", []),
    )


# ---------------------------------------------------------------------------
# Edit: education
# ---------------------------------------------------------------------------


@app.route("/edit/education", methods=["GET", "POST"])
def edit_education():
    cv = _require_cv()
    if cv is None:
        return redirect(url_for("index"))

    if request.method == "POST":
        action = request.form.get("action", "next")
        rows = _parse_indexed(
            request.form,
            "education",
            ["start_year", "end_year", "degree", "institution", "specialization", "thesis_title"],
        )
        cv.education = [
            EducationEntry(
                start_year=r["start_year"],
                end_year=r["end_year"],
                degree=r["degree"],
                institution=r["institution"],
                specialization=r["specialization"],
                thesis_title=r["thesis_title"],
            )
            for r in rows
            if any(r.values())
        ]
        save_cv(session, cv)
        _mark_visited("education")
        if action == "prev":
            return redirect(url_for("edit_employment"))
        if action == "next":
            return redirect(url_for("edit_skills"))
        return redirect(url_for("edit_education"))

    _mark_visited("education")
    return render_template(
        "education.html",
        page_title="Education",
        cv=cv,
        wizard_steps=WIZARD_STEPS,
        current_step="education",
        visited=session.get("visited", []),
    )


# ---------------------------------------------------------------------------
# Edit: skills
# ---------------------------------------------------------------------------


@app.route("/edit/skills", methods=["GET", "POST"])
def edit_skills():
    cv = _require_cv()
    if cv is None:
        return redirect(url_for("index"))

    if request.method == "POST":
        action = request.form.get("action", "next")
        rows = _parse_indexed(request.form, "skills", ["label", "items"])
        cv.skills = [
            SkillCategory(label=r["label"], items=r["items"])
            for r in rows
            if any(r.values())
        ]
        save_cv(session, cv)
        _mark_visited("skills")
        if action == "prev":
            return redirect(url_for("edit_education"))
        if action == "next":
            return redirect(url_for("edit_misc"))
        return redirect(url_for("edit_skills"))

    _mark_visited("skills")
    return render_template(
        "skills.html",
        page_title="Skills",
        cv=cv,
        wizard_steps=WIZARD_STEPS,
        current_step="skills",
        visited=session.get("visited", []),
    )


# ---------------------------------------------------------------------------
# Edit: misc
# ---------------------------------------------------------------------------


@app.route("/edit/misc", methods=["GET", "POST"])
def edit_misc():
    cv = _require_cv()
    if cv is None:
        return redirect(url_for("index"))

    if request.method == "POST":
        action = request.form.get("action", "next")
        if "skip_misc" in request.form:
            cv.skipped_sections.add("misc")
        else:
            cv.skipped_sections.discard("misc")
            rows = _parse_indexed(
                request.form, "misc", ["year", "title", "description", "subrubric"]
            )
            cv.misc = [
                MiscEntry(
                    year=r["year"],
                    title=r["title"],
                    description=r["description"],
                    subrubric=r["subrubric"],
                )
                for r in rows
                if any(r.values())
            ]
        save_cv(session, cv)
        _mark_visited("misc")
        if action == "prev":
            return redirect(url_for("edit_skills"))
        if action == "next":
            return redirect(url_for("edit_referee"))
        return redirect(url_for("edit_misc"))

    _mark_visited("misc")
    return render_template(
        "misc.html",
        page_title="Miscellaneous",
        cv=cv,
        wizard_steps=WIZARD_STEPS,
        current_step="misc",
        visited=session.get("visited", []),
    )


# ---------------------------------------------------------------------------
# Edit: referee
# ---------------------------------------------------------------------------


@app.route("/edit/referee", methods=["GET", "POST"])
def edit_referee():
    cv = _require_cv()
    if cv is None:
        return redirect(url_for("index"))

    if request.method == "POST":
        action = request.form.get("action", "next")
        referee_mode = request.form.get("referee_mode", "short")

        if referee_mode == "skip":
            cv.skipped_sections.add("referee")
            cv.referees = []
        else:
            cv.skipped_sections.discard("referee")
            cv.referee_mode = referee_mode
            if referee_mode == "full":
                rows = _parse_indexed(
                    request.form,
                    "referees",
                    ["name", "title", "institution", "address", "email"],
                )
                cv.referees = [
                    RefereeEntry(
                        name=r["name"],
                        title=r["title"],
                        institution=r["institution"],
                        address=r["address"],
                        email=r["email"],
                    )
                    for r in rows
                    if any(r.values())
                ]
            else:
                cv.referees = []

        save_cv(session, cv)
        _mark_visited("referee")
        if action == "prev":
            return redirect(url_for("edit_misc"))
        if action == "next":
            return redirect(url_for("edit_custom"))
        return redirect(url_for("edit_referee"))

    _mark_visited("referee")
    return render_template(
        "referee.html",
        page_title="Referees",
        cv=cv,
        wizard_steps=WIZARD_STEPS,
        current_step="referee",
        visited=session.get("visited", []),
    )


# ---------------------------------------------------------------------------
# Edit: custom sections list
# ---------------------------------------------------------------------------


@app.route("/edit/custom", methods=["GET", "POST"])
def edit_custom():
    cv = _require_cv()
    if cv is None:
        return redirect(url_for("index"))

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "add":
            title = request.form.get("new_title", "").strip()
            filename = request.form.get("new_filename", "").strip()
            if title and filename:
                # Sanitize filename
                filename = filename.lower().replace(" ", "_")
                filename = "".join(c for c in filename if c.isalnum() or c == "_")
                cv.custom_sections.append(
                    CustomSection(title=title, filename=filename, entries=[])
                )
                save_cv(session, cv)
                flash(f'Section "{title}" added.', "success")
            else:
                flash("Both title and filename are required.", "error")
            return redirect(url_for("edit_custom"))

        if action == "delete":
            idx = int(request.form.get("idx", -1))
            if 0 <= idx < len(cv.custom_sections):
                removed = cv.custom_sections.pop(idx)
                save_cv(session, cv)
                flash(f'Section "{removed.title}" deleted.', "success")
            return redirect(url_for("edit_custom"))

        if action == "prev":
            save_cv(session, cv)
            return redirect(url_for("edit_referee"))

        if action == "next":
            save_cv(session, cv)
            _mark_visited("custom")
            return redirect(url_for("download_page"))

    _mark_visited("custom")
    return render_template(
        "custom.html",
        page_title="Custom Sections",
        cv=cv,
        wizard_steps=WIZARD_STEPS,
        current_step="custom",
        visited=session.get("visited", []),
    )


# ---------------------------------------------------------------------------
# Edit: one custom section
# ---------------------------------------------------------------------------


@app.route("/edit/custom/<int:idx>", methods=["GET", "POST"])
def edit_custom_section(idx: int):
    cv = _require_cv()
    if cv is None:
        return redirect(url_for("index"))

    if idx < 0 or idx >= len(cv.custom_sections):
        flash("Section not found.", "error")
        return redirect(url_for("edit_custom"))

    section = cv.custom_sections[idx]

    if request.method == "POST":
        action = request.form.get("action", "save")
        section.title = request.form.get("section_title", section.title).strip()
        section.filename = request.form.get("section_filename", section.filename).strip()

        rows = _parse_indexed(
            request.form, "entries", ["label", "content", "subrubric"]
        )
        section.entries = [
            CustomEntry(
                label=r["label"],
                content=r["content"],
                subrubric=r["subrubric"],
            )
            for r in rows
            if r["label"] or r["content"]
        ]
        save_cv(session, cv)
        flash("Section saved.", "success")
        return redirect(url_for("edit_custom"))

    return render_template(
        "custom_edit.html",
        page_title=f"Edit: {section.title}",
        cv=cv,
        section=section,
        idx=idx,
        wizard_steps=WIZARD_STEPS,
        current_step="custom",
        visited=session.get("visited", []),
    )


# ---------------------------------------------------------------------------
# Download page
# ---------------------------------------------------------------------------


@app.route("/download")
def download_page():
    cv = _require_cv()
    if cv is None:
        return redirect(url_for("index"))
    issues = check_prerequisites()
    _mark_visited("download")
    return render_template(
        "download.html",
        page_title="Download",
        cv=cv,
        issues=issues,
        wizard_steps=WIZARD_STEPS,
        current_step="download",
        visited=session.get("visited", []),
    )


# ---------------------------------------------------------------------------
# Download: ZIP
# ---------------------------------------------------------------------------


@app.route("/download/zip", methods=["POST"])
def download_zip():
    cv = _require_cv()
    if cv is None:
        return redirect(url_for("index"))

    out_dir = Path(tempfile.mkdtemp(prefix="cv_zip_"))
    try:
        generate_main(cv, out_dir)
        generate_cv(cv, out_dir)
        _copy_support_files(out_dir)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for filepath in sorted(out_dir.iterdir()):
                if filepath.is_file():
                    zf.write(filepath, filepath.name)
        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name="cv.zip",
        )
    except Exception as exc:
        flash(f"Failed to generate ZIP: {exc}", "error")
        return redirect(url_for("download_page"))
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Download: PDF
# ---------------------------------------------------------------------------


@app.route("/download/pdf", methods=["POST"])
def download_pdf():
    cv = _require_cv()
    if cv is None:
        return redirect(url_for("index"))

    issues = check_prerequisites()
    if issues:
        flash("LaTeX not available: " + issues[0].split("\n")[0], "error")
        return redirect(url_for("download_page"))

    out_dir = Path(tempfile.mkdtemp(prefix="cv_pdf_"))
    try:
        main_tex = generate_main(cv, out_dir)
        generate_cv(cv, out_dir)
        _copy_support_files(out_dir)

        success, message = compile_cv(main_tex)
        if not success:
            shutil.rmtree(out_dir, ignore_errors=True)
            flash(f"Compilation failed: {message}", "error")
            return redirect(url_for("download_page"))

        pdf_path = out_dir / "cv-llt.pdf"
        if not pdf_path.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
            flash("Compilation succeeded but no PDF was found.", "error")
            return redirect(url_for("download_page"))

        @after_this_request
        def cleanup(response):
            shutil.rmtree(out_dir, ignore_errors=True)
            return response

        return send_file(
            str(pdf_path),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="cv.pdf",
        )
    except Exception as exc:
        shutil.rmtree(out_dir, ignore_errors=True)
        flash(f"Error generating PDF: {exc}", "error")
        return redirect(url_for("download_page"))


# ---------------------------------------------------------------------------
# API: clear session
# ---------------------------------------------------------------------------


@app.route("/api/session/clear", methods=["POST"])
def session_clear():
    upload_dir = session.get("upload_dir")
    if upload_dir:
        shutil.rmtree(upload_dir, ignore_errors=True)
    session.clear()
    flash("Session cleared.", "success")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_dev():
    app.run(debug=True, host="127.0.0.1", port=5000)


if __name__ == "__main__":
    run_dev()
