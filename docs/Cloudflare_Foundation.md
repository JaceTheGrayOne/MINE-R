Here we go — merged, polished, and aimed straight at Codex’s brain.

Below is the **implementation document itself**, not a prompt. It’s written *for* an IDE agent like Codex to follow step-by-step, but still understandable to you as a human.

---

# Grounded 2 Wiki – Cloudflare Implementation Master Plan

*For the MINE-R + AN-T pipeline*

This document defines the full implementation plan for deploying the Grounded 2 wiki stack on **Cloudflare D1, Workers, and Pages**, powered by the existing **MINE-R** extraction pipeline and **AN-T** normalization pipeline.

It is intended to be executed by an AI coding agent (e.g., OpenAI Codex in VS Code) with human supervision. Wherever manual credentials or decisions are required, the agent must explicitly ask the user.

---

## 1. System Overview

### 1.1 Existing Components (Local)

* **MINE-R**: Extracts Unreal Engine 5 assets → JSON → SQLite (`grounded_data.db`). 
* **AN-T**: Enrichment pipeline that:

  * Parses object paths and enums deterministically
  * Infers armor sets / classes with heuristics & clustering
  * Uses Gemini to fill in ambiguous stats/effects
  * Outputs a normalized relational model suitable for a wiki schema. 

The result is a **clean, normalized dataset** stored in a local SQLite DB and/or JSON-LD, representing items, armor sets, effects, damage types, and recipes.

### 1.2 New Cloudflare Stack

We will build:

* **Cloudflare D1** – Serverless SQLite database for the wiki.
* **Cloudflare Workers** – REST API layer using the **Hono** framework.
* **Cloudflare Pages** – React SPA (Vite + TS) frontend.
* **Ingestion Script** – Moves AN-T’s normalized data into D1 in batched, idempotent fashion.

High-level flow:

```mermaid
graph TD
  ANT[AN-T Output (SQLite / JSON)] -->|Ingestion Script| D1[Cloudflare D1 (Wiki DB)]
  D1 -->|SQL Queries| Worker[Cloudflare Worker API (Hono)]
  User[Player / Web User] -->|HTTPS| Pages[Cloudflare Pages Frontend]
  Pages -->|Fetch JSON| Worker
```

---

## 2. Prerequisites & Platform Constraints

Before implementation, the following must be true:

* Cloudflare account exists and is accessible.
* Node.js ≥ 18 is installed locally.
* `wrangler` CLI is installed globally (`npm install -g wrangler`).
* Existing MINE-R repo structure is in place with working pipeline that produces `grounded_data.db` and/or normalized export. 

Cloudflare constraints relevant to this design:

* **D1 size**: ~500MB (free) / 10GB (paid) per DB — fine for text/relational data, but we don’t store binary icons inside D1.
* **D1 import**: Bulk SQL must be batched (we’ll chunk INSERTs).
* **Workers**: Limited CPU/time per request — we avoid heavy computation in Workers and let D1 handle relational joins.
* **FTS5**: Supported for search in SQLite; we’ll use a virtual table for `Items_Search`.

---

## 3. Repository Layout

We will extend the existing `MINE-R/` repo with a `web/` subtree and an `ingest/` folder.

**Target structure (simplified):**

```plaintext
MINE-R/
├── scripts/                      # Existing MINE-R pipeline
├── tools/                        # Existing tools
├── database/                     # Existing local SQLite from MINE-R/AN-T (grounded_data.db)
├── web/                          # NEW: Cloudflare code
│   ├── api/                      # Worker API (Hono)
│   │   ├── src/
│   │   ├── wrangler.toml
│   │   └── package.json
│   ├── frontend/                 # Pages frontend (React + Vite + TS)
│   │   ├── src/
│   │   ├── public/
│   │   └── package.json
│   └── database/                 # D1 schema & migrations
│       ├── schema.sql
│       └── migrations/
└── ingest/
    └── deploy_to_d1.py           # Ingestion script (local → D1)
```

> **Codex note:** All paths in this document are relative to the repo root (`MINE-R/`).

---

## 4. D1 Schema Design

The D1 schema is derived from:

* The normalized ontology described in AN-T Section 6.1 
* The current MINE-R SQLite schema 

### 4.1 Core Entities

We will implement:

* `StatusEffects`
* `ArmorSets`
* `Items`
* `Item_Effects` (many-to-many)
* `Item_DamageTypes` (many-to-many)
* `Recipes` (optional but useful)

Future extension: `PatchNotes`, `Items_History`, etc.

### 4.2 Schema File

Codex must create `web/database/schema.sql` with the following content (this is the canonical “initial schema”):

```sql
-- 0000_initial.sql

PRAGMA foreign_keys = ON;

-- StatusEffects: canonical effects/perks from AN-T
CREATE TABLE IF NOT EXISTS StatusEffects (
    effect_id    TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT,
    category     TEXT,        -- 'positive', 'negative', 'set_bonus', etc.
    icon_path    TEXT         -- relative URL to icon asset
);

-- ArmorSets: named armor sets, plus set bonus linkage
CREATE TABLE IF NOT EXISTS ArmorSets (
    set_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    set_name             TEXT UNIQUE NOT NULL,
    set_bonus_effect_id  TEXT REFERENCES StatusEffects(effect_id)
);

-- Items: all player-facing items (armor, weapons, trinkets, etc.)
CREATE TABLE IF NOT EXISTS Items (
    item_id          TEXT PRIMARY KEY,    -- UE key or canonical ID
    name             TEXT NOT NULL,
    description      TEXT,
    icon_path        TEXT,
    tier             INTEGER,

    -- Classification (AN-T classification phases)
    item_class       TEXT,                -- e.g. 'Heavy Armor', '1H Sword'
    slot             TEXT,                -- e.g. 'Head', 'Upper Body', 'Accessory'

    -- Baseline stats (high-level)
    durability       REAL,
    dr_base          REAL,                -- flat damage reduction
    resistance_base  REAL,                -- percentage damage reduction

    -- Relationships
    armor_set_id     INTEGER REFERENCES ArmorSets(set_id),

    -- Versioning / patch tracking (optional, for diffs)
    version_added    TEXT,                -- e.g. '1.0.0'
    updated_at       TEXT                 -- ISO-8601 timestamp
);

-- Item_Effects: join table linking items to StatusEffects
CREATE TABLE IF NOT EXISTS Item_Effects (
    item_id   TEXT NOT NULL REFERENCES Items(item_id),
    effect_id TEXT NOT NULL REFERENCES StatusEffects(effect_id),
    source    TEXT NOT NULL,             -- 'Base', 'Sleek', 'Set Bonus', etc.
    PRIMARY KEY (item_id, effect_id, source)
);

-- Item_DamageTypes: damage types applied by weapons & armor
CREATE TABLE IF NOT EXISTS Item_DamageTypes (
    item_id     TEXT NOT NULL REFERENCES Items(item_id),
    damage_type TEXT NOT NULL,           -- e.g. 'Slashing', 'Spicy', 'Fresh'
    is_base_type BOOLEAN DEFAULT 1,
    PRIMARY KEY (item_id, damage_type)
);

-- Recipes (optional but useful for wiki)
CREATE TABLE IF NOT EXISTS Recipes (
    recipe_id       TEXT PRIMARY KEY,
    result_item_id  TEXT REFERENCES Items(item_id),
    amount          INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS Recipe_Ingredients (
    recipe_id       TEXT NOT NULL REFERENCES Recipes(recipe_id),
    ingredient_item_id TEXT NOT NULL REFERENCES Items(item_id),
    quantity        INTEGER NOT NULL,
    PRIMARY KEY (recipe_id, ingredient_item_id)
);

-- INDEXES for performance
CREATE INDEX IF NOT EXISTS idx_items_name ON Items(name);
CREATE INDEX IF NOT EXISTS idx_items_set ON Items(armor_set_id);
CREATE INDEX IF NOT EXISTS idx_effects_name ON StatusEffects(name);

-- FTS5 virtual table for search
CREATE VIRTUAL TABLE IF NOT EXISTS Items_Search
USING fts5(
    item_id,
    name,
    description,
    item_class,
    slot,
    content='Items',
    content_rowid='rowid'
);

-- Trigger: sync FTS on INSERT
CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON Items BEGIN
  INSERT INTO Items_Search(rowid, item_id, name, description, item_class, slot)
  VALUES (new.rowid, new.item_id, new.name, new.description, new.item_class, new.slot);
END;

-- Trigger: sync FTS on DELETE
CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON Items BEGIN
  INSERT INTO Items_Search(Items_Search, rowid, item_id, name, description, item_class, slot)
  VALUES ('delete', old.rowid, old.item_id, old.name, old.description, old.item_class, old.slot);
END;

-- Trigger: sync FTS on UPDATE
CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON Items BEGIN
  INSERT INTO Items_Search(Items_Search, rowid, item_id, name, description, item_class, slot)
  VALUES ('delete', old.rowid, old.item_id, old.name, old.description, old.item_class, old.slot);
  INSERT INTO Items_Search(rowid, item_id, name, description, item_class, slot)
  VALUES (new.rowid, new.item_id, new.name, new.description, new.item_class, new.slot);
END;
```

---

## 5. D1 Database Creation & Migrations

We will create a **single D1 instance** (e.g. `grounded-wiki-db`) and apply the schema.

### 5.1 Create the D1 Database

**Codex must:**

1. Ask the user for:

   * Desired Cloudflare D1 database name (default suggestion: `grounded-wiki-db`).
2. Instruct the user to run:

```bash
cd MINE-R
npx wrangler d1 create grounded-wiki-db
```

3. Capture the `database_id` output and tell the user to store it (we’ll put it into `wrangler.toml` for the API).

### 5.2 Apply Initial Schema

**Codex must:**

1. Instruct the user to apply the schema:

```bash
npx wrangler d1 execute grounded-wiki-db --file=web/database/schema.sql --remote
```

2. Confirm success by running a test query:

```bash
npx wrangler d1 execute grounded-wiki-db --remote --command="SELECT name FROM sqlite_master WHERE type='table';"
```

---

## 6. Ingestion Pipeline (Local → D1)

The ingestion pipeline will:

* Read from the local SQLite DB created by MINE-R/AN-T (`database/grounded_data.db`).
* Extract cleaned/normalized data for Items, ArmorSets, StatusEffects, etc.
* Generate **batched SQL** (`INSERT OR REPLACE`) for D1.
* Push batches via `wrangler d1 execute`.

### 6.1 Ingestion Script: Structure

File: `ingest/deploy_to_d1.py`

High-level logic:

1. Connect to `database/grounded_data.db`.
2. Query source tables (or views) representing normalized data from AN-T.
3. Transform into the D1 schema shape.
4. Build SQL strings with **proper escaping**.
5. Write SQL statements into temporary batch files (e.g. `temp_batch_001.sql`, `temp_batch_002.sql`, …).
6. For each batch file, run `npx wrangler d1 execute grounded-wiki-db --file=... --remote`.
7. Optionally verify row counts.

Codex should implement:

* Helper to escape `'` → `''` in strings.
* Chunk size (e.g. 200–500 INSERT statements per batch to avoid payload limits).

### 6.2 Idempotent Ingestion

The script must use:

```sql
INSERT OR REPLACE INTO Items (...)
VALUES (...);
```

Same for other tables, so re-running ingestion after a new MINE-R/AN-T run will just update rows, not create duplicates.

### 6.3 Optional Icons Handling

Phase 1 can simply assume icons are local and manually curated. Later, Codex can add:

* A step copying icons from a local asset export folder into `web/frontend/public/assets/`.
* Ensuring `icon_path` in D1 matches these URLs (e.g. `/assets/icons/items/<name>.png`).

---

## 7. Cloudflare Worker API (Hono)

### 7.1 API Directory Setup

Location: `web/api/`

Codex must:

1. Initialize a Node project:

```bash
cd MINE-R/web/api
npm init -y
npm install hono @cloudflare/workers-types
```

2. Create `web/api/wrangler.toml`:

```toml
name = "grounded-wiki-api"
main = "src/index.ts"
compatibility_date = "2025-01-01"

[[d1_databases]]
binding = "DB"
database_name = "grounded-wiki-db"
database_id = "<REPLACE_WITH_ACTUAL_ID>"
```

3. Add a basic `tsconfig.json` if needed for TypeScript.

### 7.2 API Endpoints

We will implement:

1. `GET /items`
2. `GET /items/:id`
3. `GET /armor-sets`
4. `GET /search`
5. (Optional) `GET /patch-diff/:version` (later phase)

#### 7.2.1 `GET /items`

* Query parameters:

  * `limit` (default 50)
  * `offset` (default 0)
  * `type` / `class` / `slot` filters (optional)
* Returns a paginated list of basic item info.

SQL shape (simplified):

```sql
SELECT item_id, name, tier, item_class, slot, icon_path
FROM Items
WHERE 1=1
  [AND item_class LIKE ?]
  [AND slot = ?]
ORDER BY name
LIMIT ? OFFSET ?;
```

#### 7.2.2 `GET /items/:id`

Returns **full item detail**, including:

* Item row (name, description, class, slot, stats).
* Related `ArmorSets` info (if applicable).
* Related `Item_Effects` + `StatusEffects`.
* Related `Item_DamageTypes`.

Codex can either:

* Run multiple queries and assemble JSON, or
* Use joins + aggregations and parse the result.

Example pattern:

```sql
SELECT
  i.*,
  asu.set_name
FROM Items i
LEFT JOIN ArmorSets asu ON i.armor_set_id = asu.set_id
WHERE i.item_id = ?;
```

Then:

```sql
SELECT se.effect_id, se.name, se.description, ie.source
FROM Item_Effects ie
JOIN StatusEffects se ON ie.effect_id = se.effect_id
WHERE ie.item_id = ?;
```

And:

```sql
SELECT damage_type, is_base_type
FROM Item_DamageTypes
WHERE item_id = ?;
```

Hono handler assembles these into a single JSON response.

#### 7.2.3 `GET /armor-sets`

Returns all armor sets with nested items.

* Query `ArmorSets`.
* For each set, query associated items from `Items`.
* Optional: include set bonus effect (join `StatusEffects`).

#### 7.2.4 `GET /search?q=...`

Search over `Items_Search`:

```sql
SELECT i.item_id, i.name, i.icon_path, i.item_class, i.slot
FROM Items_Search s
JOIN Items i ON i.rowid = s.rowid
WHERE Items_Search MATCH ?
LIMIT 20;
```

Codex must:

* Transform user query into an FTS expression (e.g. `q*` for prefix search).
* Sanitize input (no unescaped `'` in the query).

### 7.3 Hono App Skeleton

`web/api/src/index.ts` should:

* Create Hono app.
* Add CORS middleware to allow frontend domain.
* Bind D1 via `c.env.DB`.
* Map routes to handlers executing `DB.prepare(...).bind(...).all()`.

---

## 8. Frontend – Cloudflare Pages (React + Vite)

### 8.1 Setup

Location: `web/frontend/`

Codex must:

1. Scaffold a Vite React + TS app:

```bash
cd MINE-R/web
npm create vite@latest frontend -- --template react-ts
```

2. Install dependencies:

```bash
cd frontend
npm install @tanstack/react-query react-router-dom axios
```

3. Optionally install Tailwind CSS for styling.

### 8.2 Pages

Core routes:

1. `/` – Home:

   * Search bar.
   * Some quick filters (Armor, Weapons, etc.).
   * List of featured or recently updated items (using `updated_at`).

2. `/item/:id` – Item detail:

   * Name, icon, tier, item_class, slot.
   * Stats: durability, dr_base, resistance_base.
   * Effects: list of `StatusEffects` from API.
   * Damage types badges (Spicy, Slashing, etc.).
   * Armor set section if `armor_set_id` present.

3. `/sets` – Armor sets:

   * Grid of sets with icons.
   * Clicking a set goes to a set detail or filtered items.

4. `/search?q=...` – (optional) search results page.

### 8.3 API Client Layer

Create `src/api/client.ts`:

* Base URL for API (e.g. `https://api.yourdomain.com` or a Cloudflare Worker route).
* Functions:

  * `getItems(params)`
  * `getItemById(id)`
  * `searchItems(query)`
  * `getArmorSets()`

Use **React Query** to:

* Cache list/detail responses.
* Avoid refetching when navigating back & forth.

### 8.4 Icons

For V1:

* Treat `icon_path` from DB as a relative path under `/assets/`.
* Place some initial icons in `public/assets/...`.
* Later, integrate pipeline to copy icons from MINE-R exports.

---

## 9. CI/CD and Deployment

We will use **Wrangler** for deploy and optionally **GitHub Actions** for automation.

### 9.1 Manual Deploy (MVP)

**API:**

```bash
cd MINE-R/web/api
npx wrangler deploy
```

**Frontend (Pages):**

Option 1 – Use `wrangler pages`:

```bash
cd MINE-R/web/frontend
npm run build
npx wrangler pages deploy dist --project-name grounded2-wiki-frontend
```

Option 2 – Configure in Cloudflare Dashboard pointing to repo branch and build command.

### 9.2 GitHub Actions (Later)

Add `.github/workflows/deploy.yml` to:

* On push to `main`:

  * Install Node.
  * Run D1 migrations (if you move schema to migrations).
  * Deploy Worker.
  * Build + deploy Pages.

Separate pipeline (manual or triggered) for:

* Running MINE-R/AN-T locally.
* Running `python ingest/deploy_to_d1.py` to upload new data.

---

## 10. Codex Execution Checklist

This section is written **directly for Codex** (or similar agent). Follow steps in order. After each major step, confirm success with the user.

---

### Phase 1 – Project Wiring

1. **Confirm repo structure**

   * Ask the user to confirm the root project path (assume `MINE-R/`).
   * Verify that `scripts/` and `database/` exist.

2. **Create web tree**

   * Under `MINE-R/`, create directories:

     * `web/api/`
     * `web/frontend/`
     * `web/database/`
   * Create `ingest/` if it does not exist.

3. **Create base files**

   * `web/database/schema.sql` (use schema from Section 4.2).
   * Empty placeholder: `ingest/deploy_to_d1.py`.

---

### Phase 2 – D1 Setup

4. **Ask user for Cloudflare setup**

   * Ask user to ensure `wrangler` is installed and they’re logged in.
   * Ask for desired D1 database name (suggest: `grounded-wiki-db`).

5. **Guide user to create D1**

   * Tell the user to run:

     ```bash
     cd MINE-R
     npx wrangler d1 create grounded-wiki-db
     ```

   * Ask the user to paste the `database_id`. Store it for later.

6. **Guide user to apply schema**

   * Tell the user to run:

     ```bash
     npx wrangler d1 execute grounded-wiki-db --file=web/database/schema.sql --remote
     ```

   * Then run a verification command and show output.

---

### Phase 3 – Worker API

7. **Initialize `web/api` project**

   * In `MINE-R/web/api`:

     * Create `package.json` with basics (or run `npm init -y`).
     * Install dependencies:

       ```bash
       npm install hono @cloudflare/workers-types
       ```

8. **Create `wrangler.toml` for API**

   * Put the `database_id` captured earlier into:

     ```toml
     [[d1_databases]]
     binding = "DB"
     database_name = "grounded-wiki-db"
     database_id = "<DATABASE_ID_FROM_USER>"
     ```

9. **Create `src/index.ts`**

   * Implement:

     * Hono app creation.
     * Basic health route `GET /health`.
     * `GET /items` endpoint (Section 7.2.1).
     * `GET /items/:id` endpoint (Section 7.2.2).
     * `GET /armor-sets` (Section 7.2.3).
     * `GET /search` (Section 7.2.4).
   * Use `c.env.DB.prepare(...).bind(...).all()` for queries.

10. **Local test**

    * Use `npx wrangler dev` and test endpoints (with simple test data or after ingestion later).

---

### Phase 4 – Frontend

11. **Scaffold Vite app**

    * In `MINE-R/web`:

      ```bash
      npm create vite@latest frontend -- --template react-ts
      ```

12. **Install frontend libraries**

    * In `MINE-R/web/frontend`:

      ```bash
      npm install @tanstack/react-query react-router-dom axios
      ```

13. **Implement basic routing**

    * Set up `BrowserRouter` with routes:

      * `/` → Home
      * `/item/:id` → Item detail
      * `/sets` → Armor sets (stub)

14. **API client**

    * Create `src/api/client.ts` with Axios instance pointed at the Worker URL (temporary placeholder).
    * Implement functions: `getItems`, `getItemById`, `searchItems`, `getArmorSets`.

15. **Connect to API**

    * Use React Query to call the API and render:

      * Item list on home.
      * Item detail page showing at least name + description.

---

### Phase 5 – Ingestion Script

16. **Implement `ingest/deploy_to_d1.py`**

    * Use Python’s `sqlite3` module to connect to `database/grounded_data.db`. 
    * Query normalized tables that match the schema in Section 4 (you may need the user to confirm table names/columns from AN-T’s integration step). 
    * For each entity type:

      * Generate `INSERT OR REPLACE` statements into the D1 schema tables.
      * Escape strings safely.

17. **Batching**

    * Implement batching:

      * Collect ~200 statements.

      * Write them into `temp_batch_XXX.sql`.

      * Call:

        ```bash
        npx wrangler d1 execute grounded-wiki-db --file=temp_batch_XXX.sql --remote
        ```

      * Continue until all statements executed.

18. **Verification**

    * After ingestion, run:

      ```bash
      npx wrangler d1 execute grounded-wiki-db --remote --command="SELECT COUNT(*) FROM Items;"
      ```

    * Compare count to local source; inform user.

---

### Phase 6 – Deployment

19. **Deploy API**

    * From `MINE-R/web/api`, run:

      ```bash
      npx wrangler deploy
      ```

    * Capture the deployed URL and provide it to the user.

20. **Wire frontend to API URL**

    * Update the frontend API client base URL to match the deployed Worker domain/route.

21. **Build & deploy frontend**

    * From `MINE-R/web/frontend`:

      ```bash
      npm run build
      npx wrangler pages deploy dist --project-name grounded2-wiki-frontend
      ```

22. **Final sanity check**

    * Open the deployed frontend URL.
    * Confirm:

      * Items are listed.
      * Clicking an item navigates to detail.
      * Search works for some known items.

---
