import os
import json
import sqlite3

# --- CONFIG ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STAGING_DIR = os.path.join(PROJECT_ROOT, "json_staging")
DB_PATH = os.path.join(PROJECT_ROOT, "database", "grounded_data.db")

ADD_LIST_PATH = os.path.join(PROJECT_ROOT, "files_add.json")
UPDATE_LIST_PATH = os.path.join(PROJECT_ROOT, "files_update.json")

# Path to the localization file
LOCALIZATION_PATH = os.path.join(STAGING_DIR, "Exported/Release_0_1/Localized/enus/Text/Text_enus.json")

# Media path for the website
WEB_MEDIA_ROOT = "/media/"

# Mappings
STR_TABLES_BY_ID = {
    1: "game/gui",
    2: "game/items",
    9: "game/characters",
    33: "game/statuseffects",
    195: "game/perks"
}

ARMOR_CLASSES = {
    "RogueFinisherCriticals": "Rogue",
    "FighterMajorThreat": "Fighter",
    "RangerWeakPointDamage": "Ranger",
    "MageStaffStaminaReduction": "Mage"
}
# --- END CONFIG ---

# --- Helper Functions ---

def load_localization_table():
    """Loads the entire localization table into memory for fast lookups."""
    try:
        with open(LOCALIZATION_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)[0]["Properties"]["StringTables"]
    except Exception as e:
        print(f"CRITICAL ERROR: Could not load localization file at {LOCALIZATION_PATH}. Error: {e}")
        return []

# Load localization
print("Loading localization file...")
g_localization_table = load_localization_table()

def get_localized_string(string_entry: dict) -> str:
    """Finds a display string from the global localization table."""
    if not g_localization_table or not string_entry:
        return ""
        
    table_index = string_entry.get("StringTableID", -1)
    table_id = STR_TABLES_BY_ID.get(table_index, "unknown")
    string_id = str(string_entry.get("StringID", -1))
        
    for table in g_localization_table:
        if table["Key"] == table_id:
            for entry in table["Value"]["Entries"]:
                if entry["Key"] == string_id:
                    return entry["Value"]["DefaultText"]
    return ""

def build_web_asset_path(asset: str, image: bool = False) -> str:
    """Converts an in-game asset path to a public web URL."""
    if not asset or not image:
        return ""
    
    # Example: /Game/UI/Images/StatusEffects/T_UI_SE_SetBonus.png
    if '/Game/' in asset:
        relative_path = asset.split('/Game/')[-1]
        return f"{WEB_MEDIA_ROOT}{relative_path}".replace('\\', '/')
    
    # Example: /Augusta/Content/UI/Images/StatusEffects/T_UI_SE_SetBonus.png
    if '/Augusta/Content/' in asset:
        relative_path = asset.split('/Augusta/Content/')[-1]
        return f"{WEB_MEDIA_ROOT}{relative_path}".replace('\\', '/')
        
    return ""

# --- Database Processor Functions ---

def process_status_effects(filepath, conn):
    """Parses a Table_StatusEffects.json file and updates the database."""
    print(f"Processing Status Effects from: {filepath}")
    c = conn.cursor()
    
    with open(filepath, 'r', encoding='utf-8') as f:
        rows = json.load(f)[0]["Rows"]
        
    for key, entry in rows.items():
        try:
            name = get_localized_string(entry.get("DisplayData", {}).get("Name", {}))
            icon_path = build_web_asset_path(
                entry.get("DisplayData", {}).get("Icon", {}).get("ObjectPath", ""), 
                image=True
            )
            
            c.execute("""
                INSERT OR REPLACE INTO StatusEffects (key, name, icon_path)
                VALUES (?, ?, ?)
            """, (key, name, icon_path))
            
        except Exception as e:
            print(f"Error parsing status effect '{key}': {e}")
            
    conn.commit()
    print(f"Finished processing {len(rows)} status effects.")


def process_all_items(filepath, conn):
    """Parses a Table_AllItems.json file and updates the database."""
    print(f"Processing All Items from: {filepath}")
    c = conn.cursor()
    
    with open(filepath, 'r', encoding='utf-8') as f:
        rows = json.load(f)[0]["Rows"]
        
    for key, entry in rows.items():
        try:
            equippable_data = entry.get("EquippableData", {}) or {}
            
            # Insert/Update the Item
            c.execute("""
                INSERT OR REPLACE INTO Items (
                    key, name, icon_path, tier, slot, durability,
                    flat_damage_reduction, percentage_damage_reduction
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                key,
                get_localized_string(entry.get("LocalizedDisplayName", {})),
                build_web_asset_path(entry.get("Icon", {}).get("AssetPathName", ""), image=True),
                entry.get("Tier", -1),
                entry.get("Slot", "None").replace("EEquipmentSlot::", ""),
                equippable_data.get("Durability", 0.0),
                equippable_data.get("FlatDamageReduction", 0.0),
                equippable_data.get("PercentageDamageReduction", 0.0)
            ))
            
            c.execute("DELETE FROM Item_StatusEffects WHERE item_key = ?", (key,))
            
            for effect in equippable_data.get("StatusEffects", []):
                effect_key = effect.get("RowName", "")
                if effect_key:
                    c.execute("""
                        INSERT OR REPLACE INTO Item_StatusEffects (item_key, effect_key, is_hidden)
                        VALUES (?, ?, 0)
                    """, (key, effect_key))
            
            for effect in equippable_data.get("HiddenStatusEffects", []):
                effect_key = effect.get("RowName", "")
                if effect_key:
                    c.execute("""
                        INSERT OR REPLACE INTO Item_StatusEffects (item_key, effect_key, is_hidden)
                        VALUES (?, ?, 1)
                    """, (key, effect_key))

        except Exception as e:
            print(f"Error parsing item '{key}': {e}")
            
    conn.commit()
    print(f"Finished processing {len(rows)} items.")


def process_item_sets(filepath, conn):
    """Parses a Table_ItemSets.json file and updates the database."""
    print(f"Processing Item Sets from: {filepath}")
    c = conn.cursor()
    
    with open(filepath, 'r', encoding='utf-8') as f:
        rows = json.load(f)[0]["Rows"]
        
    for key, entry in rows.items():
        try:
            item_keys = [row.get("RowName") for row in entry.get("Items", []) if row.get("RowName")]
            effect_keys = [row.get("RowName") for row in entry.get("StatusEffects", []) if row.get("RowName")]
            
            set_items_data = []
            if item_keys:
                query = f"SELECT name, tier, slot FROM Items WHERE key IN ({','.join('?'*len(item_keys))})"
                c.execute(query, item_keys)
                set_items_data = c.fetchall()

            # Get Common Name
            item_names = [row[0] for row in set_items_data if row[0]]
            common = []
            if item_names:
                splits = [name.split() for name in item_names]
                common = [word for word in splits[0] if all(word in s for s in splits[1:])]
            set_name = " ".join(common) or "Unknown"
            
            # Get Tier
            tiers = list(set([row[1] for row in set_items_data if row[1]]))
            set_tier = tiers[0] if tiers else -1
            
            # Get Class
            set_class = ""
            if item_keys:
                query = f"""
                    SELECT effect_key FROM Item_StatusEffects 
                    WHERE item_key IN ({','.join('?'*len(item_keys))})
                """
                c.execute(query, item_keys)
                item_effect_keys = [row[0] for row in c.fetchall()]
                for effect_key in item_effect_keys:
                    if effect_key in ARMOR_CLASSES:
                        set_class = ARMOR_CLASSES[effect_key]
                        break
            
            # Insert/Update the ArmorSet
            c.execute("""
                INSERT OR REPLACE INTO ArmorSets (key, name, tier, class)
                VALUES (?, ?, ?, ?)
            """, (key, f"{set_name} Armor", set_tier, set_class))
            
            c.execute("DELETE FROM ArmorSet_Items WHERE set_key = ?", (key,))
            for item_key in item_keys:
                c.execute("INSERT OR REPLACE INTO ArmorSet_Items (set_key, item_key) VALUES (?, ?)", (key, item_key))
            
            c.execute("DELETE FROM ArmorSet_Effects WHERE set_key = ?", (key,))
            for effect_key in effect_keys:
                c.execute("INSERT OR REPLACE INTO ArmorSet_Effects (set_key, effect_key) VALUES (?, ?)", (key, effect_key))

        except Exception as e:
            print(f"Error parsing item set '{key}': {e}")

    conn.commit()
    print(f"Finished processing {len(rows)} item sets.")


# --- Main Execution ---

def main():
    """
    Main function to run the database update process.
    """
    try:
        with open(ADD_LIST_PATH, 'r', encoding='utf-8') as f:
            files_to_add = json.load(f)
        with open(UPDATE_LIST_PATH, 'r', encoding='utf-8') as f:
            files_to_update = json.load(f)
    except FileNotFoundError:
        print("Error: `files_add.json` or `files_update.json` not found.")
        print("Please run `4_process_manifest.py` first.")
        return

    files_to_process = files_to_add + files_to_update
    if not files_to_process:
        print("No new or updated files to process. Database is up to date.")
        return

    print(f"Connecting to database at {DB_PATH}...")
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # --- File Processing Router ---
        # Routes files to the correct parser function.
        print("Starting Pass 1: Core Data (Effects, Items)...")
        for relative_path in files_to_process:
            filepath = os.path.join(STAGING_DIR, relative_path)
            
            if "Table_StatusEffects.json" in relative_path:
                process_status_effects(filepath, conn)
            
            if "Table_AllItems.json" in relative_path:
                process_all_items(filepath, conn)
            
            # ... (Add other core parsers here: Recipes, Creatures, etc.) ...
        
        print("Starting Pass 2: Relational Data (Item Sets)...")
        for relative_path in files_to_process:
            filepath = os.path.join(STAGING_DIR, relative_path)
            
            if "Table_ItemSets.json" in relative_path:
                process_item_sets(filepath, conn)
                
            # ... (Add other relational parsers here) ...

        print("-" * 30)
        print("Database update complete.")

    except sqlite3.Error as e:
        print(f"An error occurred with the database: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    if not g_localization_table:
        print("Halting execution. Localization file failed to load.")
    else:
        main()
