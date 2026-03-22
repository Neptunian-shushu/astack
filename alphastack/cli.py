import argparse
from pathlib import Path

from alphastack.config import AlphaStackConfig
from alphastack.core.pipeline import AlphaPipeline
from alphastack.adapters.example_adapter import ExampleAdapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AlphaStack CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the alpha research pipeline")
    run.add_argument("--goal", required=True)
    run.add_argument("--symbol-set", default="demo-universe")
    run.add_argument("--max-ideas", type=int, default=10)
    run.add_argument("--output-dir", default="outputs")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "run":
        config = AlphaStackConfig(max_ideas=args.max_ideas, output_dir=Path(args.output_dir))
        pipeline = AlphaPipeline(config=config, adapter=ExampleAdapter())
        result = pipeline.run(goal=args.goal, symbol_set=args.symbol_set)
        print(f"Saved report to: {result}")


if __name__ == "__main__":
    main()
