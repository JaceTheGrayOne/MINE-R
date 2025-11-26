

# **Cloudflare Full-Stack Architecture for MINE-R \+ AN-T: Grounded 2 Wiki Implementation Plan**

## **1\. Introduction and Architectural Vision**

The development of the public-facing wiki for *Grounded 2* represents the final stage of the MINE-R (extraction) and AN-T (enrichment) data pipeline. With the game’s sequel shifting to Unreal Engine 5 and introducing complex new mechanics—such as "Sizzling" environmental hazards, O.R.C. creature variants, and enhanced armor class stamina penalties—the hosting infrastructure must evolve beyond simple static HTML generation.1 The objective is to deploy a high-performance, edge-cached, and relational backend that provides near-instantaneous access to normalized game data while supporting complex analytical queries for build optimization and patch-diff analysis.

This report outlines a comprehensive execution plan for implementing this system on the Cloudflare Developer Platform. By leveraging Cloudflare D1 (serverless SQLite), Workers (edge compute), and Pages (static frontend), the architecture eliminates traditional server management while optimizing for the high-read, burst-traffic patterns typical of game launches. The system is designed to ingest the JSON-LD ontology produced by AN-T, enforcing strict relational integrity that mirrors the game's internal UDataTable structures, and exposing this data via a typed REST API.

### **1.1 The Operational Context: Grounded 2 Data Complexity**

The requirement for a relational database, rather than a NoSQL document store, stems directly from the *Grounded 2* mechanic set. Unlike its predecessor, the sequel introduces highly interdependent systems where singular items carry multi-faceted payloads. For instance, armor pieces now possess tiered stamina usage penalties based on weight class (Light, Medium, Heavy) alongside distinct resistance values for new damage types like "Sizzling" and "O.R.C. Bane".3 A single query for "Acorn Armor" must resolve its base defense stats, its set bonus ("Major Threat"), and its status effect modifiers.3

Furthermore, the wiki must serve as a historical record. With the game in Early Access as of July 2025, frequent patches will alter damage coefficients and status effect durations.5 The MINE-R pipeline detects these changes via manifest analysis, and the hosting layer must reflect these "diffs" to the user, necessitating a schema that supports versioned ingestion or robust tracking of updated\_at timestamps to visualize patch changes.6

### **1.2 System Architecture Components**

The architecture follows a monorepo design, tightly coupling the backend schema with the frontend interfaces to ensure type safety across the stack.

| Layer | Component | Technology | Responsibility |
| :---- | :---- | :---- | :---- |
| **Database** | Cloudflare D1 | SQLite (Distributed) | Stores the normalized ontology. Handles relational joins between Items, StatusEffects, and DamageTypes. Supports FTS5 for full-text search.8 |
| **API** | Cloudflare Workers | Hono Framework | Serverless gateway. Handles routing, request validation, and SQL execution. Manages edge caching policies (Cache-Control).9 |
| **Frontend** | Cloudflare Pages | React \+ Vite | Single Page Application (SPA). Consumes the API to render item details, search interfaces, and patch diff visualizations.11 |
| **Ingestion** | Node.js Script | Wrangler CLI | Orchestrates the transfer of MINE-R/AN-T output into D1 via batch SQL execution, bypassing HTTP body limits.13 |

This architectural choice provides significant advantages in latency and scalability. Cloudflare D1 allows the database to exist close to the user, reducing the round-trip time for complex join queries.14 The integration of the FTS5 module directly into SQLite eliminates the need for a separate search service like Algolia, reducing both cost and architectural complexity.8

---

## **2\. Cloudflare Ecosystem Setup and Environment Initialization**

The foundation of the *Grounded 2* wiki infrastructure lies in the correct configuration of the Cloudflare environment. This section details the initialization of the account, the tooling, and the workspace structure required to support the monorepo.

### **2.1 Account Prerequisites and Limits**

The implementation operates within the specific constraints of the Cloudflare Workers platform. It is imperative to acknowledge these limits during the design phase to prevent deployment failures during data ingestion.

The D1 database imposes a hard limit of 10 GB per database on the paid plan (500 MB on free), which is sufficient for the text-based ontology of *Grounded 2* but requires efficient schema design—storing binary assets like icons in R2 or standard CDN paths rather than the database itself.17 The bulk import process is limited to 500 MB per execution command, dictating that the ingestion pipeline must batch SQL statements rather than attempting a monolithic dump.18 Additionally, the Workers runtime restricts environment variables (used here for configuration secrets) to 5 KB each, with a total limit of 128 variables.20

**Prerequisites for Execution:**

1. **Cloudflare Account:** A standard account with a verified email address.  
2. **Domain Name:** A custom domain (e.g., grounded2-wiki.com) must be active in the Cloudflare Dashboard to allow custom API routing (e.g., api.grounded2-wiki.com).  
3. **Node.js Environment:** Version 18 or higher is required to support the latest wrangler CLI and Hono framework features.21

### **2.2 Tooling Installation and Authentication**

The primary interface for all deployment, configuration, and database management is wrangler, the Cloudflare Command Line Interface. Codex will utilize wrangler for both local development (emulating D1 and Workers) and production deployment.22

Step 1: Wrangler Installation  
Codex must enforce the global installation of the latest Wrangler version to ensure compatibility with the D1 batch command and Pages monorepo support.

Bash

npm install \-g wrangler

Step 2: Authentication  
In an interactive environment, wrangler login initiates an OAuth flow. However, for the automated pipeline Codex runs, authentication relies on API tokens. The agent must verify authentication status before proceeding with any infrastructure creation commands.

Bash

wrangler whoami

*Validation:* The output must confirm the authenticated user and list the Account ID associated with the target domain. If this command fails, the process must halt for credential verification.

### **2.3 Monorepo Structure and Workspaces**

To facilitate code sharing between the Workers API and the Pages Frontend—specifically shared TypeScript interfaces for the database schema—the project will use an npm workspace configuration. This structure allows the API and Frontend to exist as distinct applications while consuming a shared schema package.23

**Directory Layout:**

/grounded-wiki-monorepo  
├── package.json \# Root configuration defining workspaces  
├── pnpm-workspace.yaml \# (Optional) if using pnpm for strict dependency management  
├── wrangler.toml \# Root configuration (can be inherited)  
├── /apps  
│ ├── /frontend \# Cloudflare Pages (React \+ Vite)  
│ │ ├── package.json  
│ │ ├── vite.config.ts  
│ │ └── src/  
│ └── /api \# Cloudflare Workers (Hono \+ D1 Binding)  
│ ├── package.json  
│ ├── wrangler.toml \# Worker-specific config  
│ └── src/  
└── /packages  
└── /schema \# Shared TypeScript definitions and SQL migrations  
├── package.json  
├── index.ts \# Exports TypeScript types  
└── migrations/ \#.sql files for D1 versioning  
Root Configuration:  
The root package.json defines the workspace context. This enables commands like npm install to resolve dependencies for all sub-projects simultaneously, ensuring that the hono version used in the API matches any client-side types used in the frontend.25

JSON

{  
  "name": "grounded-wiki-root",  
  "private": true,  
  "workspaces": \[  
    "apps/\*",  
    "packages/\*"  
  \],  
  "scripts": {  
    "deploy:api": "npm run deploy \-w apps/api",  
    "deploy:frontend": "npm run deploy \-w apps/frontend"  
  }  
}

This setup is critical for the "Grounded 2" pipeline because the AN-T enrichment process produces a strict ontology. By centralizing this ontology in /packages/schema, we ensure that if the game adds a new damage type (e.g., "Sizzling"), both the database migration and the frontend "Damage Badge" component can be updated from a single source of truth.

---

## **3\. Data Model Analysis and D1 Schema Definition**

The design of the database schema is the most critical component of the architecture. It must accurately model the complex, interconnected nature of *Grounded 2* game data. Unlike a standard wiki that might store data as unstructured blobs, this implementation uses a strictly normalized relational model to enable powerful queries, such as "Find all Heavy Armor items that provide Sizzle Resistance."

### **3.1 Ontology Analysis: Grounded 2 Mechanics**

To define the schema, we must analyze the specific data structures revealed in the research snippets regarding *Grounded 2*.

* **Armor Classes & Stamina:** Armor is categorized into Light, Medium, and Heavy. Each class imposes a specific stamina regeneration penalty and damage reduction percentage. For example, "Heavy Armor" grants 30% damage reduction but increases stamina usage by 25%.3 This implies that weight\_class is not just a label but a functional key linked to specific stat modifiers.  
* **Status Effects & Complexity:** Effects in *Grounded 2* are granular. They include "Sizzle Reduction," "O.R.C. Bane" (specific damage against O.R.C. creatures), and "Parry Buggie Heal".4 These effects are not simple key-value pairs; they have descriptions, icon paths, and magnitudes (e.g., "50% reduction"). This dictates a many-to-many relationship between Items and StatusEffects.  
* **Damage Types:** The game features distinct damage types: Slashing, Smashing, Chopping, and new elemental types like "Spicy" or "Fresh".27 Weapons often deal multiple types (e.g., a "Spicy Coaltana" deals both Slashing and Spicy damage). This requires a normalized DamageTypes table linked via a junction table to Items.

### **3.2 Schema Definition Strategy**

We will utilize Cloudflare D1's SQLite compatibility to implement this model.8 We will enforce PRAGMA foreign\_keys \= ON to ensure that we cannot insert an item that references a non-existent status effect—a common issue when parsing raw game files where references might be broken or deprecated.28

The schema will be versioned using migration files located in packages/schema/migrations. Codex will generate these files sequentially.

### **3.3 Detailed D1 SQL Schema**

The following SQL definitions constitute the core 0001\_initial\_schema.sql.

#### **1\. Base Entities: Items Table**

This is the master table for all game objects (Armor, Weapons, Consumables). We store universal attributes here. Note the updated\_at column, which is crucial for the Patch Diff feature.

SQL

CREATE TABLE Items (  
    id TEXT PRIMARY KEY, \-- String ID from UE DataTable (e.g., "Armor\_Acorn\_Chest")  
    name TEXT NOT NULL,  
    description TEXT,  
    tier INTEGER, \-- Tier I, II, III  
    type TEXT CHECK(type IN ('Armor', 'Weapon', 'Consumable', 'Material', 'Trinket')),  
    rarity TEXT,  
    icon\_path TEXT, \-- Relative path to CDN asset  
    wiki\_url TEXT, \-- Slug for frontend routing  
    version\_added TEXT, \-- e.g., "1.0.4"  
    created\_at TIMESTAMP DEFAULT CURRENT\_TIMESTAMP,  
    updated\_at TIMESTAMP DEFAULT CURRENT\_TIMESTAMP  
);

#### **2\. Game Mechanics: Status Effects & Damage Types**

These lookup tables normalize the mechanics described in 4 and.27

SQL

CREATE TABLE StatusEffects (  
    id TEXT PRIMARY KEY, \-- e.g., "Effect\_SizzleProt"  
    name TEXT NOT NULL, \-- "Sizzle Protection"  
    description TEXT, \-- "Reduces the rate at which sizzle builds up."  
    icon\_path TEXT,  
    is\_positive BOOLEAN DEFAULT 1 \-- Distinguishes buffs vs debuffs  
);

CREATE TABLE DamageTypes (  
    id TEXT PRIMARY KEY, \-- e.g., "DmgType\_Spicy"  
    name TEXT NOT NULL, \-- "Spicy"  
    description TEXT \-- "Elemental damage effective against Spiders."  
);

#### **3\. Item Specifics: Armor and Weapon Stats**

Instead of a sparse Items table with NULL columns for every possible stat, we use vertical partitioning. The ArmorStats table holds data specific to armor behavior as detailed in 3 (Defense, Resistance, Weight Class).

SQL

CREATE TABLE ArmorStats (  
    item\_id TEXT PRIMARY KEY,  
    defense\_base INTEGER,  
    defense\_max INTEGER, \-- At max upgrade level  
    damage\_reduction REAL, \-- e.g., 0.30 for 30%  
    stamina\_cost\_penalty REAL, \-- e.g., 0.25 for 25%  
    weight\_class TEXT CHECK(weight\_class IN ('Light', 'Medium', 'Heavy')),  
    durability INTEGER,  
    FOREIGN KEY (item\_id) REFERENCES Items(id) ON DELETE CASCADE  
);

CREATE TABLE WeaponStats (  
    item\_id TEXT PRIMARY KEY,  
    min\_damage INTEGER,  
    max\_damage INTEGER,  
    attack\_speed REAL,  
    stun\_value REAL,  
    block\_value INTEGER, \-- Shields also map here or separate table  
    FOREIGN KEY (item\_id) REFERENCES Items(id) ON DELETE CASCADE  
);

#### **4\. Relational Linking: Junction Tables**

These tables enable the complex queries required for "Build Calculator" features.

SQL

\-- Links items to their passive effects (e.g., Acorn Armor \-\> Major Threat)  
CREATE TABLE Item\_StatusEffects (  
    item\_id TEXT,  
    effect\_id TEXT,  
    magnitude REAL, \-- e.g., 20.0 for "+20%"  
    duration REAL, \-- Seconds, NULL if passive/permanent  
    trigger\_condition TEXT, \-- e.g., "Perfect Block", "On Hit"  
    PRIMARY KEY (item\_id, effect\_id),  
    FOREIGN KEY (item\_id) REFERENCES Items(id) ON DELETE CASCADE,  
    FOREIGN KEY (effect\_id) REFERENCES StatusEffects(id) ON DELETE CASCADE  
);

\-- Links weapons to their damage types (e.g., Coaltana \-\> Slash, Spicy)  
CREATE TABLE Item\_DamageTypes (  
    item\_id TEXT,  
    damage\_type\_id TEXT,  
    PRIMARY KEY (item\_id, damage\_type\_id),  
    FOREIGN KEY (item\_id) REFERENCES Items(id) ON DELETE CASCADE,  
    FOREIGN KEY (damage\_type\_id) REFERENCES DamageTypes(id) ON DELETE CASCADE  
);

#### **5\. Search Index: FTS5 Virtual Table**

To support the search bar without an external service, we implement SQLite's FTS5. Triggers ensure this virtual table stays synchronized with the main Items table.8

SQL

CREATE VIRTUAL TABLE Items\_Search USING fts5(id, name, description, type, content\='Items', content\_rowid\='rowid');

\-- Triggers to sync FTS5  
CREATE TRIGGER items\_ai AFTER INSERT ON Items BEGIN  
  INSERT INTO Items\_Search(rowid, id, name, description, type) VALUES (new.rowid, new.id, new.name, new.description, new.type);  
END;  
CREATE TRIGGER items\_ad AFTER DELETE ON Items BEGIN  
  INSERT INTO Items\_Search(Items\_Search, rowid, id, name, description, type) VALUES('delete', old.rowid, old.id, old.name, old.description, old.type);  
END;  
CREATE TRIGGER items\_au AFTER UPDATE ON Items BEGIN  
  INSERT INTO Items\_Search(Items\_Search, rowid, id, name, description, type) VALUES('delete', old.rowid, old.id, old.name, old.description, old.type);  
  INSERT INTO Items\_Search(rowid, id, name, description, type) VALUES (new.rowid, new.id, new.name, new.description, new.type);  
END;

---

## **4\. Ingestion Pipeline (MINE-R Integration)**

The Ingestion Pipeline is the bridge between the MINE-R data extraction tools and the live D1 database. Unlike traditional databases where a persistent connection allows for continuous streams of inserts, D1 in a serverless environment requires a batched HTTP-based approach.18 The MINE-R pipeline, likely running in a CI/CD environment (Github Actions), will trigger this ingestion process upon detecting changes in the game manifest.

### **4.1 Batch Execution Strategy**

The primary challenge in D1 ingestion is the limitation on transaction size and execution time. A monolithic SQL dump of thousands of game items often exceeds the 500 MB limit or the execution timeout of the Workers API.17 Therefore, the ingestion strategy relies on **intelligent batching**.

The ingestion script must parse the massive JSON-LD ontology output by AN-T and slice it into manageable SQL transaction chunks. Each chunk will be executed sequentially via wrangler d1 execute. This ensures atomicity per batch; if a batch fails (e.g., due to a syntax error or constraint violation), the pipeline stops, preventing a partially corrupted database state.13

### **4.2 Ingestion Script Implementation**

Codex will generate a Node.js script located at ingest/ingest-to-d1.js. This script functions as the controller for the deployment.

**Script Logic Flow:**

1. **Load Data:** Read the ant\_output\_normalized.json file.  
2. **Generate SQL:** Iterate through the entities. For each entity, generate an INSERT OR REPLACE INTO statement. The OR REPLACE clause is vital: it allows the pipeline to be idempotent. If MINE-R re-runs, it simply updates existing records without duplicate key errors.  
   * *Sanitization:* The script must escape single quotes in strings (e.g., "Assassin's Dagger" \-\> "Assassin''s Dagger") to prevent SQL injection or syntax crashes.  
3. **Chunking:** Push statements into an array. When the array size reaches 500 statements (or \~1MB of text), flush it to a temporary .sql file (e.g., batch\_001.sql).  
4. **Execution:** Use child\_process.execSync to call Wrangler:  
   Bash  
   npx wrangler d1 execute grounded-db \--remote \--file=./temp/batch\_001.sql

5. **Verification:** After all batches, run a quick SELECT count(\*) FROM Items check to verify the total record count matches the source JSON.

### **4.3 Handling Patch Diffs and Updates**

One of the core requirements is tracking changes between patches (e.g., identifying that "Mantis Blade" damage changed from 45 to 50 in Patch 1.0.4).5

Since D1 does not natively support temporal tables in the same way MS SQL Server does 31, we implement a "Soft Diff" strategy in the ingestion layer:

1. **Timestamping:** The Items table has an updated\_at column.  
2. **Change Detection:** When generating the SQL, the script compares the new data against a cached checksum of the previous data (or relies on INSERT OR REPLACE).  
3. **Frontend Logic:** The API will expose items with updated\_at \> last\_patch\_date. The frontend will use this to highlight "New" or "Changed" items.  
4. **Detailed History:** For a rigorous history, we would create a shadow table Items\_History. However, for this implementation plan, we will rely on the AN-T pipeline to generate "Patch Note" JSONs separately, which are ingested into a dedicated PatchNotes table, linking modified Item IDs to the patch version.

---

## **5\. Workers API Implementation Plan**

The API Layer serves as the query engine for the wiki. Built on Cloudflare Workers using the Hono framework, it acts as a lightweight, type-safe translation layer between the HTTP requests and the D1 SQL database.9 Hono is selected specifically for its ultra-low overhead and native support for Workers' ExecutionCtx and environment bindings.

### **5.1 Worker Configuration (wrangler.toml)**

Configuration is managed via apps/api/wrangler.toml. This file binds the D1 database to the variable DB in the runtime environment.34

Ini, TOML

name \= "grounded-wiki-api"  
main \= "src/index.ts"  
compatibility\_date \= "2025-01-01"

\# Database Binding  
\[\[d1\_databases\]\]  
binding \= "DB"  
database\_name \= "grounded-db"  
database\_id \= "8f4b... (Codex to fill this)"

\# CORS Policy (handled in code via Hono middleware, but allowed origins can be set here)  
\[vars\]  
ALLOWED\_ORIGIN \= "https://grounded2-wiki.com"

### **5.2 API Endpoints Specification**

The API follows RESTful principles. All responses are JSON. Error handling is standardized to return HTTP 404 for missing resources and 500 for internal errors.

#### **A. List Items (Paginated & Filtered)**

* **Route:** GET /items  
* **Purpose:** The main feed for the "Items" wiki page.  
* **Parameters:**  
  * page: Integer (default 1).  
  * limit: Integer (default 50).  
  * type: Filter by 'Armor', 'Weapon', etc.  
  * tier: Filter by Tier (1, 2, 3).  
* Logic:  
  Constructs a dynamic SQL query.  
  SQL  
  SELECT id, name, tier, type, icon\_path FROM Items WHERE type \=? LIMIT? OFFSET?

  *Insight:* This query is highly cacheable. The Worker should set Cache-Control: public, max-age=3600 to serve subsequent requests from the Cloudflare Edge Cache, minimizing D1 reads.

#### **B. Item Details (Relational Join)**

* **Route:** GET /items/:id  
* **Purpose:** Full detail view for a specific item, including all joined stats.  
* Logic:  
  This endpoint requires fetching data from multiple tables. We can perform a join, or parallel queries. Given D1's latency, a single query with joins is preferred, but mapping the result to a nested JSON object requires aggregation.  
  Query Strategy:  
  SQL  
  SELECT i.\*,   
         as.defense\_base, as.damage\_reduction, as.stamina\_cost\_penalty,  
         json\_group\_array(json\_object('name', se.name, 'magnitude', ise.magnitude)) as effects  
  FROM Items i  
  LEFT JOIN ArmorStats as ON i.id \= as.item\_id  
  LEFT JOIN Item\_StatusEffects ise ON i.id \= ise.item\_id  
  LEFT JOIN StatusEffects se ON ise.effect\_id \= se.id  
  WHERE i.id \=?

  The json\_group\_array function (native to SQLite) is powerful here.35 It allows the database to return the item *and* its list of effects in a single row containing a JSON string. The Worker then simply parses this JSON string before returning the response, saving multiple round-trips.

#### **C. Semantic Search**

* **Route:** GET /search  
* **Purpose:** Power the global search bar.  
* **Logic:** Executes against the Items\_Search virtual table.  
  SQL  
  SELECT \* FROM Items\_Search WHERE Items\_Search MATCH? ORDER BY rank LIMIT 10

  The query parameter q must be sanitized. If the user types "spicy", the query becomes spicy\* to enable prefix matching. This leverages the FTS5 module enabled in the schema.8

#### **D. Patch Diff View**

* **Route:** GET /patch-diff/:version  
* **Purpose:** Returns all items modified in a specific version.  
* **Logic:** Queries the Items table filtering by version\_added or updated\_at. This allows the frontend to generate a "What's New in Patch 1.0.4" page dynamically.

---

## **6\. Frontend (Pages) Architecture**

The frontend is the user's window into the data. We utilize Cloudflare Pages to host a React Single Page Application (SPA) built with Vite.12 The key challenge here is visualizing the complex relational data (like "Sizzling" resistance) and the patch diffs in a user-friendly manner.

### **6.1 State Management and Data Fetching**

Given the relational nature of the data, the frontend state can become complex. We will use **TanStack Query (React Query)** to manage server state.

* **Caching:** React Query handles caching of API responses on the client side. If a user navigates from "Acorn Armor" to "Home" and back, the data is loaded instantly from the cache.  
* **Stale-While-Revalidate:** The app will show cached data while fetching updates in the background, making the wiki feel incredibly fast.

### **6.2 Component Architecture: Visualizing Grounded 2 Stats**

1\. The StatBlock Component:  
This component is responsible for rendering the complex ArmorStats and WeaponStats returned by the API.

* *Input:* defense\_base, damage\_reduction, weight\_class.  
* *Visualization:* It renders a bar chart for Defense. Crucially, it must interpret the weight\_class. If weight\_class \=== 'Heavy', it renders a warning tooltip: "Increases Stamina Cost by 25%".3 This logic is hard-coded in the component based on the game's immutable rules, while the *values* come from the DB.

2\. The EffectBadge Component:  
Displays Status Effects.

* *Input:* effect\_object (from the json\_group\_array API response).  
* *Interaction:* Hovering the badge (e.g., a "Spicy" icon) triggers a tooltip showing the description from the StatusEffects table (e.g., "Deals 15 spicy damage...").

3\. The DiffVisualizer Component:  
To handle the "Wiki" aspect of showing changes, this component uses a JSON diffing library like react-json-view-compare.36

* *Scenario:* When viewing a "Patch Notes" page, the component receives two JSON objects: Item\_Old and Item\_New.  
* *Render:* It highlights changed fields. For example, if "Damage" changed from 20 to 25, it renders the number 25 in green with an arrow (20 \-\> 25). This automates the tedious work of writing patch notes.

### **6.3 Routing and Asset Handling**

* **Client-Side Routing:** react-router-dom handles navigation (e.g., /items/acorn-chestplate).  
* **Asset Handling:** Images (icons for items and effects) are not stored in D1. They are stored in the /public/assets folder of the Pages repo or an R2 bucket. The D1 icon\_path column stores the relative URL (e.g., /assets/icons/items/armor\_acorn.png).

---

## **7\. Search and Discovery Implementation**

Effective search is non-negotiable for a wiki. Users will search for "coaltana", "sizzle protection", or "spider". The FTS5 implementation in D1 provides the backend, but the frontend experience matters.

### **7.1 Search UX**

The search bar in the React header uses a **debounced input**. As the user types, requests are sent to /api/search.

* **Debounce Time:** 300ms. This prevents flooding the API with a request for every keystroke.  
* **Results:** The API returns a lightweight JSON list (id, name, icon). The search dropdown renders these immediately.  
* **Navigation:** Clicking a result navigates to /items/:id directly.

### **7.2 Advanced Filtering**

Beyond text search, the /items page implements facet filtering based on the D1 columns:

* **Filter by Effect:** "Show me all items with 'Sizzle Protection'." This requires the API to join Items \-\> Item\_StatusEffects \-\> StatusEffects and filter by effect\_id.  
* **Filter by Damage Type:** "Show me weapons dealing 'Spicy' damage."

---

## **8\. CI/CD and Deployment Strategy**

The system must be deployable via automation. We will use GitHub Actions to orchestrate the deployment of the Worker, the Database Migrations, and the Frontend Pages site.38

### **8.1 GitHub Actions Workflow (.github/workflows/deploy.yml)**

This workflow defines the pipeline. It is triggered on pushes to main or via a repository\_dispatch event from the MINE-R pipeline.

**Job 1: Deploy Backend (Worker & D1)**

1. **Checkout Code:** Get the latest schema and API code.  
2. **Setup Node:** Install dependencies.  
3. **Apply Migrations:**  
   Bash  
   wrangler d1 migrations apply grounded-db \--remote

   *Note:* This ensures the production database schema matches the code before the new API code is deployed.40  
4. **Deploy Worker:**  
   Bash  
   wrangler deploy \--project-name grounded-wiki-api

**Job 2: Deploy Frontend (Pages)**

1. **Build React App:** Run npm run build in apps/frontend. This produces a dist/ folder.  
2. **Deploy to Pages:**  
   Bash  
   wrangler pages deploy apps/frontend/dist \--project-name grounded-wiki-frontend

**Job 3: Data Ingestion (Conditional)**

* *Trigger:* Only runs if the workflow was triggered by MINE-R (indicating new data).  
* *Action:* Downloads the AN-T artifact and runs node ingest/ingest-to-d1.js.

### **8.2 Environment Secrets**

For security, the Cloudflare credentials are never committed to the repo. They are stored in GitHub Secrets:

* CLOUDFLARE\_API\_TOKEN: Used by Wrangler for all commands.  
* CLOUDFLARE\_ACCOUNT\_ID: Required for determining the deployment target.

---

## **9\. Codex Step-by-Step Execution Checklist**

**Codex, you are authorized to execute the implementation plan. Proceed sequentially through the following phases.**

### **Phase 1: Environment Scaffolding**

1. **Request Input:** Ask the user for the intended CLOUDFLARE\_ACCOUNT\_ID and the desired DOMAIN\_NAME for the API.  
2. **Initialize Monorepo:**  
   * Create the root directory grounded-wiki-monorepo.  
   * Generate the root package.json with workspace configuration (see Section 2.3).  
   * Run npm install.  
3. **Create Directory Structure:**  
   * apps/api  
   * apps/frontend  
   * packages/schema  
   * ingest

### **Phase 2: Database & Schema**

4. **Create D1 Database:** Run wrangler d1 create grounded-db and parse the output to retrieve the database\_id.  
5. **Generate Migration:** Create packages/schema/migrations/0001\_initial\_schema.sql containing the SQL definitions from Section 3.3 (Items, ArmorStats, WeaponStats, StatusEffects, DamageTypes, FTS5 triggers).  
6. **Generate Types:** Create packages/schema/src/types.ts exporting TypeScript interfaces that mirror the SQL tables.

### **Phase 3: API Implementation**

7. **Configure Wrangler:** Generate apps/api/wrangler.toml using the database\_id from Phase 2\.  
8. **Install Dependencies:** In apps/api, install hono and the local schema package (npm install workspace:packages/schema).  
9. **Implement Server:** Generate apps/api/src/index.ts. Implement the routes:  
   * GET /items (Paginated list)  
   * GET /items/:id (Detailed relational join with json\_group\_array)  
   * GET /search (FTS5 query)  
   * GET /patch-diff/:version

### **Phase 4: Frontend Implementation**

10. **Scaffold Vite App:** Navigate to apps/frontend and run npm create vite@latest. \-- \--template react-ts.  
11. **Install Libs:** npm install react-router-dom @tanstack/react-query axios react-json-view-compare.  
12. **Create Service Layer:** Generate src/services/api.ts to encapsulate Axios calls to the Worker.  
13. **Create Components:**  
    * StatBlock.tsx (Logic for Armor Weight Class tooltips).  
    * EffectBadge.tsx (Tooltip for Status Effects).  
    * DiffView.tsx (Using react-json-view-compare).  
14. **Implement Pages:** Create ItemDetail.tsx and ItemList.tsx using the components.

### **Phase 5: Ingestion Pipeline**

15. **Create Script:** Generate ingest/ingest-to-d1.js. Implement the batching logic (Section 4.1) and string sanitization.  
16. **Test Script:** Create a dummy ant\_output.json and verify that the script generates valid SQL batches.

### **Phase 6: Deployment Configuration**

17. **Generate Workflow:** Create .github/workflows/deploy.yml matching the logic in Section 8.1.  
18. **Final Handoff:** Output a summary of the created files and instruct the user to push to GitHub to trigger the initial build.

#### **Works cited**

1. accessed November 25, 2025, [https://en.wikipedia.org/wiki/Grounded\_2\#:\~:text=It%20is%20the%20sequel%20to,and%20Xbox%20Series%20X%2FS.](https://en.wikipedia.org/wiki/Grounded_2#:~:text=It%20is%20the%20sequel%20to,and%20Xbox%20Series%20X%2FS.)  
2. Grounded 2 \- Wikipedia, accessed November 25, 2025, [https://en.wikipedia.org/wiki/Grounded\_2](https://en.wikipedia.org/wiki/Grounded_2)  
3. Armor (Grounded) \- Grounded Wiki, accessed November 25, 2025, [https://grounded.wiki.gg/wiki/Armor\_(Grounded)](https://grounded.wiki.gg/wiki/Armor_\(Grounded\))  
4. Status Effects (Grounded 2), accessed November 25, 2025, [https://grounded.wiki.gg/wiki/Status\_Effects\_(Grounded\_2)](https://grounded.wiki.gg/wiki/Status_Effects_\(Grounded_2\))  
5. Grounded 2 (Game Preview) Lands July 29 – Here's What You Need to Know \- Xbox Wire, accessed November 25, 2025, [https://news.xbox.com/en-us/2025/07/16/grounded-2-game-preview-july-29-what-you-need-to-know/](https://news.xbox.com/en-us/2025/07/16/grounded-2-game-preview-july-29-what-you-need-to-know/)  
6. What's a good way to version control an SQLite database schema? \- Stack Overflow, accessed November 25, 2025, [https://stackoverflow.com/questions/33809881/whats-a-good-way-to-version-control-an-sqlite-database-schema](https://stackoverflow.com/questions/33809881/whats-a-good-way-to-version-control-an-sqlite-database-schema)  
7. sqlite-history: tracking changes to SQLite tables using triggers (also weeknotes) \- Simon Willison, accessed November 25, 2025, [https://simonwillison.net/2023/Apr/15/sqlite-history/](https://simonwillison.net/2023/Apr/15/sqlite-history/)  
8. SQL statements \- D1 \- Cloudflare Docs, accessed November 25, 2025, [https://developers.cloudflare.com/d1/sql-api/sql-statements/](https://developers.cloudflare.com/d1/sql-api/sql-statements/)  
9. Build an API to access D1 using a proxy Worker \- Cloudflare Docs, accessed November 25, 2025, [https://developers.cloudflare.com/d1/tutorials/build-an-api-to-access-d1/](https://developers.cloudflare.com/d1/tutorials/build-an-api-to-access-d1/)  
10. Build Scalable Cloudflare Workers with Hono, D1, and KV: A Complete Guide to Serverless APIs and Storage | by Jahel | Medium, accessed November 25, 2025, [https://medium.com/@jleonro/build-scalable-cloudflare-workers-with-hono-d1-and-kv-a-complete-guide-to-serverless-apis-and-2c217a4a4afe](https://medium.com/@jleonro/build-scalable-cloudflare-workers-with-hono-d1-and-kv-a-complete-guide-to-serverless-apis-and-2c217a4a4afe)  
11. Your frontend, backend, and database — now in one Cloudflare Worker, accessed November 25, 2025, [https://blog.cloudflare.com/full-stack-development-on-cloudflare-workers/](https://blog.cloudflare.com/full-stack-development-on-cloudflare-workers/)  
12. Overview · Cloudflare Pages docs, accessed November 25, 2025, [https://developers.cloudflare.com/pages/](https://developers.cloudflare.com/pages/)  
13. D1 Database \- Cloudflare Docs, accessed November 25, 2025, [https://developers.cloudflare.com/d1/worker-api/d1-database/](https://developers.cloudflare.com/d1/worker-api/d1-database/)  
14. Build a natively serverless SQL database with Cloudflare D1, accessed November 25, 2025, [https://www.cloudflare.com/developer-platform/products/d1/](https://www.cloudflare.com/developer-platform/products/d1/)  
15. D1: We turned it up to 11 \- The Cloudflare Blog, accessed November 25, 2025, [https://blog.cloudflare.com/d1-turning-it-up-to-11/](https://blog.cloudflare.com/d1-turning-it-up-to-11/)  
16. A Quest to Find the Fastest Search Stack \- Wolk, accessed November 25, 2025, [https://www.wolk.work/blog/posts/a-quest-to-find-the-fastest-search-stack](https://www.wolk.work/blog/posts/a-quest-to-find-the-fastest-search-stack)  
17. Limits · Cloudflare D1 docs, accessed November 25, 2025, [https://developers.cloudflare.com/d1/platform/limits/](https://developers.cloudflare.com/d1/platform/limits/)  
18. Bulk import to D1 using REST API \- Cloudflare Docs, accessed November 25, 2025, [https://developers.cloudflare.com/d1/tutorials/import-to-d1-with-rest-api/](https://developers.cloudflare.com/d1/tutorials/import-to-d1-with-rest-api/)  
19. Import and export data \- D1 \- Cloudflare Docs, accessed November 25, 2025, [https://developers.cloudflare.com/d1/best-practices/import-export-data/](https://developers.cloudflare.com/d1/best-practices/import-export-data/)  
20. Limits · Cloudflare Workers docs, accessed November 25, 2025, [https://developers.cloudflare.com/workers/platform/limits/](https://developers.cloudflare.com/workers/platform/limits/)  
21. Hono · Cloudflare Workers docs, accessed November 25, 2025, [https://developers.cloudflare.com/workers/framework-guides/web-apps/more-web-frameworks/hono/](https://developers.cloudflare.com/workers/framework-guides/web-apps/more-web-frameworks/hono/)  
22. Commands \- Wrangler · Cloudflare Workers docs, accessed November 25, 2025, [https://developers.cloudflare.com/workers/wrangler/commands/](https://developers.cloudflare.com/workers/wrangler/commands/)  
23. Advanced setups · Cloudflare Workers docs, accessed November 25, 2025, [https://developers.cloudflare.com/workers/ci-cd/builds/advanced-setups/](https://developers.cloudflare.com/workers/ci-cd/builds/advanced-setups/)  
24. husniadil/cloudflare-workers-monorepo-project-template \- GitHub, accessed November 25, 2025, [https://github.com/husniadil/cloudflare-workers-monorepo-project-template](https://github.com/husniadil/cloudflare-workers-monorepo-project-template)  
25. How to Create a Monorepo With Vite, Cloudflare, Remix, PNPM and Turborepo (No Build Step) | HackerNoon, accessed November 25, 2025, [https://hackernoon.com/how-to-create-a-monorepo-with-vite-cloudflare-remix-pnpm-and-turborepo-no-build-step](https://hackernoon.com/how-to-create-a-monorepo-with-vite-cloudflare-remix-pnpm-and-turborepo-no-build-step)  
26. \[Spreadsheet\] Exact stats for ALL armor pieces (datamined); Includes exact numbers for all buffs and effects. : r/GroundedGame \- Reddit, accessed November 25, 2025, [https://www.reddit.com/r/GroundedGame/comments/ydqaas/spreadsheet\_exact\_stats\_for\_all\_armor\_pieces/](https://www.reddit.com/r/GroundedGame/comments/ydqaas/spreadsheet_exact_stats_for_all_armor_pieces/)  
27. Damage Types (Grounded 2\) \- Grounded Wiki, accessed November 25, 2025, [https://grounded.wiki.gg/wiki/Damage\_Types\_(Grounded\_2)](https://grounded.wiki.gg/wiki/Damage_Types_\(Grounded_2\))  
28. Query a database \- D1 \- Cloudflare Docs, accessed November 25, 2025, [https://developers.cloudflare.com/d1/best-practices/query-d1/](https://developers.cloudflare.com/d1/best-practices/query-d1/)  
29. Define foreign keys \- D1 \- Cloudflare Docs, accessed November 25, 2025, [https://developers.cloudflare.com/d1/sql-api/foreign-keys/](https://developers.cloudflare.com/d1/sql-api/foreign-keys/)  
30. Grounded 2 Hairy and Scary Update Patch Notes \- IGN, accessed November 25, 2025, [https://www.ign.com/wikis/grounded-2/Grounded\_2\_Hairy\_and\_Scary\_Update\_Patch\_Notes](https://www.ign.com/wikis/grounded-2/Grounded_2_Hairy_and_Scary_Update_Patch_Notes)  
31. Temporal Tables \- SQL Server | Microsoft Learn, accessed November 25, 2025, [https://learn.microsoft.com/en-us/sql/relational-databases/tables/temporal-tables?view=sql-server-ver17](https://learn.microsoft.com/en-us/sql/relational-databases/tables/temporal-tables?view=sql-server-ver17)  
32. Unlocking Time: Harnessing the power of temporal tables in SQLite \- ohneKontur, accessed November 25, 2025, [https://www.ohnekontur.de/2024/02/19/unlocking-time-harnessing-the-power-of-temporal-tables-in-sqlite/](https://www.ohnekontur.de/2024/02/19/unlocking-time-harnessing-the-power-of-temporal-tables-in-sqlite/)  
33. Query D1 from Hono \- Cloudflare Docs, accessed November 25, 2025, [https://developers.cloudflare.com/d1/examples/d1-and-hono/](https://developers.cloudflare.com/d1/examples/d1-and-hono/)  
34. Configuration \- Wrangler · Cloudflare Workers docs, accessed November 25, 2025, [https://developers.cloudflare.com/workers/wrangler/configuration/](https://developers.cloudflare.com/workers/wrangler/configuration/)  
35. Query JSON \- D1 \- Cloudflare Docs, accessed November 25, 2025, [https://developers.cloudflare.com/d1/sql-api/query-json/](https://developers.cloudflare.com/d1/sql-api/query-json/)  
36. JSON Diff \- The semantic JSON compare tool, accessed November 25, 2025, [https://jsondiff.com/](https://jsondiff.com/)  
37. React component for efficiently comparing large JSON objects with arrays \- Reddit, accessed November 25, 2025, [https://www.reddit.com/r/react/comments/1ms0ylu/react\_component\_for\_efficiently\_comparing\_large/](https://www.reddit.com/r/react/comments/1ms0ylu/react_component_for_efficiently_comparing_large/)  
38. GitHub Actions · Cloudflare Workers docs, accessed November 25, 2025, [https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/)  
39. Deploy to Cloudflare buttons \- Workers, accessed November 25, 2025, [https://developers.cloudflare.com/workers/platform/deploy-buttons/](https://developers.cloudflare.com/workers/platform/deploy-buttons/)  
40. BUG: D1 migration doesn't work on Github Actions · Issue \#3598 · cloudflare/workers-sdk, accessed November 25, 2025, [https://github.com/cloudflare/workers-sdk/issues/3598](https://github.com/cloudflare/workers-sdk/issues/3598)