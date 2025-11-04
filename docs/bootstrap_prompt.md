I am building a data pipeline for Grounded 2. Please analyze the contents and structure of all the `.json` files located in the `/json_staging/` directory.
>
> Pay close attention to data types, nested objects, and arrays (which will need to become related tables).
>
> Based on your analysis, please write a new Python script named `scripts/0_setup_database.py`. This script must:
> 1.  Use the standard `sqlite3` library.
> 2.  Define a constant `DB_PATH = "database/grounded_data.db"`.
> 3.  Create a function `create_schema()` that connects to the database and executes all necessary `CREATE TABLE IF NOT EXISTS` commands.
> 4.  The schema must be normalized. This means you should create:
>     * Main tables (e.g., `Items`, `ArmorSets`, `StatusEffects`, `Recipes`).
>     * Join tables for many-to-many relationships (e.g., `ArmorSetItems`, `RecipeIngredients`, `ItemStatusEffects`).
> 5.  Use appropriate primary keys (`TEXT PRIMARY KEY` for keys like "HeadAcorn") and foreign keys to link the tables.
> 6.  Include `IF NOT EXISTS` to make the script safe to re-run.
> 7.  Add a `if __name__ == "__main__":` block to call the `create_schema()` function and print a success message."
