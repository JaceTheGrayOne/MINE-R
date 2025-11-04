> # Grounded 2 Data Pipeline: Guiding Principles
>
> You are an expert data pipeline engineer. Our goal is to build and maintain an automated data pipeline to extract data from the game Grounded 2 and populate a SQLite database for a web frontend.
>
> ## Core Project Structure
>
> All file paths are relative to the project root.
>
> * `/scripts/`: All automation scripts (.ps1, .py).
> * `/raw_extracted/`: Raw output from Retoc.
> * `/datatables_filtered/`: Filtered `.uasset` data tables.
> * `/json_staging/`: Converted `.json` data tables.
> * `/database/grounded_data.db`: The final SQLite database.
> * `/manifest.json`: The manifest of processed JSON content hashes.
> * `/frontend/`: The web application.
>
> ## The 5-Script Workflow
>
> 1.  **`1_extract_gamedata.ps1`:** Runs Retoc, extracts all to `/raw_extracted/`.
> 2.  **`2_filter_datatables.ps1`:** Filters `DT_` and `*Table*` files from `/raw_extracted/` to `/datatables_filtered/`.
> 3.  **`3_convert_uassets.py`:** Uses `uassetapi` to convert files from `/datatables_filtered/` to `/json_staging/`.
> 4.  **`4_process_manifest.py`:** Reads `/json_staging/`, runs **Canonical Content Hash** on all JSONs, compares to `manifest.json`, and outputs `files_add.json` and `files_update.json`.
> 5.  **`5_update_database.py`:** Reads the "to-do" lists, parses the relevant JSONs from `/json_staging/`, and uses `INSERT OR REPLACE` to update `database/grounded_data.db`.
>
> ## Critical Rules
>
> 1.  **Change Detection:** We **NEVER** use file timestamps or standard hashes on `.uasset` files due to Unreal Engine offset changes. We **ONLY** use the "Canonical Content Hash" method on the JSON files in `/json_staging/`.
> 2.  **Database:** The SQLite DB is the final source of truth. All data updates **MUST** use `INSERT OR REPLACE INTO` (upsert) to handle both new and changed data.
> 3.  **Data Parsing:** Logic for parsing (like finding set names or classes) should be adapted from the `Sparrows Crawler Explanation.docx` file.
> 4.  **Media Paths:** All image/icon paths stored in the database **MUST** be web-accessible URLs (e.g., `/media/UI/Icons/icon.png`), not local file paths. The `build_web_asset_path` function in `5_update_database.py` is responsible for this.
> 5.  **Idempotency:** All scripts should be "idempotent" (safe to re-run without causing errors).
