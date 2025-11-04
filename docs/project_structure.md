This guide details the full, end-to-end process for building an automated data pipeline for Grounded 2\.
The goal is to extract raw game data, process it, identify changes, store it in a local database, and make it available for a modern web frontend.
This workflow is designed to be managed in a Visual Studio Code workspace and orchestrated by a local AI assistant like Claude Code.

## **Core Concepts**

* **Change Detection:** We will **not** use file timestamps or standard file hashes (like SHA-256) on the raw .uasset files. Unreal Engine changes file offsets during extraction, which would create false positives. Instead, we will convert data tables to JSON and then perform a **"Canonical Content Hash"** on the JSON data. This hashes the *semantic content* (sorted, whitespace-removed) to accurately detect real data changes.  
* **Automation:** The process is broken into a series of scripts (PowerShell and Python) that can be run in sequence. This turns a multi-hour manual task into a single, automated workflow.  
* **Persistence:** All structured data will be stored in a local **SQLite** database. This database will be the "single source of truth" for your frontend, making it fast and easy to query.

## **Prerequisites**

Before you begin, ensure you have the following tools installed and accessible:

* **Retoc:** Your tool for extracting .uasset files from the game's .pak archives.  
* **UAssetAPI (or similar):** A tool or library capable of converting .uasset files to .json. The scripts will assume it has a CLI or is a Python library.  
* **PowerShell:** For scripting the file extraction and conversion steps.  
* **Python 3.x:** For the data parsing and database logic.  
* **Node.js:** For the frontend web project (e.g., Astro or Next.js).  
* **VSC \+ Claude Code:** Your development environment for building and running this pipeline.

## **Project Structure**

Your VSC workspace should be organized as follows. This structure is critical for the scripts to find each other and the data.

/grounded-wiki-pipeline/  
├── .gitignore  
├── instruction.md           \# Guiding context for Claude (Appendix 2\)  
├── manifest.json            \# Stores the hashes of all processed JSONs  
├── database/  
│   └── grounded\_data.db     \# Your final SQLite database  
│  
├── frontend/                \# Your Astro/Next.js website project  
│   └── ...  
│  
├── raw\_extracted/           \# (Ignored by Git) Output of Step 1 (Retoc)  
│   └── Augusta/  
│       └── Content/  
│           └── ... (all raw .uasset and .png files)  
│  
├── datatables\_filtered/     \# (Ignored by Git) Output of Step 2 (Filtered .uasset files)  
│   └── ...  
│  
├── json\_staging/            \# (Ignored by Git) Output of Step 3 (Converted .json files)  
│   └── ...  
│  
└── scripts/                 \# All your automation scripts (Appendix 3\)  
    ├── 0\_setup\_database.py  
    ├── 1\_extract\_gamedata.ps1  
    ├── 2\_filter\_datatables.ps1  
    ├── 3\_convert\_uassets.py   \# Changed to Python for UAssetAPI library  
    ├── 4\_process\_manifest.py  
    ├── 5\_update\_database.py  
    └── master\_run.ps1         \# An orchestrator script

## **The Step-by-Step Workflow**

Here is the detailed process for your pipeline. The ready-to-use code for each script is in **Appendix 3**.

### **Step 0: Create the Database Schema**

**Script:** scripts/0\_setup\_database.py

* **Purpose:** To create the SQLite database (grounded\_data.db) and all the necessary tables *before* any data is inserted.  
* **Action:** This Python script uses sqlite3 to execute CREATE TABLE commands for Items, ArmorSets, StatusEffects, Recipes, and the join tables needed to link them.  
* **How to run:** Run this script *once* manually or via Claude to initialize your project.

### **Step 1: Extract Raw Game Assets**

**Script:** scripts/1\_extract\_gamedata.ps1

* **Purpose:** To extract all game assets (.uasset, .png, etc.) from the game's .pak files.  
* **Action:** This PowerShell script calls your **Retoc** tool and tells it to dump all extracted contents into the /raw\_extracted/ folder.  
* **Note:** You must edit this script to point to your correct Retoc executable and game data path.

### **Step 2: Filter Data Tables**

**Script:** scripts/2\_filter\_datatables.ps1

* **Purpose:** To find only the data tables you care about (e.g., DT\_ and Table\_ files) and copy them to a clean location.  
* **Action:** This PowerShell script recursively scans the /raw\_extracted/ folder. It copies any file prefixed with DT\_ or containing Table into the /datatables\_filtered/ folder, preserving the directory structure.

### **Step 3: Convert UAssets to JSON**

**Script:** scripts/3\_convert\_uassets.py

* **Purpose:** To convert the filtered .uasset data tables into a human-readable JSON format for parsing.  
* **Action:** This Python script (using the **UAssetAPI** library) scans the /datatables\_filtered/ folder, loads each .uasset file, and saves it as a .json file in the /json\_staging/ folder.

### **Step 4: Detect Changes via Canonical Hash**

**Script:** scripts/4\_process\_manifest.py

* **Purpose:** This is the core of your change-detection. It compares the newly converted JSON files against a "manifest" of previously processed files to see what *actually* changed.  
* **Action:**  
  1. Loads manifest.json (which stores {"filename": "content\_hash"}).  
  2. Scans /json\_staging/ and generates a **canonical content hash** for each JSON file (ignores formatting and offset changes).  
  3. Compares the new hashes to the old manifest.  
  4. Generates two "to-do" lists: files\_add.json and files\_update.json.  
  5. Overwrites manifest.json with the new hashes for the next run.

### **Step 5: Update the Database**

**Script:** scripts/5\_update\_database.py

* **Purpose:** To parse the changed JSON files and update the SQLite database.  
* **Action:**  
  1. Reads files\_add.json and files\_update.json to get the list of files to process.  
  2. For each file, it opens the corresponding JSON from /json\_staging/.  
  3. It uses parsing logic (adapted from your friend's script) to extract the data.  
  4. It connects to database/grounded\_data.db and uses INSERT OR REPLACE INTO ... (an "upsert" command) to add new data or overwrite changed data.

### **Step 6: Build the Frontend**

**Project:** /frontend/

* **Purpose:** To display the data to the user.  
* **Action:** This is your Astro or Next.js project. It connects *directly* to the database/grounded\_data.db file (SQLite is just a file) during its build process.  
* **Example (Astro):** You can write code on your pages like this:  
  // src/pages/armor.astro  
  import { db, Items, ArmorSets } from '../db/config'; // Your DB config

  // This code runs at build time  
  const sets \= await db.select().from(ArmorSets).all();  
  \---  
  \<h1\>All Armor Sets\</h1\>  
  \<ul\>  
    {sets.map(set \=\> (  
      \<li\>\<a href={\`/armor/${set.key}\`}\>{set.name}\</a\>\</li\>  
    ))}  
  \</ul\>  
