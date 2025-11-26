Perfect — here is the **Codex Execution Document**, fully structured, atomic, deterministic, and ready to paste directly into VS Code for Codex to run **phase-by-phase**.

It references your uploaded documents **only for context**, never requiring Codex to read them. This is the “do this exactly” version — the one Codex can follow *literally*.

---

# **📘 Codex Execution Document: Grounded 2 Wiki Platform (Cloudflare D1 + Workers + Pages)**

## **Codex Behavioral Rules**

Before performing any steps, Codex must obey the following rules:

```
1. Execute steps exactly in the order presented.
2. Do not skip steps or merge steps.
3. Do not invent or assume any file paths, filenames, code structures, or dependencies.
4. Only create, modify, or delete files when explicitly instructed.
5. Always ask the user before running any shell commands.
6. After finishing each step, STOP and wait for the user to confirm success.
7. Never continue until the user clearly says "continue".
8. Use the exact file contents provided—no rewrites or “improvements.”
9. All code blocks inside <file> MUST be written verbatim to disk.
10. If information is missing (e.g., database_id), you must ask the user.
```

---

# **PHASE 1 — Environment Setup & Confirmation**

### **Goal**

Ensure Codex is operating in the correct repository and the user has required tools installed.

### **Action**

Codex must ask the user the following questions one at a time:

1. “What is the absolute path to the root of your MINE-R project?”
2. “Do you have Node.js ≥ 18 installed?”
3. “Do you have Wrangler installed (`npm install -g wrangler`)? If not, would you like me to generate installation commands?”
4. “Are you logged into Cloudflare (`wrangler login`)?”

After the user confirms each item, proceed.

### **Completion Condition**

Codex has received confirmation for all four questions.

### **Next**

Ask the user:
**“Ready to continue to Phase 2?”**

---

# **PHASE 2 — Create Web and Ingest Directory Structure**

### **Goal**

Create the folder tree needed for the Cloudflare stack.

### **Action**

Codex must create the following directories inside the project root:

```
web/
web/api/
web/api/src/
web/frontend/
web/database/
web/database/migrations/
ingest/
```

### **Output**

These directories now exist in the filesystem.

### **Completion Condition**

Codex must list each created directory and ask the user to confirm they exist.

### **Next**

Ask the user:
**“Continue to Phase 3?”**

---

# **PHASE 3 — Create Initial D1 Schema**

### **Goal**

Define the database schema for Cloudflare D1.

### **Action**

Codex must create the following file:

---

### **Create file: `web/database/schema.sql`**

<file path="web/database/schema.sql">
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS StatusEffects (
effect_id    TEXT PRIMARY KEY,
name         TEXT NOT NULL,
description  TEXT,
category     TEXT,
icon_path    TEXT
);

CREATE TABLE IF NOT EXISTS ArmorSets (
set_id               INTEGER PRIMARY KEY AUTOINCREMENT,
set_name             TEXT UNIQUE NOT NULL,
set_bonus_effect_id  TEXT REFERENCES StatusEffects(effect_id)
);

CREATE TABLE IF NOT EXISTS Items (
item_id          TEXT PRIMARY KEY,
name             TEXT NOT NULL,
description      TEXT,
icon_path        TEXT,
tier             INTEGER,
item_class       TEXT,
slot             TEXT,
durability       REAL,
dr_base          REAL,
resistance_base  REAL,
armor_set_id     INTEGER REFERENCES ArmorSets(set_id),
version_added    TEXT,
updated_at       TEXT
);

CREATE TABLE IF NOT EXISTS Item_Effects (
item_id   TEXT NOT NULL REFERENCES Items(item_id),
effect_id TEXT NOT NULL REFERENCES StatusEffects(effect_id),
source    TEXT NOT NULL,
PRIMARY KEY (item_id, effect_id, source)
);

CREATE TABLE IF NOT EXISTS Item_DamageTypes (
item_id      TEXT NOT NULL REFERENCES Items(item_id),
damage_type  TEXT NOT NULL,
is_base_type BOOLEAN DEFAULT 1,
PRIMARY KEY (item_id, damage_type)
);

CREATE TABLE IF NOT EXISTS Recipes (
recipe_id         TEXT PRIMARY KEY,
result_item_id    TEXT REFERENCES Items(item_id),
amount            INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS Recipe_Ingredients (
recipe_id          TEXT NOT NULL REFERENCES Recipes(recipe_id),
ingredient_item_id TEXT NOT NULL REFERENCES Items(item_id),
quantity           INTEGER NOT NULL,
PRIMARY KEY (recipe_id, ingredient_item_id)
);

CREATE INDEX IF NOT EXISTS idx_items_name ON Items(name);
CREATE INDEX IF NOT EXISTS idx_items_set ON Items(armor_set_id);
CREATE INDEX IF NOT EXISTS idx_effects_name ON StatusEffects(name);

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

CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON Items BEGIN
INSERT INTO Items_Search(rowid, item_id, name, description, item_class, slot)
VALUES (new.rowid, new.item_id, new.name, new.description, new.item_class, new.slot);
END;

CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON Items BEGIN
INSERT INTO Items_Search(Items_Search, rowid, item_id, name, description, item_class, slot)
VALUES ('delete', old.rowid, old.item_id, old.name, old.description, old.item_class, old.slot);
END;

CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON Items BEGIN
INSERT INTO Items_Search(Items_Search, rowid, item_id, name, description, item_class, slot)
VALUES ('delete', old.rowid, old.item_id, old.name, old.description, old.item_class, old.slot);
INSERT INTO Items_Search(rowid, item_id, name, description, item_class, slot)
VALUES (new.rowid, new.item_id, new.name, new.description, new.item_class, new.slot);
END; </file>

---

### **Completion Condition**

Codex must show the file contents back to the user and ask for confirmation.

### **Next**

Ask the user:
**“Now we need to create the D1 database. Ready to continue to Phase 4?”**

---

# **PHASE 4 — Create the Cloudflare D1 Database**

### **Goal**

Create the hosted Cloudflare D1 instance and apply the schema.

### **Action**

Codex must:

1. Ask the user for the desired D1 database name (suggest: `grounded-wiki-db`).
2. Ask the user to run this command manually in the terminal:

```
npx wrangler d1 create grounded-wiki-db
```

3. Ask the user to paste back the **database_id**.
4. Ask the user to run:

```
npx wrangler d1 execute grounded-wiki-db --file=web/database/schema.sql --remote
```

### **Completion Condition**

User confirms the schema applied successfully.

### **Next**

Ask user:
**“Proceed to Phase 5 (API Worker)?”**

---

# **PHASE 5 — Cloudflare Worker API (Hono)**

### **Goal**

Create the API Worker, wire it to D1, and implement the REST endpoints.

---

## **Step 5.1 — Initialize API Project**

Codex must:

1. Create `web/api/package.json`:

<file path="web/api/package.json">
{
  "name": "grounded-wiki-api",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "hono": "^4.0.0"
  },
  "devDependencies": {
    "@cloudflare/workers-types": "^4.20250101.0"
  }
}
</file>

2. Create empty:

```
web/api/src/index.ts
```

---

## **Step 5.2 — Create wrangler.toml**

<file path="web/api/wrangler.toml">
name = "grounded-wiki-api"
main = "src/index.ts"
compatibility_date = "2025-01-01"

[[d1_databases]]
binding = "DB"
database_name = "grounded-wiki-db"
database_id = "<REPLACE_WITH_USER_VALUE>" </file>

Codex must pause here and ask the user for the actual `database_id` and then fill it in.

---

## **Step 5.3 — Implement API**

Codex must overwrite `web/api/src/index.ts` with:

<file path="web/api/src/index.ts">
import { Hono } from 'hono';

export interface Env {
DB: D1Database;
}

const app = new Hono<{ Bindings: Env }>();

app.get('/health', (c) => c.json({ ok: true }));

app.get('/items', async (c) => {
const limit = Number(c.req.query('limit') ?? 50);
const offset = Number(c.req.query('offset') ?? 0);

const sql = `     SELECT item_id, name, tier, item_class, slot, icon_path
    FROM Items
    ORDER BY name
    LIMIT ? OFFSET ?
  `;
const data = await c.env.DB.prepare(sql)
.bind(limit, offset)
.all();

return c.json(data.results);
});

app.get('/items/:id', async (c) => {
const id = c.req.param('id');

const item = await c.env.DB.prepare(`     SELECT *
    FROM Items
    WHERE item_id = ?
  `).bind(id).first();

if (!item) return c.json({ error: 'not found' }, 404);

const effects = await c.env.DB.prepare(`     SELECT se.effect_id, se.name, se.description, ie.source
    FROM Item_Effects ie
    JOIN StatusEffects se ON se.effect_id = ie.effect_id
    WHERE ie.item_id = ?
  `).bind(id).all();

const dmg = await c.env.DB.prepare(`     SELECT damage_type, is_base_type
    FROM Item_DamageTypes
    WHERE item_id = ?
  `).bind(id).all();

return c.json({ ...item, effects: effects.results, damage: dmg.results });
});

app.get('/armor-sets', async (c) => {
const sets = await c.env.DB.prepare(`     SELECT set_id, set_name, set_bonus_effect_id
    FROM ArmorSets
    ORDER BY set_name
  `).all();

return c.json(sets.results);
});

app.get('/search', async (c) => {
const q = c.req.query('q') ?? '';
if (!q) return c.json([]);

const sql = `     SELECT i.item_id, i.name, i.icon_path
    FROM Items_Search s
    JOIN Items i ON i.rowid = s.rowid
    WHERE Items_Search MATCH ?
    LIMIT 20
  `;

const results = await c.env.DB.prepare(sql).bind(q + '*').all();
return c.json(results.results);
});

export default app; </file>

---

### **Completion Condition**

User confirms the Worker builds locally via:

```
npx wrangler dev
```

### **Next**

Ask the user:
**“Continue to Phase 6 (Frontend)?”**

---

# **PHASE 6 — Frontend (Cloudflare Pages: React + Vite)**

## **Step 6.1 — Scaffold Frontend Project**

Codex must NOT run shell commands—ask the user to run:

```
cd web
npm create vite@latest frontend -- --template react-ts
```

Then:

```
cd frontend
npm install @tanstack/react-query react-router-dom axios
```

---

## **Step 6.2 — Create Basic API Client**

Codex must create:

<file path="web/frontend/src/api/client.ts">
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE ?? '[http://localhost:8787](http://localhost:8787)';

export const client = axios.create({
baseURL: API_BASE
});

export const getItems = (params = {}) =>
client.get('/items', { params }).then(r => r.data);

export const getItem = (id: string) =>
client.get(`/items/${id}`).then(r => r.data);

export const searchItems = (q: string) =>
client.get('/search', { params: { q } }).then(r => r.data);

export const getArmorSets = () =>
client.get('/armor-sets').then(r => r.data); </file>

---

## **Step 6.3 — Create Pages/Routes**

Codex must modify the React app to include:

* `/`
* `/item/:id`
* `/sets`

Skeleton code can be added later as needed.

---

### **Completion Condition**

Frontend compiles with no errors:

```
npm run dev
```

---

# **PHASE 7 — Ingestion Script (Local → D1)**

Codex must generate:

<file path="ingest/deploy_to_d1.py">
import sqlite3
import subprocess
import os
import math

DB_LOCAL = "database/grounded_data.db"
BATCH_SIZE = 200
TEMP_FOLDER = "ingest/temp"

os.makedirs(TEMP_FOLDER, exist_ok=True)

def escape(s):
return s.replace("'", "''") if isinstance(s, str) else s

def fetch_all(conn, query):
return conn.execute(query).fetchall()

def write_batch(batch_num, statements):
path = f"{TEMP_FOLDER}/batch_{batch_num:04d}.sql"
with open(path, "w", encoding="utf-8") as f:
for stmt in statements:
f.write(stmt + ";\n")
return path

def main():
conn = sqlite3.connect(DB_LOCAL)
cur = conn.cursor()

```
# Example queries (user may update depending on AN-T output tables)
items = fetch_all(cur, "SELECT item_id, name, description, icon_path, tier, item_class, slot, durability, dr_base, resistance_base, armor_set_id, version_added, updated_at FROM Items")
effects = fetch_all(cur, "SELECT item_id, effect_id, source FROM Item_Effects")
dmg = fetch_all(cur, "SELECT item_id, damage_type, is_base_type FROM Item_DamageTypes")

statements = []

for row in items:
    row = [escape(x) for x in row]
    stmt = f"INSERT OR REPLACE INTO Items VALUES('{row[0]}','{row[1]}','{row[2]}','{row[3]}',{row[4]},'{row[5]}','{row[6]}',{row[7]},{row[8]},{row[9]},{row[10]},'{row[11]}','{row[12]}')"
    statements.append(stmt)

for item_id, effect_id, source in effects:
    stmt = f"INSERT OR REPLACE INTO Item_Effects VALUES('{escape(item_id)}','{escape(effect_id)}','{escape(source)}')"
    statements.append(stmt)

for item_id, dmg_type, is_base_type in dmg:
    stmt = f"INSERT OR REPLACE INTO Item_DamageTypes VALUES('{escape(item_id)}','{escape(dmg_type)}',{is_base_type})"
    statements.append(stmt)

total = len(statements)
batches = math.ceil(total / BATCH_SIZE)

for b in range(batches):
    chunk = statements[b * BATCH_SIZE:(b + 1) * BATCH_SIZE]
    batch_path = write_batch(b, chunk)
    print(f"Run: npx wrangler d1 execute grounded-wiki-db --file={batch_path} --remote")

print("Done. Execute each command above.")
```

</file>

Codex must stop and ask the user:

> “Please confirm that the ingestion queries match your AN-T output schema. If not, tell me what needs to be adjusted.”

---

# **PHASE 8 — Final Deployment**

### **Goal**

Deploy the public API and frontend.

### **Action**

Codex must instruct the user to:

**Deploy API:**

```
cd web/api
npx wrangler deploy
```

**Deploy Frontend:**

```
cd web/frontend
npm run build
npx wrangler pages deploy dist --project-name grounded2-wiki-frontend
```

---

# **End of Codex Execution Document**

When you’re ready for Codex to begin, say:

**“Codex, start at Phase 1.”**
