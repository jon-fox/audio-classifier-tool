import json
import os
import sys

def fix_char_positions(json_file_path):
    """
    Fixes the char_start and char_end for labels in the JSON file by finding the text_snippet in the text field.
    
    Args:
        json_file_path (str): Path to the JSON file to fix.
    """
    if not os.path.exists(json_file_path):
        print(f"File {json_file_path} not found.")
        return
    
    # Load the JSON file
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    text = data.get("text", "")
    labels = data.get("labels", [])
    
    for label in labels:
        text_snippet = label.get("text_snippet", "").strip()
        if text_snippet:
            pos = text.find(text_snippet)
            if pos != -1:
                label["char_start"] = pos
                label["char_end"] = pos + len(text_snippet)
                print(f"Fixed label: {text_snippet[:50]}... at {pos}-{pos + len(text_snippet)}")
            else:
                print(f"Could not find text_snippet: {text_snippet[:50]}...")
    
    # Save the updated JSON
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Updated {json_file_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        # Default: look for JSON files in training/ directory or subdirectories
        training_dir = os.path.join(os.path.dirname(__file__), '..')
        json_files = []
        for root, dirs, files in os.walk(training_dir):
            for file in files:
                if file.endswith('_training_data.json'):
                    json_files.append(os.path.join(root, file))
        if json_files:
            json_file = json_files[0]  # Take the first one
            print(f"Using file: {json_file}")
        else:
            print("No _training_data.json file found in training/ directory.")
            sys.exit(1)
    
    fix_char_positions(json_file)
