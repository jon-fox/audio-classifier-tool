import json

def make_label(label_name, start_time, end_time, full_text, out_path="ad_label.txt"):
    """Create a label entry from manual input and write to a text file."""
    snippet = full_text.strip()
    char_start = full_text.find(snippet)
    char_end = char_start + len(snippet)

    label = {
        "label": label_name,
        "char_start": char_start,
        "char_end": char_end,
        "start_time": float(start_time),
        "end_time": float(end_time),
        "text_snippet": snippet,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(label, ensure_ascii=False, indent=2))

    print(f"\nLabel written to {out_path}. Copy-paste ready:\n")
    print(json.dumps(label, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # Ask user for input
    label_name = input("Label name (default: Ad): ") or "Ad"
    start_time = input("Start time (seconds): ")
    end_time = input("End time (seconds): ")
    print("Paste ad text below, then press ENTER + CTRL+D (or CTRL+Z on Windows) when done:\n")

    # Read multiline input from terminal
    import sys
    ad_text = sys.stdin.read()

    make_label(label_name, start_time, end_time, ad_text)
