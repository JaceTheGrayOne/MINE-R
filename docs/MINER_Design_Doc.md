# MINE-R: Technical Design Document

## Project Overview

**MINE-R** (Modular Interactive Node Extraction and Retrieval) is an automated data mining pipeline for the video game **Grounded 2**. The system extracts game data from Unreal Engine 5 asset files (.pak/.utoc/.ucas) and transforms it into a structured SQLite database for use in external applications such as wikis, companion apps, or data analysis tools.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    MINE-R Data Pipeline                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [1] IoStore → Legacy    [retoc]                            │
│       ↓                                                      │
│  [2] Filter DataTables   [PowerShell]                       │
│       ↓                                                      │
│  [3] UAsset → JSON       [UAssetAPI + C#]                   │
│       ↓                                                      │
│  [4] Process Manifest    [Python + SHA-256]                 │
│       ↓                                                      │
│  [5] Update Database     [Python + SQLite]                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## System Components

### 1. Data Extraction Layer

#### 1.1 IoStore to Legacy Conversion
**Script**: `scripts/1_convert_iostore.ps1`
**Tool**: `retoc.exe` (Unreal Engine asset extractor)

**Purpose**: Converts modern UE5 IoStore container format (.pak/.utoc/.ucas) to legacy asset format (.uasset/.uexp).

**Configuration**:
- **Engine Version**: UE5_4
- **Source**: Steam game installation directory
- **Output**: `legacy_assets/` directory
- **AES Key**: Optional encryption key for protected assets

**Process**:
1. Validates retoc.exe and game directory paths
2. Clears previous legacy assets directory
3. Executes retoc with `to-legacy` command
4. Produces directory tree of .uasset/.uexp files

**Dependencies**:
- retoc.exe (third-party tool for Unreal asset conversion)
- Valid Grounded 2 game installation

---

#### 1.2 DataTable Filtering
**Script**: `scripts/2_filter_datatables.ps1`

**Purpose**: Filters and copies only relevant DataTable files from the massive asset extraction, reducing processing time and storage.

**Filter Patterns**:
- `DT_*.uasset` - DataTable assets
- `Table_*.uasset` - Table assets
- `Text_enus.uasset` - Localization data

**Process**:
1. Scans `legacy_assets/Augusta/Content/` recursively
2. Matches files against filter patterns
3. Copies matched .uasset files with companion .uexp files
4. Preserves directory structure in `datatables_filtered/`

**Output**: ~196 filtered DataTable files (based on manifest.json)

---

### 2. Data Transformation Layer

#### 2.1 UAsset to JSON Conversion
**Script**: `scripts/3_convert_uassets.ps1`
**Tool**: Custom C# application (`tools/uasset_converter/`)

**Purpose**: Converts binary UAsset files to structured JSON using UAssetAPI.

**Configuration**:
- **Engine Version**: VER_UE5_4
- **Mapping File**: `tools/mappings/Grounded2.usmap` (property schema)
- **Converter**: `UAssetToJson.exe` (.NET 8.0 application)

**C# Converter Architecture**:
```
UAssetToJson.exe
├── UAssetAPI.dll (core library - compiled from source)
├── Dependencies:
│   ├── Newtonsoft.Json v13.0.3
│   └── ZstdSharp.Port v0.8.1 (compression)
```

**Process**:
1. Iterates through all .uasset files in `datatables_filtered/`
2. For each file:
   - Loads with UAssetAPI using engine version and .usmap mapping
   - Parses binary structures into object model
   - Serializes to JSON with full fidelity
3. Outputs to `json_staging/` preserving directory structure
4. Tracks success/failure counts

**Error Handling**: Continues on individual file failures, reports summary at end

---

### 3. Change Detection Layer

#### 3.1 Manifest Processing
**Script**: `scripts/4_process_manifest.py`

**Purpose**: Implements incremental processing by detecting which JSON files are new, updated, or deleted since the last run.

**Algorithm**:
```python
1. Load old manifest (manifest.json)
2. Scan json_staging/ directory
3. For each JSON file:
   - Load and parse JSON
   - Create canonical representation (sorted keys, no whitespace)
   - Compute SHA-256 hash
4. Compare hashes:
   - New files: in new_manifest but not old_manifest
   - Updated files: different hash between manifests
   - Deleted files: in old_manifest but not new_manifest
5. Write results:
   - manifest.json (complete new manifest)
   - files_add.json (new files)
   - files_update.json (changed files)
```

**Benefits**:
- Skips unchanged files in database update
- Detects game updates automatically
- Ignores formatting-only changes (whitespace, key order)

---

### 4. Data Storage Layer

#### 4.1 Database Schema
**Script**: `scripts/0_setup_database.py`
**Database**: `database/grounded_data.db` (SQLite 3)

**Entity-Relationship Model**:

```
┌──────────────┐       ┌─────────────────────┐       ┌───────────────┐
│    Items     │◄──────┤ Item_StatusEffects  ├──────►│StatusEffects  │
└──────┬───────┘       └─────────────────────┘       └───────────────┘
       │
       │
       ├───────────┐
       │           │
┌──────▼─────┐  ┌─▼────────────────┐  ┌──────────────┐
│  Recipes   │  │ ArmorSet_Items   ├──►│  ArmorSets   │
└────┬───────┘  └──────────────────┘  └──────┬───────┘
     │                                         │
┌────▼──────────────────┐          ┌──────────▼───────────┐
│ Recipe_Ingredients    │          │ ArmorSet_Effects     │
└───────────────────────┘          └──────────────────────┘
```

**Tables**:

**Items**
- `key` TEXT PRIMARY KEY - Unique item identifier (e.g., "Item_Armor_Ladybug_Head")
- `name` TEXT - Localized display name
- `icon_path` TEXT - Web path to icon image
- `tier` INTEGER - Equipment tier (0-9)
- `slot` TEXT - Equipment slot (Head, Chest, Legs, etc.)
- `durability` REAL - Item durability value
- `flat_damage_reduction` REAL - Armor value
- `percentage_damage_reduction` REAL - % damage reduction

**StatusEffects**
- `key` TEXT PRIMARY KEY - Effect identifier
- `name` TEXT - Localized display name
- `icon_path` TEXT - Web path to icon image

**ArmorSets**
- `key` TEXT PRIMARY KEY - Set identifier
- `name` TEXT - Derived set name (e.g., "Ladybug Armor")
- `tier` INTEGER - Set tier
- `class` TEXT - Armor class (Rogue, Fighter, Ranger, Mage)

**Join Tables**:
- `Item_StatusEffects` - Links items to their effects (with is_hidden flag)
- `ArmorSet_Items` - Links sets to component items
- `ArmorSet_Effects` - Links sets to set bonuses
- `Recipe_Ingredients` - Links recipes to required materials

---

#### 4.2 Database Update Process
**Script**: `scripts/5_update_database.py`

**Purpose**: Parses JSON files and populates/updates the SQLite database.

**Key Features**:

1. **Localization System**
   - Loads `Text_enus.json` into memory at startup
   - Provides `get_localized_string()` function
   - Maps StringTableID/StringID pairs to display text
   - String table mappings:
     - 1: game/gui
     - 2: game/items
     - 9: game/characters
     - 33: game/statuseffects
     - 195: game/perks

2. **Asset Path Translation**
   - Converts UE asset paths to web URLs
   - Handles `/Game/` and `/Augusta/Content/` prefixes
   - Example: `/Game/UI/Images/Items/icon.png` → `/media/UI/Images/Items/icon.png`

3. **Two-Pass Processing**
   - **Pass 1**: Core data (StatusEffects, Items, Recipes, etc.)
   - **Pass 2**: Relational data (ArmorSets - requires Items to exist first)

4. **Data Processing Functions**:
   - `process_status_effects()` - Parses Table_StatusEffects.json
   - `process_all_items()` - Parses Table_AllItems.json
   - `process_item_sets()` - Parses Table_ItemSets.json and derives metadata

**Derived Data Logic** (ArmorSets):
- **Name**: Finds common words across all item names in set
- **Tier**: Uses tier from set items (validates consistency)
- **Class**: Detects from status effect keys (e.g., "RogueFinisherCriticals" → "Rogue")

---

### 5. Orchestration Layer

#### 5.1 Master Pipeline
**Script**: `scripts/master_run.ps1`

**Purpose**: Executes entire pipeline in sequence with error handling.

**Execution Flow**:
```
1. Convert IoStore to Legacy Assets
2. Filter Data Tables
3. Convert UAssets to JSON
4. Process Manifest (Detect Changes)
5. Update Database
```

**Error Handling**:
- `$ErrorActionPreference = "Stop"` - Fail-fast on errors
- Try-catch wrapper around entire pipeline
- Reports which step failed
- Exit code 1 on failure for CI/CD integration

---

## Directory Structure

```
MINE-R/
├── scripts/
│   ├── master_run.ps1              # Pipeline orchestrator
│   ├── 0_setup_database.py         # Database schema creation
│   ├── 1_convert_iostore.ps1       # IoStore → Legacy
│   ├── 2_filter_datatables.ps1     # Filter relevant assets
│   ├── 3_convert_uassets.ps1       # UAsset → JSON
│   ├── 4_process_manifest.py       # Change detection
│   └── 5_update_database.py        # Database population
│
├── tools/
│   ├── retoc/
│   │   └── retoc.exe               # Asset extraction tool
│   ├── mappings/
│   │   └── Grounded2.usmap         # Property schema for UE5
│   ├── uasset_converter/
│   │   ├── Program.cs              # C# converter source
│   │   ├── uasset_converter.csproj # .NET project file
│   │   ├── lib/
│   │   │   └── UAssetAPI.dll       # UAssetAPI library
│   │   └── bin/Release/net8.0/
│   │       └── UAssetToJson.exe    # Compiled converter
│   └── UAssetAPI_source/           # UAssetAPI source code
│
├── database/
│   └── grounded_data.db            # SQLite database (output)
│
├── legacy_assets/                  # Step 1 output (large, ~GB)
├── datatables_filtered/            # Step 2 output (~196 files)
├── json_staging/                   # Step 3 output (structured JSON)
│
├── manifest.json                   # File hashes for change detection
├── files_add.json                  # New files list
├── files_update.json               # Updated files list
│
└── MINER_Design_Doc.md            # This document
```

---

## Data Flow

### Example: Item Processing

```
1. Source File:
   Grounded2/Augusta/Content/Paks/pakchunk0-*.pak

2. After Step 1 (retoc):
   legacy_assets/Augusta/Content/Blueprints/Items/Table_AllItems.uasset

3. After Step 2 (filter):
   datatables_filtered/Blueprints/Items/Table_AllItems.uasset

4. After Step 3 (UAssetToJson):
   json_staging/Blueprints/Items/Table_AllItems.json

5. After Step 4 (manifest):
   Entry in manifest.json with SHA-256 hash

6. After Step 5 (database):
   Row in Items table:
   {
     key: "Item_Armor_Ladybug_Head",
     name: "Ladybug Helmet",
     icon_path: "/media/UI/Images/Items/T_UI_Item_Ladybug_Head.png",
     tier: 2,
     slot: "Head",
     durability: 1000.0,
     flat_damage_reduction: 15.0,
     percentage_damage_reduction: 0.0
   }
```

---

## Technology Stack

### Languages & Frameworks
- **PowerShell 5.1+**: Windows automation, file operations
- **Python 3.8+**: Data processing, database operations
- **C# / .NET 8.0**: Binary asset parsing

### Libraries & Dependencies
- **UAssetAPI**: Unreal Engine asset parsing library
- **Newtonsoft.Json**: JSON serialization
- **ZstdSharp.Port**: Compression support
- **SQLite3**: Database engine (via Python sqlite3 module)

### External Tools
- **retoc.exe**: Third-party Unreal Engine asset extractor

---

## Performance Characteristics

### Processing Times (Estimated)
- **Step 1** (IoStore Conversion): ~10-30 minutes (depends on game size)
- **Step 2** (Filtering): ~5-10 seconds (196 files from thousands)
- **Step 3** (JSON Conversion): ~2-5 minutes (196 files)
- **Step 4** (Manifest): ~5-10 seconds (hash computation)
- **Step 5** (Database Update): ~10-30 seconds (SQL operations)

**Total Pipeline**: ~15-35 minutes (first run), ~3-6 minutes (incremental updates)

### Storage Requirements
- **legacy_assets/**: ~1-5 GB (temporary, can be deleted)
- **datatables_filtered/**: ~10-50 MB
- **json_staging/**: ~20-100 MB
- **database/**: ~5-20 MB (compressed SQLite)

---

## Incremental Update Strategy

The system uses content-based change detection:

1. **Manifest File** (`manifest.json`): Maps file paths to SHA-256 hashes
2. **Hash Computation**: JSON canonical form (sorted keys, no whitespace)
3. **Change Detection**: Compares old vs. new manifest
4. **Selective Processing**: Only processes new/changed files in Step 5

**Benefits**:
- Skips database updates for unchanged data
- Detects game patches automatically
- Handles file renames/moves
- Ignores formatting-only changes

**Example Manifest Entry**:
```json
{
  "Blueprints\\Items\\Table_AllItems.json": "bc567cbf62a1b7f978508e1ee7b4a0ed5c5fe000f4079e15f19773363c3fc60d"
}
```

---

## Error Handling & Reliability

### Script-Level Error Handling
- **PowerShell**: `$ErrorActionPreference = "Stop"` + try-catch blocks
- **Python**: Exception handling with detailed error messages
- **C#**: Try-catch with exit codes

### Failure Recovery
1. **Step 1-3 Failures**: Pipeline stops, preserves existing outputs
2. **Step 4-5 Failures**: Database remains in last consistent state
3. **Partial File Failures**: Continues processing remaining files, reports summary

### Validation Checks
- Path existence validation before operations
- File count reporting at each stage
- Success/failure counters for batch operations
- Database foreign key constraints

---

## Configuration Management

### Centralized Configuration Locations

**1_convert_iostore.ps1**:
- `$RETOC_EXE_PATH`: Path to retoc.exe
- `$GAME_PAKS_PATH`: Grounded 2 installation directory
- `$UE_VERSION`: Unreal Engine version (UE5_4)
- `$AES_KEY`: Encryption key (if required)

**3_convert_uassets.ps1**:
- `$CONVERTER_EXE`: Path to UAssetToJson.exe
- `$ENGINE_VERSION`: UE version for UAssetAPI (VER_UE5_4)
- `$USMAP_PATH`: Path to Grounded2.usmap

**5_update_database.py**:
- `STR_TABLES_BY_ID`: String table ID mappings
- `ARMOR_CLASSES`: Effect key to class mappings
- `WEB_MEDIA_ROOT`: Base path for web assets (/media/)

---

## Extension Points

### Adding New Data Types

**Step 1**: Define database schema in `0_setup_database.py`
```python
c.execute('''
CREATE TABLE IF NOT EXISTS NewDataType (
    key TEXT PRIMARY KEY,
    name TEXT,
    ...
)''')
```

**Step 2**: Create parser function in `5_update_database.py`
```python
def process_new_data_type(filepath, conn):
    # Parse JSON and insert into database
    pass
```

**Step 3**: Add router logic in `main()`
```python
if "Table_NewDataType.json" in relative_path:
    process_new_data_type(filepath, conn)
```

### Adding New Filters
Modify `2_filter_datatables.ps1`:
```powershell
$filterPatterns = @("DT_*.uasset", "Table_*.uasset", "NewPattern_*.uasset")
```

---

## Security Considerations

### Input Validation
- File path validation (prevents directory traversal)
- JSON parsing errors handled gracefully
- SQL injection prevention (parameterized queries)

### Access Control
- Database uses local filesystem permissions
- No network exposure by default
- AES key stored in configuration (not committed to repo)

### Data Integrity
- Foreign key constraints in database
- Transaction-based database updates
- Manifest-based change detection prevents corruption

---

## Known Limitations

1. **Game Version Dependency**: Requires matching .usmap file for each game update
2. **Windows-Only**: PowerShell scripts require Windows (WSL possible with modifications)
3. **Manual .usmap Updates**: Property mappings must be updated for new game versions
4. **Limited Data Types**: Currently extracts Items, StatusEffects, ArmorSets (extensible)
5. **No Real-time Updates**: Manual pipeline execution required
6. **Localization**: English-only (enus) localization currently supported

---

## Future Enhancements

### Planned Features
1. **Additional Data Types**:
   - Creatures/Bestiary (`Table_Bestiary.json`)
   - Crafting Recipes (`Table_CraftingRecipes.json`)
   - Perks (`Table_Perks.json`)
   - Quests (`Table_Quests_ALL.json`)

2. **Multi-language Support**:
   - Parse all language files from `Exported/Release_*/Localized/`
   - Add language column to database tables

3. **Asset Extraction**:
   - Extract and convert texture assets (icons)
   - Build web-ready asset library

4. **Automation**:
   - Windows Task Scheduler integration
   - Auto-detect game updates via Steam API
   - Automatic .usmap download from community repositories

5. **Data Export**:
   - REST API for database access
   - JSON export endpoints
   - Static site generation from database

---

## Maintenance Guide

### Regular Maintenance Tasks

**After Game Update**:
1. Acquire updated `Grounded2.usmap` from community (e.g., FModel Discord)
2. Place in `tools/mappings/`
3. Run `scripts/master_run.ps1`
4. Verify output in database

**Periodic Cleanup**:
```powershell
# Optional: Clear intermediate files to save space
Remove-Item -Recurse legacy_assets/
Remove-Item -Recurse datatables_filtered/
# json_staging is needed for incremental updates (keep it)
```

**Database Rebuild**:
```powershell
# Full rebuild (clears manifest)
python scripts/0_setup_database.py
Remove-Item manifest.json, files_add.json, files_update.json
.\scripts\master_run.ps1
```

### Troubleshooting

**"Converter tool not found"**:
- Build C# project: `dotnet build tools/uasset_converter/ -c Release`

**"No old manifest found"**:
- Expected on first run, can be ignored

**"Failed to convert [file].uasset"**:
- Check that .usmap file matches game version
- Verify UAssetAPI supports the asset type
- Check C# application logs

**Database schema errors**:
- Delete `database/grounded_data.db`
- Re-run `0_setup_database.py`

---

## References

### External Dependencies
- **UAssetAPI**: https://github.com/atenfyr/UAssetAPI
- **retoc**: Community Unreal Engine asset tool
- **FModel**: Community asset extraction tool (for obtaining .usmap files)

### Game Information
- **Grounded 2**: Obsidian Entertainment
- **Engine**: Unreal Engine 5.4
- **Platform**: Steam (Windows)

---

## Glossary

- **DataTable**: Unreal Engine asset type for structured data (like CSV/database in-engine)
- **IoStore**: Modern UE5 container format (.pak/.utoc/.ucas) with optimized streaming
- **Legacy Format**: Older UE asset format (.uasset/.uexp) easier to parse
- **.usmap**: Unreal Mappings file - contains property names/types for assets
- **Manifest**: Change-tracking file using content hashes
- **Canonical JSON**: Standardized JSON representation (sorted, compact) for hashing
- **Status Effect**: Gameplay buff/debuff applied by items or abilities
- **Armor Set**: Collection of equipment items that grant bonuses when worn together

---

## Version History

- **v1.0** (2025-01-12): Initial technical design document

---

## Contact & Support

For issues, feature requests, or contributions, please refer to the project repository.
