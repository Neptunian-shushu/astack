import argparse
import json
from pathlib import Path

from astack.config import AStackConfig
from astack.runtime.agent import ResearchAgent
from astack.adapters.example_adapter import ExampleAdapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AStack — Alpha Research Workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    # astack run — 完整 loop
    run = sub.add_parser("run", help="Run full research loop")
    run.add_argument("--goal", required=True)
    run.add_argument("--symbol-set", default="default")
    run.add_argument("--max-ideas", type=int, default=10)
    run.add_argument("--output-dir", default="outputs")

    # astack generate
    gen = sub.add_parser("generate", help="Generate alpha ideas")
    gen.add_argument("--goal", required=True)
    gen.add_argument("--max-ideas", type=int, default=10)

    # astack formalize
    form = sub.add_parser("formalize", help="Formalize ideas into specs")
    form.add_argument("--goal", required=True)
    form.add_argument("--max-ideas", type=int, default=5)

    # astack evaluate
    evl = sub.add_parser("evaluate", help="Evaluate specs against criteria")
    evl.add_argument("--goal", required=True)
    evl.add_argument("--symbol-set", default="default")
    evl.add_argument("--max-ideas", type=int, default=5)

    # astack evolve
    evo = sub.add_parser("evolve", help="Evolve surviving specs")
    evo.add_argument("--goal", required=True)
    evo.add_argument("--symbol-set", default="default")
    evo.add_argument("--max-ideas", type=int, default=5)

    return parser


def _make_agent(args) -> ResearchAgent:
    config = AStackConfig(
        max_ideas=getattr(args, "max_ideas", 10),
        output_dir=Path(getattr(args, "output_dir", "outputs")),
    )
    return ResearchAgent(config=config, adapter=ExampleAdapter())


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    agent = _make_agent(args)

    if args.command == "run":
        result = agent.run(goal=args.goal, symbol_set=args.symbol_set)
        print(f"Completed: {len(result.rankings)} alphas ranked")
        print(f"Report: {result.export_path}")

    elif args.command == "generate":
        ideas = agent.generate(goal=args.goal)
        for idea in ideas:
            print(f"  {idea.name}: {idea.hypothesis[:80]}")

    elif args.command == "formalize":
        ideas = agent.generate(goal=args.goal)
        specs = agent.formalize(ideas)
        for spec in specs:
            print(f"  {spec.name}: {spec.formula_expression[:60]}")

    elif args.command == "evaluate":
        ideas = agent.generate(goal=args.goal)
        specs = agent.formalize(ideas)
        reports = agent.validate(specs, symbol_set=args.symbol_set)
        for r in reports:
            print(f"  {r.alpha_name}: quality={r.quality_score:.3f} implementable={r.implementable}")

    elif args.command == "evolve":
        ideas = agent.generate(goal=args.goal)
        specs = agent.formalize(ideas)
        reports = agent.validate(specs, symbol_set=args.symbol_set)
        survivors = [s for s, r in zip(specs, reports) if r.quality_score >= 0.55]
        evolved = agent.evolve(survivors)
        for spec in evolved:
            print(f"  {spec.name}: {spec.formula_expression[:60]}")


if __name__ == "__main__":
    main()
