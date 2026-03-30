# Scoring Rules Reference

## Timing

- Notices with deadlines less than 7 days away are penalized and marked as not timing-viable.
- Notices older than 90 days can be suppressed by the default scan strategy.
- Missing deadline and publication date values reduce score and confidence.

## Positive Domains

- document and records management
- case handling and workflow orchestration
- correspondence and registry
- e-filing, forms, and public service flows
- e-government and institutional digitization
- audit, compliance, and retention
- interoperability where platform orchestration is central

## Keyword Matching Improvements

- keyword terms can be configured as plain phrases or structured terms with aliases
- matches can be scoped to `title`, `summary`, `buyer`, `metadata`, or the full notice
- title matches can receive extra weight where they are stronger intent signals
- ambiguous terms can require supporting context before they count
- acronym-style terms such as `BPM`, `DMS`, `EDMS`, and `ERP` can be matched more strictly
- keyword combination rules add deterministic bonus points when multiple F2-relevant domains appear together

## Negative Signals

- hardware-only and network equipment
- security-only procurement
- website-only or mobile-only delivery
- construction, logistics, vehicles, fuel
- staffing-only and hosting-only scopes
- isolated OCR or ERP-only scopes

## Platform Lock Logic

- hard lock terms create strong penalties and can force a `CONDITIONAL` or `NO` fit label
- soft lock terms are treated as qualification risks, not automatic exclusions
- openness wording offsets some lock risk where equivalent solutions seem acceptable

## Outputs

- Fit label: `YES`, `CONDITIONAL`, `NO`
- Priority: `HIGH`, `GOOD`, `WATCHLIST`, `IGNORE`
- Confidence: `HIGH`, `MEDIUM`, `LOW`
