import sqlite3
import os

DB_DIR = "database"
DB_NAME = "grounded_data.db"
DB_PATH = os.path.join(DB_DIR, DB_NAME)

def create_schema():
    """
    Creates the initial database schema in database/grounded_data.db
    """
    # Ensure the database directory exists
    os.makedirs(DB_DIR, exist_ok=True)
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # --- Main Data Tables ---
        
        c.execute('''
        CREATE TABLE IF NOT EXISTS Items (
            key TEXT PRIMARY KEY,
            name TEXT,
            icon_path TEXT,
            tier INTEGER,
            slot TEXT,
            durability REAL,
            flat_damage_reduction REAL,
            percentage_damage_reduction REAL
        )''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS StatusEffects (
            key TEXT PRIMARY KEY,
            name TEXT,
            icon_path TEXT
        )''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS ArmorSets (
            key TEXT PRIMARY KEY,
            name TEXT,
            tier INTEGER,
            class TEXT
        )''')

        # --- Join Tables ---

        c.execute('''
        CREATE TABLE IF NOT EXISTS ArmorSet_Items (
            set_key TEXT,
            item_key TEXT,
            PRIMARY KEY (set_key, item_key),
            FOREIGN KEY(set_key) REFERENCES ArmorSets(key) ON DELETE CASCADE,
            FOREIGN KEY(item_key) REFERENCES Items(key) ON DELETE CASCADE
        )''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS ArmorSet_Effects (
            set_key TEXT,
            effect_key TEXT,
            PRIMARY KEY (set_key, effect_key),
            FOREIGN KEY(set_key) REFERENCES ArmorSets(key) ON DELETE CASCADE,
            FOREIGN KEY(effect_key) REFERENCES StatusEffects(key) ON DELETE CASCADE
        )''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS Item_StatusEffects (
            item_key TEXT,
            effect_key TEXT,
            is_hidden INTEGER DEFAULT 0,
            PRIMARY KEY (item_key, effect_key),
            FOREIGN KEY(item_key) REFERENCES Items(key) ON DELETE CASCADE,
            FOREIGN KEY(effect_key) REFERENCES StatusEffects(key) ON DELETE CASCADE
        )''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS Recipes (
            item_key TEXT PRIMARY KEY, -- The item this recipe crafts
            type TEXT NOT NULL, -- 'Crafting' or 'Repair'
            FOREIGN KEY(item_key) REFERENCES Items(key) ON DELETE CASCADE
        )''')
        
        c.execute('''
        CREATE TABLE IF NOT EXISTS Recipe_Ingredients (
            recipe_item_key TEXT,
            recipe_type TEXT,
            ingredient_item_key TEXT,
            quantity INTEGER,
            PRIMARY KEY (recipe_item_key, recipe_type, ingredient_item_key),
            FOREIGN KEY(recipe_item_key) REFERENCES Recipes(item_key) ON DELETE CASCADE,
            FOREIGN KEY(ingredient_item_key) REFERENCES Items(key) ON DELETE CASCADE
        )''')

        conn.commit()
        print(f"Success: Database schema created at {DB_PATH}")

    except sqlite3.Error as e:
        print(f"Error creating database schema: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_schema()
