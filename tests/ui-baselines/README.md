Approved screenshot baselines for the Playwright UI review test live in this folder.

Workflow:
- Run `set UI_REVIEW_APPROVE=1` before the screenshot test when you want to approve a new visual baseline.
- Run the test normally without that env var to compare current UI output against the approved baseline.
- Fresh capture artifacts are written to `tests/.artifacts/ui-review/` for manual inspection.