#!/usr/bin/env python
"""Train the self-distilled ad classifier from past runs' decision files.

    uv run python examples/train_classifier.py [output-dir]

Every processed episode adds training data (transcripts labeled by the LLM's
cut/keep decisions under output/). Once trained, runs automatically feed the
classifier's flags to the LLM as an extra detection signal.
"""

import sys

import audioclassifier


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else None
    metrics = audioclassifier.train_text_classifier(output_dir)
    print("Trained:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
