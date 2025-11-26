This document serves as the **Master Implementation Plan** for the **Grounded 2 Wiki Architecture**. It is designed to be fed into OpenAI Codex (or similar IDE agents) to generate the complete codebase for the web hosting, API, and database layers of the MINE-R project.

---

# **Grounded 2 Wiki: Cloudflare Implementation Plan**

## **1\. Introduction & High-Level Architecture**

This system extends the existing **MINE-R** (Extraction) and **AN-T** (Normalization) pipelines. While the existing pipeline runs locally to produce clean data, this new layer publishes that data to the edge for public consumption.

### **Architecture Diagram**

Code snippet

graph TD  
    Local\_ANT\[AN-T Output JSON/SQL\] \--\>|Ingestion Script| D1\[Cloudflare D1 Database\]  
    D1 \--\>|Query| Worker\[Cloudflare Worker API\]  
    User\[Web User\] \--\>|HTTPS| Pages\[Cloudflare Pages Frontend\]  
    Pages \--\>|Fetch JSON| Worker

### **Core Stack**

* **Database:** Cloudflare D1 (Serverless SQLite).  
* **API:** Cloudflare Workers (using Hono framework).  
* **Frontend:** Cloudflare Pages (React \+ Vite \+ Tailwind).  
* **Ingestion:** Python script bridging MINE-R output to wrangler d1 execute.

---

## **2\. Project Repository Structure**

Codex must restructure the existing MINE-R repository to accommodate the web stack without disrupting the Python/PowerShell extractors.

**Target Directory Structure:**

Plaintext

MINE-R/  
├── scripts/                  \# (Existing MINE-R scripts)  
├── tools/                    \# (Existing tools)  
├── data/                     \# (Local output of MINE-R/AN-T)  
├── web/                      \# \[NEW\] The Cloudflare Monorepo Root  
│   ├── api/                  \# \[NEW\] Cloudflare Worker (Hono)  
│   │   ├── src/  
│   │   ├── wrangler.toml  
│   │   └── package.json  
│   ├── frontend/             \# \[NEW\] React \+ Vite App  
│   │   ├── src/  
│   │   ├── public/  
│   │   └── package.json  
│   └── database/             \# \[NEW\] D1 Schemas & Migrations  
│       ├── schema.sql  
│       └── migrations/  
└── ingest/                   \# \[NEW\] Deployment scripts  
    └── deploy\_to\_d1.py       \# Pushes local data to Cloudflare D1

---

## **3\. D1 Schema & Data Model**

**Objective:** Define the SQL schema for Cloudflare D1 based on the normalized ontology from **AN-T Section 6.1** and **MINE-R Section 4.1**.

### **Schema Definition**

Codex will generate a file web/database/schema.sql.

SQL

\-- 0000\_initial.sql

\-- CORE TABLES  
CREATE TABLE IF NOT EXISTS StatusEffects (  
    effect\_id TEXT PRIMARY KEY,  
    name TEXT NOT NULL,  
    description TEXT,  
    category TEXT, \-- 'positive', 'negative', 'set\_bonus'  
    icon\_path TEXT  
);

CREATE TABLE IF NOT EXISTS ArmorSets (  
    set\_id INTEGER PRIMARY KEY AUTOINCREMENT,  
    set\_name TEXT UNIQUE NOT NULL,  
    set\_bonus\_effect\_id TEXT REFERENCES StatusEffects(effect\_id)  
);

CREATE TABLE IF NOT EXISTS Items (  
    item\_id TEXT PRIMARY KEY,  
    name TEXT NOT NULL,  
    description TEXT,  
    icon\_path TEXT,  
    tier INTEGER,  
      
    \-- Classification (AN-T Phase 3\)  
    item\_class TEXT, \-- 'Heavy Armor', 'Sword'  
    slot TEXT,       \-- 'Head', 'Upper Body'  
      
    \-- Stats (AN-T Phase 1 & 3\)  
    durability REAL,  
    dr\_base REAL,  
    resistance\_base REAL,  
      
    \-- Relationships  
    armor\_set\_id INTEGER REFERENCES ArmorSets(set\_id)  
);

\-- JOIN TABLES  
CREATE TABLE IF NOT EXISTS Item\_Effects (  
    item\_id TEXT NOT NULL REFERENCES Items(item\_id),  
    effect\_id TEXT NOT NULL REFERENCES StatusEffects(effect\_id),  
    source TEXT NOT NULL, \-- 'Base', 'Sleek', 'Set Bonus'  
    PRIMARY KEY (item\_id, effect\_id, source)  
);

CREATE TABLE IF NOT EXISTS Item\_DamageTypes (  
    item\_id TEXT NOT NULL REFERENCES Items(item\_id),  
    damage\_type TEXT NOT NULL, \-- 'Slashing', 'Spicy'  
    is\_base\_type BOOLEAN DEFAULT 1,  
    PRIMARY KEY (item\_id, damage\_type)  
);

CREATE TABLE IF NOT EXISTS Recipes (  
    recipe\_id TEXT PRIMARY KEY,  
    result\_item\_id TEXT REFERENCES Items(item\_id),  
    amount INTEGER DEFAULT 1  
);

\-- INDEXES  
CREATE INDEX idx\_items\_name ON Items(name);  
CREATE INDEX idx\_items\_set ON Items(armor\_set\_id);  
CREATE INDEX idx\_effects\_name ON StatusEffects(name);

---

## **4\. Data Ingestion Pipeline**

**Objective:** Automate the transfer of AN-T's locally processed data into the remote D1 instance.

### **Strategy**

Directly uploading a .db file to D1 is not recommended for incremental updates. Instead, we will use a Python script to generate a batch of SQL statements and execute them via wrangler.

### **Script Specification: ingest/deploy\_to\_d1.py**

Codex must implement this script with the following logic:

1. **Load Data:** Connect to the local database/grounded\_data.db (produced by MINE-R/AN-T).  
2. **Batch Generation:** Iterate through tables (Items, ArmorSets, etc.).  
3. **Sanitization:** Escape quotes and handle NULLs.  
4. **SQL Construction:** Generate INSERT OR REPLACE INTO... statements.  
5. **Execution:** Use subprocess to call:  
6. Bash

npx wrangler d1 execute grounded-wiki-db \--file=./temp\_batch\_import.sql \--remote

7.   
8.   
9. **Optimization:** Split into chunks (e.g., 100 rows per batch) to avoid Cloudflare payload limits.

---

## **5\. Workers API Implementation Plan**

**Objective:** Create a high-performance, read-heavy API using **Hono** on Cloudflare Workers.

**Location:** web/api/

### **Endpoints**

1. **GET /api/items**  
   * **Query Params:** ?limit=50\&offset=0\&search=acorn\&class=Heavy  
   * **Logic:** Select from Items. Join ArmorSets for set names.  
   * **Response:** JSON array of simplified Item objects.  
2. **GET /api/items/:id**  
   * **Logic:** Fetch full Item details.  
   * **Sub-queries:**  
     * Fetch related Item\_Effects (join StatusEffects).  
     * Fetch Item\_DamageTypes.  
     * Fetch Recipes where this item is the result.  
   * **Response:** Comprehensive JSON object (Wiki Page data).  
3. **GET /api/armor-sets**  
   * **Logic:** List all armor sets with their member items nested.  
   * **Response:** JSON List.  
4. **GET /api/search**  
   * **Query Params:** ?q=query  
   * **Logic:** SELECT \* FROM Items WHERE name LIKE ? OR description LIKE ? (Basic search for MVP).

### **Codex Configuration Details**

* **wrangler.toml**: Must bind the D1 database as binding \= "DB".  
* **CORS**: Enable CORS middleware in Hono to allow requests from the Pages domain.

---

## **6\. Frontend (Pages) Implementation Plan**

**Objective:** A clean, searchable Wiki interface.

Location: web/frontend/

Stack: React, Vite, Tailwind CSS, TanStack Query (for API caching).

### **Page Architecture**

1. **Home (/)**: Search bar, "Recently Updated" (using AN-T's diff detection if available), and Category tiles (Armor, Weapons, Tools).  
2. **Item Detail (/item/:id)**:  
   * **Header:** Icon, Name, Tier, Class (Heavy/Medium/Light).  
   * **Stats Grid:** Durability, DR %, Resistance %.  
   * **Damage/Effects:** Visual tags for Damage Types (Slashing) and Effects (Buffs).  
   * **Set Context:** "Part of \[Set Name\]" link.  
   * **Recipe:** Ingredients list.  
3. **Armor Sets (/sets)**: visual grid of full armor sets.

### **Asset Handling**

* **Images:** MINE-R extracts images locally.  
* **Deployment:** The ingest pipeline should upload extracted icons to an R2 bucket (Object Storage) or strictly copy them to the web/frontend/public/assets folder during build time so they are served as static assets by Pages. **Recommendation for Codex:** Copy to public/assets for simplicity in V1.

---

## **7\. CI/CD & Deployment Plan**

**Objective:** Automate deployment via GitHub Actions.

### **GitHub Actions Workflow: .github/workflows/deploy.yml**

Codex must generate a workflow that:

1. **Triggers:** On push to main.  
2. **Job 1: Deploy API (Worker)**  
   * cd web/api  
   * npm install  
   * npx wrangler deploy  
3. **Job 2: Deploy Frontend (Pages)**  
   * cd web/frontend  
   * npm install  
   * npm run build  
   * npx wrangler pages deploy dist

*Note: Database Ingestion is NOT in CI. It is a manual trigger run by the data maintainer (User) after running MINE-R locally, as it requires the large game assets.*

---

## **8\. Step-by-Step Execution Checklist for Codex**

**Codex, execute the following steps in order. Stop after each step to confirm success.**

### **Phase 1: Initialization**

1. Initialize a new Cloudflare project structure inside web/.  
2. Create web/api (Worker) using the Hono template.  
3. Create web/frontend (Pages) using Vite (React \+ TS).  
4. Create web/database folder.

### **Phase 2: Database Setup**

5. Generate the web/database/schema.sql file containing the tables defined in Section 3\.  
6. Ask the user to run: npx wrangler d1 create grounded-wiki-db.  
7. Ask the user to run: npx wrangler d1 execute grounded-wiki-db \--file=web/database/schema.sql \--remote.

### **Phase 3: The API Layer**

8. Modify web/api/wrangler.toml to bind the D1 database.  
9. Install hono in web/api.  
10. Generate web/api/src/index.ts implementing the endpoints defined in Section 5\. Ensure c.env.DB is used for queries.

### **Phase 4: The Ingestion Script**

11. Create ingest/deploy\_to\_d1.py.  
12. Implement the SQLite-to-SQL logic defined in Section 4\. Ensure it reads from database/grounded\_data.db (the MINE-R output).  
13. Add a helper function to copy extracted images from legacy\_assets/... to web/frontend/public/assets/... so the frontend has icons.

### **Phase 5: The Frontend**

14. Setup Tailwind CSS in web/frontend.  
15. Create a client.ts api wrapper to fetch from the Worker URL.  
16. Scaffolding the ItemDetail component to display the complex JSON data (Effects, Damage Types).  
17. Scaffolding the Search component.

### **Phase 6: Deployment**

18. Generate the .github/workflows/deploy.yml file.  
19. Provide the user with a final summary of commands to run the first full ingestion.

