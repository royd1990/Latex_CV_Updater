# LaTeX CV Updater

## Project Structure
- `Deba_CV/` — Existing LaTeX CV source using the `curve` document class
- `cv_updater/` — Python package: interactive CLI agent for CV editing
  - `models.py` — Dataclasses for all CV sections
  - `parser.py` — Regex-based parser: `.tex` → models
  - `generator.py` — Jinja2-based generator: models → `.tex`
  - `compiler.py` — LaTeX compilation orchestration
  - `cli.py` — Interactive CLI (update or create mode)
  - `templates/` — Jinja2 templates for each section

## LaTeX Syntax (curve class)
- Entries use `\entry*[key]` — the `*` variant omits the prefix marker
- Employment/Education: `\entry*[2021 -- $\cdots\cdot$]%` + tab-indented content
- Skills: `\entry*[Label]\n\tContent` (no `%` after bracket)
- Present date marker: `$\cdots\cdot$`
- Section wrapper: `\begin{rubric}{Title} ... \end{rubric}`
- Sub-sections: `\subrubric{Name}`
- Main doc includes sections via `\makerubric{filename}` (without `.tex`)
- `%` lines between entries prevent extra whitespace

## Compilation
```bash
cd Deba_CV && xelatex cv-llt.tex && biber cv-llt && xelatex cv-llt.tex && xelatex cv-llt.tex
```
Requires: xelatex (MacTeX), biber. Install: `brew install --cask mactex`

## Running
```bash
pip install -e .
python -m cv_updater
```
