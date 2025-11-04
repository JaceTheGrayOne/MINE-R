import os
import json
import hashlib

# --- CONFIG ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STAGING_DIR = os.path.join(PROJECT_ROOT, "json_staging")
MANIFEST_PATH = os.path.join(PROJECT_ROOT, "manifest.json")
ADD_LIST_PATH = os.path.join(PROJECT_ROOT, "files_add.json")
UPDATE_LIST_PATH = os.path.join(PROJECT_ROOT, "files_update.json")
# --- END CONFIGURATION ---

def get_canonical_hash(json_filepath):
    """
    Loads a JSON file, creates a sorted, compact string
    representation, and returns its SHA-256 hash.
    This ignores formatting changes and file offsets.
    """
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Create a canonical string: sorted keys, no whitespace
        canonical_string = json.dumps(data, sort_keys=True, separators=(',', ':'))
        
        # Hash the resulting string
        hash_object = hashlib.sha256(canonical_string.encode('utf-8'))
        return hash_object.hexdigest()
        
    except Exception as e:
        print(f"Warning: Could not process hash for {json_filepath}. Reason: {e}")
        return None

def process_manifest():
    """
    Compares JSONs in STAGING_DIR against MANIFEST_PATH to find changes.
    Outputs files_add.json and files_update.json.
    """
    print(f"Processing manifest. Comparing {STAGING_DIR} against {MANIFEST_PATH}...")
    
    # Load manifest
    try:
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            old_manifest = json.load(f)
    except FileNotFoundError:
        print("No old manifest found. This must be the first run.")
        old_manifest = {}
    
    # Scan staging dir and generate new manifest
    new_manifest = {}
    for root, _, files in os.walk(STAGING_DIR):
        for file in files:
            if file.endswith(".json"):
                json_path = os.path.join(root, file)
                # Use relative path as the key
                relative_path = os.path.relpath(json_path, STAGING_DIR)
                
                content_hash = get_canonical_hash(json_path)
                if content_hash:
                    new_manifest[relative_path] = content_hash

    # Compare manifests
    old_files = set(old_manifest.keys())
    new_files = set(new_manifest.keys())

    files_to_add = list(new_files - old_files)
    files_to_delete = list(old_files - new_files)
    
    files_to_update = []
    # Check for content changes in files that exist in both
    for path in (old_files & new_files):
        if old_manifest[path] != new_manifest[path]:
            files_to_update.append(path)
            
    # Save the new manifest
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(new_manifest, f, indent=2)
        
    # Save the lists for the database script
    with open(ADD_LIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(files_to_add, f, indent=2)
        
    with open(UPDATE_LIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(files_to_update, f, indent=2)

    print("-" * 30)
    print("Manifest processing complete.")
    print(f"New files added:     {len(files_to_add)}")
    print(f"Existing files updated: {len(files_to_update)}")
    print(f"Files removed:       {len(files_to_delete)}")
    print(f"To-do lists saved to {ADD_LIST_PATH} and {UPDATE_LIST_PATH}")

if __name__ == "__main__":
    process_manifest()
