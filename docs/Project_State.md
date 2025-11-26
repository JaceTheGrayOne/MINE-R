# Project State

## Snapshot
- Core extract/transform/load pipeline from the design doc exists: `scripts/0_setup_database.py`, `scripts/1_convert_iostore.ps1`, `scripts/2_filter_datatables.ps1`, `scripts/3_convert_uassets.ps1`, `scripts/4_process_manifest.py`, `scripts/5_update_database.py`, and orchestrator `scripts/master_run.ps1`. The C# converter (`tools/uasset_converter/Program.cs`) is built (`tools/uasset_converter/bin/Release/net8.0/UAssetToJson.exe`) with required dependencies and `tools/mappings/Grounded2.usmap` + `tools/retoc/retoc.exe` are present.
- Working directories are empty (0 files in `legacy_assets/`, `datatables_filtered/`, `json_staging/`), so no extracted assets or converted JSON are currently available. The SQLite database `database/grounded_data.db` exists but all tables are empty.
- `manifest.json` still contains hashes from a prior run, but because the staging directory is empty, `files_add.json` and `files_update.json` are empty; rerunning the manifest step now would wipe the manifest to empty and process nothing.
- Update logic currently ingests only StatusEffects, Items, and ItemSets; recipe handling is schema-only and no other DataTables are wired in. No frontend or API surface is present.
- The AI-driven AN-T normalization pipeline described in `resources/AI-Driven Game Data Normalization Pipeline.md` has not been started: no enrichment scripts, schema extensions, Gemini/embedding dependencies, caching, or JSON-LD output exist.

## Alignment with MINE-R Design Doc
- Implemented: All five pipeline stages and the master orchestrator are present with configuration placeholders (e.g., `1_convert_iostore.ps1` points to `E:\SteamLibrary\...` and leaves `$AES_KEY` blank). The UAsset converter is compiled, the `.usmap` mapping is included, and the SQLite schema matches the design tables (Items, StatusEffects, ArmorSets, join tables, Recipes).
- Partially done: Database updater (`scripts/5_update_database.py`) routes only `Table_StatusEffects.json`, `Table_AllItems.json`, and `Table_ItemSets.json`; other DataTables mentioned as extensible in the design doc (recipes, creatures, perks, quests, etc.) are not hooked up. Deletions are detected but not applied to the database.
- Not validated: No current asset drop is present, so the pipeline has not been exercised end-to-end in this workspace; DB contents are empty and staging outputs are missing.

## Alignment with AI-Driven Normalization Plan (AN-T)
- Not started: No implementation of deterministic parsers, heuristic/embedding-based set clustering, Gemini-based classification/extraction, caching layer, JSON-LD emitter, or normalized schema changes (Armor weight, damage types, Item_Effects, Item_DamageTypes, etc.).
- Existing schema and loader remain in the pre-AN-T shape; `master_run.ps1` does not call any enrichment step.

## Work Remaining
- Provide source assets and rerun stages 1–3 to repopulate `legacy_assets/`, `datatables_filtered/`, `json_staging/`; regenerate `manifest.json`, `files_add.json`, `files_update.json`, and load data into `database/grounded_data.db`.
- Extend the ETL router to cover additional DataTables (recipes, perks, quests, creatures, localization variants) and handle deletions so the DB mirrors the manifest.
- Design and implement the AN-T pipeline from the normalization plan: deterministic parsing utilities, fuzzy/embedding clustering for armor sets, Gemini-backed classifiers/extractors with caching, schema migrations for normalized tables, JSON-LD output, and orchestration integration.
- Add validation and automation (unit tests around parsers, lightweight integration test of the pipeline, optional CI script) plus operational docs for configuring paths/AES keys and running `scripts/master_run.ps1`.
