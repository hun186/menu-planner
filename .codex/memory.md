# Project Memory

- 2026-06-08: Excel export menu sheet now includes a daily `人數` column after `日期`/`週幾`, resolving values from `day.procurement.people`, `cfg.schedule.people_overrides` by date/index, then `cfg.people` fallback.
- 2026-06-08: Excel export sheets use content-based column width calculation (`auto_fit_columns`) with East Asian character width handling and max-width caps instead of fixed widths.
- 2026-06-08: Planner page subtitle describes flexible menu role counts, prep-time limits, and newer constraints.

- 2026-06-08: Refined the planner page subtitle to explicitly call out per-role daily quantities, weekday overrides, prep-time limits, explainable scoring, and Excel export.
- 2026-06-08: Added a column visibility panel to the planner result table so users can hide/show any result column. Column visibility uses per-column data markers, updates explanation-row colspan dynamically, and persists hidden columns in localStorage.
- 2026-06-08: Validation for result-column hiding passed targeted Node UI static tests; full UI static suite still has the two pre-existing `test_index_allowed_weekdays.mjs` expectation failures. Playwright browser validation remained blocked because Chromium binaries cannot be installed through the proxy-blocked apt repositories.
