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
        pos = -1
        snippet = label.get("text_snippet", "")  # no .strip()
        if snippet:
            hint = label.get("char_start", 0)
            # try near the previous position first
            pos = text.find(snippet, max(0, hint - 50))
            if pos == -1:
                pos = text.find(snippet)
            if pos != -1 and text[pos:pos+len(snippet)] == snippet:
                label["char_start"] = pos
                label["char_end"] = pos + len(snippet)
                print(f"Fixed label: {snippet[:50]}... at {pos}-{pos + len(snippet)}")
            else:
                print(f"[WARN] Could not align snippet (len={len(snippet)})")
    
    # Save the updated JSON
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Updated {json_file_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        # Default: look for JSON files in output/ directory
        output_dir = "training/output"
        if os.path.exists(output_dir):
            json_files = [f for f in os.listdir(output_dir) if f.endswith('.json')]
            if json_files:
                json_file = os.path.join(output_dir, json_files[0])  # Take the first one
                print(f"Using file: {json_file}")
            else:
                print("No JSON files found in training/output/ directory.")
                sys.exit(1)
        else:
            print("Output directory does not exist.")
            sys.exit(1)
    
    fix_char_positions(json_file)
