import json
import os
import sys

def update_label_times(json_file_path):
    """
    Updates the start_time and end_time for labels by finding the corresponding segments.
    
    Args:
        json_file_path (str): Path to the JSON file to update.
    """
    if not os.path.exists(json_file_path):
        print(f"File {json_file_path} not found.")
        return
    
    # Load the JSON file
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    text = data.get("text", "")
    segments = data.get("segments", [])
    labels = data.get("labels", [])
    
    # Build cumulative positions for segments
    cumulative = 0
    segment_positions = []
    for seg in segments:
        seg_text = seg["text"]
        start_pos = cumulative
        end_pos = cumulative + len(seg_text)
        segment_positions.append({
            "start_pos": start_pos,
            "end_pos": end_pos,
            "start_time": seg["start"],
            "end_time": seg["end"]
        })
        cumulative = end_pos + 1  # +1 for space, but approximately
    
    for label in labels:
        char_start = label.get("char_start")
        char_end = label.get("char_end")
        if char_start is None or char_end is None:
            continue
        
        # Find start_time
        start_time = None
        for pos in segment_positions:
            if pos["start_pos"] <= char_start < pos["end_pos"]:
                start_time = pos["start_time"]
                break
        
        # Find end_time
        end_time = None
        for pos in reversed(segment_positions):  # Start from the end
            if pos["start_pos"] < char_end <= pos["end_pos"]:
                end_time = pos["end_time"]
                break
        
        if start_time is not None:
            label["start_time"] = start_time
            print(f"Updated start_time to {start_time}")
        
        if end_time is not None:
            label["end_time"] = end_time
            print(f"Updated end_time to {end_time}")
        
        if start_time is not None and end_time is not None and end_time < start_time:
            print(f"Warning: end_time {end_time} < start_time {start_time} for label at {char_start}-{char_end}")
    
    # Save the updated JSON
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Updated {json_file_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        # Default: look for JSON files in training/ directory or subdirectories
        script_dir = os.path.dirname(__file__)
        training_dir = os.path.join(script_dir, '..')
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
    
    update_label_times(json_file)
