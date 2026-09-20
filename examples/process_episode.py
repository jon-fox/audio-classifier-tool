#!/usr/bin/env python
"""Run the real pipeline against an episode URL using the library API.

    export OPENAI_API_KEY=<your-key>
    uv run python examples/process_episode.py "<episode-mp3-url>" \
        --podcast "My Podcast" --episode "Episode 1"

The classifier is config-driven: --detection selects what gets found and cut.
This example defaults to the ad classifier at examples/configs/ads.toon;
examples/configs/politics.toon shows a different classifier — pass it with:

    --detection examples/configs/politics.toon

Progress streams to the console; results and per-segment LLM decisions are
printed at the end.
"""

import argparse
import glob
import json
import logging
import os

import audioclassifier


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("audio_url", help="episode mp3 url")
    parser.add_argument("--podcast", default="Example Podcast")
    parser.add_argument("--episode", default="Example Episode")
    parser.add_argument(
        "--detection",
        default=os.path.join(os.path.dirname(__file__), "configs", "ads.toon"),
        help="detection config .toon path or a name in ./configs "
        "(default: the example ad classifier)",
    )
    args = parser.parse_args()

    logger = logging.getLogger("audioclassifier")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    print(f"Detection config: {args.detection}")
    result = audioclassifier.process_episode(
        podcast_name=args.podcast,
        episode_name=args.episode,
        audio_url=args.audio_url,
        detection=args.detection,
    )

    print("\n=== Result ===")
    print(f"Output:            {result['output_path']}")
    print(f"Original duration: {result['original_duration']:.0f}s")
    print(f"Filtered duration: {result['filtered_duration']:.0f}s")
    print(f"Removed:           {result['seconds_removed']:.0f}s")

    transcripts_dir = os.path.join(os.path.dirname(result["output_path"]), "transcripts")
    for path in sorted(glob.glob(os.path.join(transcripts_dir, "*_decision.json"))):
        decision = json.load(open(path))
        print(f"\n{os.path.basename(path)}: {decision['action'].upper()}")
        if decision["cut_ranges_seconds"]:
            print(f"  ranges: {decision['cut_ranges_seconds']}")
        print(f"  reasoning: {decision['reasoning']}")


if __name__ == "__main__":
    main()
