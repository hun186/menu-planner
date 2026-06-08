# Technical Decisions

- 2026-06-08: Menu-sheet people values should prefer already-enriched procurement data so UI-edited per-day people counts are preserved on export; config overrides remain the fallback for days without procurement details.
- 2026-06-08: Excel column auto-fit is implemented in Python by estimating display width, counting wide/fullwidth East Asian characters as two columns and capping very long columns to keep JSON/help text manageable.
