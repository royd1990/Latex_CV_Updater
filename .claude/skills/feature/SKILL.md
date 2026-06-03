---
name: feature
description: Add a new feature to the project. Handles branch creation, planning, implementation, testing, and PR. Use when starting any new feature work.
argument-hint: [feature description]
disable-model-invocation: true
allowed-tools: Bash(git *) Bash(pytest *) Bash(python -m pytest *) Bash(pip install *) Bash(python *) Read Edit Write Glob Grep Agent
effort: high
---

# New Feature Workflow

You are executing the **feature** skill. Follow every checkpoint below in order. Do NOT skip steps. Ask the user before proceeding at each confirmation point.

The feature request is: **$ARGUMENTS**

---

## Checkpoint 1: Interpret Feature Name

- Derive a short, kebab-case branch name from the feature description (e.g., `web-dashboard`, `pdf-export`, `auth-middleware`).
- Present the interpreted name to the user: _"I'll name the branch `feature/<name>`. Does that work?"_
- Wait for confirmation. If the user suggests a different name, use that instead.

## Checkpoint 2: Verify Clean Working Tree

- Run `git status` to check for uncommitted changes.
- If the working tree is dirty, **stop and warn the user**. Ask whether to:
  - Stash changes (`git stash`)
  - Commit them first
  - Abort the skill
- Do NOT proceed with a dirty working tree.

## Checkpoint 3: Choose Base Branch

- Show the user the current branch and list available local branches.
- Ask: _"Which branch should I base the feature branch on?"_ (suggest `main` as default)
- Wait for confirmation.

## Checkpoint 4: Branch Strategy

- Ask the user: _"Create a new branch `feature/<name>` from `<base>`, or continue working on the current branch?"_
- If creating a new branch:
  - `git checkout <base>` and `git pull origin <base>` to ensure it's up to date.
  - `git checkout -b feature/<name>`
- If continuing on the current branch, confirm and proceed.

## Checkpoint 5: Explore and Plan

Before writing any code:

1. **Explore the codebase** — read relevant files, understand the architecture and existing patterns.
2. **Draft an implementation plan** — outline:
   - Which files will be created or modified
   - Key design decisions and trade-offs
   - Any new dependencies required
   - How the feature integrates with existing code
3. **Present the plan** to the user and ask for approval.
4. Do NOT write code until the plan is approved.

## Checkpoint 6: Implement

- Write the code following the approved plan.
- Follow existing code conventions and patterns found in the codebase.
- Keep changes focused — do not refactor unrelated code.
- If you discover the plan needs adjustment during implementation, pause and discuss with the user before continuing.

## Checkpoint 7: Run Tests

After implementation is complete:

1. Look for existing test infrastructure (pytest, unittest, test directories, CI config).
2. **Write tests** for the new feature if a test suite exists.
3. Run the full test suite:
   - `python -m pytest` (or whatever test runner the project uses)
4. If tests fail:
   - Diagnose and fix the failures.
   - Re-run tests until they pass.
   - Show the user the passing test output.
5. If no test infrastructure exists, inform the user and ask whether to set one up or skip.

## Checkpoint 8: Lint and Format (if applicable)

- Check for linter/formatter configs (`.flake8`, `pyproject.toml [tool.ruff]`, `.eslintrc`, `prettier`, etc.).
- If found, run the linter/formatter and fix any issues.
- If none found, skip this step.

## Checkpoint 9: Commit

- Stage only the relevant changed files (no `git add -A`).
- Draft a conventional commit message summarizing the feature.
- Show the commit message to the user for approval before committing.
- Commit using the approved message.

## Checkpoint 10: Offer PR Creation

- Ask the user: _"Would you like me to push the branch and create a pull request?"_
- If yes:
  - Push: `git push -u origin feature/<name>`
  - Create PR using `gh pr create` with a summary of changes and test plan.
  - Return the PR URL to the user.
- If no, inform the user how to push/PR manually when ready.

---

## General Rules

- **Always ask before acting** on anything destructive or irreversible.
- **Never force-push** or use `--no-verify`.
- **Show progress** — give brief status updates at each checkpoint.
- If at any point the user wants to abort, cleanly exit (offer to delete the branch if it was just created).
