# LaTeX CV Updater

Interactive CLI app for creating and updating LaTeX CVs that use the `curve` document class.

## What this project does

- Parses CV section files (`.tex`) into structured Python models
- Lets you edit entries interactively from a terminal UI
- Regenerates section files from templates
- Optionally compiles the CV to PDF

Main package: `cv_updater/`
Example CV source folder: `Deba_CV/`

## Prerequisites

- Python 3.9+
- [uv](https://docs.astral.sh/uv/)
- LaTeX tools for PDF compilation:
  - `xelatex` (preferred), or `lualatex`/`pdflatex`
  - `biber`

### Install LaTeX tools

Linux (Debian/Ubuntu):

```bash
sudo apt update
sudo apt install -y texlive-xetex texlive-latex-extra biber
```

macOS:

```bash
brew install --cask mactex
```

## Setup with uv

From the project root:

```bash
uv sync
```

This installs runtime dependencies from `pyproject.toml` into the project environment.

## Run the app with uv

Use either command:

```bash
uv run cv-updater
```

or

```bash
uv run python -m cv_updater
```

## How to use

When launched, the app will:

1. Check LaTeX prerequisites
2. Ask for a CV directory path (defaults to `Deba_CV/`)
3. Ask whether to:
   - Update existing CV
   - Create new CV
4. Generate updated section files
5. Optionally compile `cv-llt.tex` into a PDF

## Manual compile command

If you skip compilation in the app, run this manually inside your CV directory:

```bash
xelatex cv-llt.tex && biber cv-llt && xelatex cv-llt.tex && xelatex cv-llt.tex
```

## Project layout

```text
cv_updater/
  cli.py
  parser.py
  generator.py
  compiler.py
  models.py
  templates/
Deba_CV/
  cv-llt.tex
  employment.tex
  education.tex
  skills.tex
  misc.tex
  referee.tex
```
