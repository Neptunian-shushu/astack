"""
AStack CLI — artifact-based workflow

每个命令支持 --input / --output，实现可串联的流水线：
  astack generate --goal "..." --output ideas.json
  astack formalize --input ideas.json --output specs.json
  astack evaluate --input specs.json --output reports.json
  astack dedupe --input reports.json --output deduped.json
  astack rank --input reports.json --output ranked.json
  astack evolve --input specs.json --output evolved.json
  astack run --goal "..."  # 完整 loop
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List

from astack.config import AStackConfig
from astack.runtime.agent import ResearchAgent
from astack.adapters.example_adapter import ExampleAdapter


# ---------------------------------------------------------------------------
# Artifact I/O helpers
# ---------------------------------------------------------------------------

def _read_artifact(path: str) -> List[dict]:
    data = json.loads(Path(path).read_text())
    return data if isinstance(data, list) else [data]


def _write_artifact(path: str, data: Any) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(data, "model_dump"):
        payload = data.model_dump()
    elif isinstance(data, list) and data and hasattr(data[0], "model_dump"):
        payload = [d.model_dump() for d in data]
    else:
        payload = data
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"-> {out}")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AStack — Alpha Research Workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    # 共享参数
    def add_io(p, need_goal=False):
        if need_goal:
            p.add_argument("--goal", default=None, help="Research goal (required if no --input)")
        p.add_argument("--input", "-i", default=None, help="Input artifact JSON path")
        p.add_argument("--output", "-o", default=None, help="Output artifact JSON path")
        p.add_argument("--max-ideas", type=int, default=10)

    # astack run
    run = sub.add_parser("run", help="Run full research loop")
    run.add_argument("--goal", required=True)
    run.add_argument("--symbol-set", default="default")
    run.add_argument("--max-ideas", type=int, default=10)
    run.add_argument("--output-dir", default="outputs")

    # astack generate
    gen = sub.add_parser("generate", help="Generate alpha ideas")
    add_io(gen, need_goal=True)

    # astack formalize
    form = sub.add_parser("formalize", help="Formalize ideas into specs")
    add_io(form, need_goal=True)

    # astack evaluate
    evl = sub.add_parser("evaluate", help="Evaluate specs")
    add_io(evl, need_goal=True)
    evl.add_argument("--symbol-set", default="default")

    # astack dedupe
    ded = sub.add_parser("dedupe", help="Deduplicate reports")
    add_io(ded)

    # astack rank
    rnk = sub.add_parser("rank", help="Rank reports")
    add_io(rnk)

    # astack evolve
    evo = sub.add_parser("evolve", help="Evolve surviving specs")
    add_io(evo, need_goal=True)

    return parser


def _make_agent(args) -> ResearchAgent:
    config = AStackConfig(
        max_ideas=getattr(args, "max_ideas", 10),
        output_dir=Path(getattr(args, "output_dir", "outputs")),
    )
    return ResearchAgent(config=config, adapter=ExampleAdapter())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def main() -> None:
    from astack.schemas import AlphaIdea, AlphaSpec, ValidationReport

    parser = build_parser()
    args = parser.parse_args()
    agent = _make_agent(args)

    if args.command == "run":
        result = agent.run(goal=args.goal, symbol_set=args.symbol_set)
        print(f"Completed: {len(result.rankings)} alphas ranked")
        print(f"Report: {result.export_path}")
        return

    # --- generate ---
    if args.command == "generate":
        goal = args.goal
        if not goal:
            print("Error: --goal is required for generate", file=sys.stderr)
            sys.exit(1)
        ideas = agent.generate(goal)
        for idea in ideas:
            print(f"  {idea.name}: {idea.hypothesis[:80]}")
        if args.output:
            _write_artifact(args.output, ideas)
        return

    # --- formalize ---
    if args.command == "formalize":
        if args.input:
            ideas = [AlphaIdea(**d) for d in _read_artifact(args.input)]
        elif args.goal:
            ideas = agent.generate(args.goal)
        else:
            print("Error: --input or --goal required", file=sys.stderr)
            sys.exit(1)
        specs = agent.formalize(ideas)
        for spec in specs:
            print(f"  {spec.name}: {spec.formula_expression[:60]}")
        if args.output:
            _write_artifact(args.output, specs)
        return

    # --- evaluate ---
    if args.command == "evaluate":
        if args.input:
            specs = [AlphaSpec(**d) for d in _read_artifact(args.input)]
        elif args.goal:
            ideas = agent.generate(args.goal)
            specs = agent.formalize(ideas)
        else:
            print("Error: --input or --goal required", file=sys.stderr)
            sys.exit(1)
        symbol_set = getattr(args, "symbol_set", "default")
        reports = agent.validate(specs, symbol_set=symbol_set)
        for r in reports:
            print(f"  {r.alpha_name}: quality={r.quality_score:.3f}")
        if args.output:
            _write_artifact(args.output, reports)
        return

    # --- dedupe ---
    if args.command == "dedupe":
        if not args.input:
            print("Error: --input required for dedupe", file=sys.stderr)
            sys.exit(1)
        reports = [ValidationReport(**d) for d in _read_artifact(args.input)]
        deduped = agent.dedupe(reports)
        print(f"  {len(reports)} -> {len(deduped)} after dedupe")
        if args.output:
            _write_artifact(args.output, deduped)
        return

    # --- rank ---
    if args.command == "rank":
        if not args.input:
            print("Error: --input required for rank", file=sys.stderr)
            sys.exit(1)
        reports = [ValidationReport(**d) for d in _read_artifact(args.input)]
        rankings = agent.rank(reports)
        for r in rankings:
            print(f"  {r.alpha_name}: score={r.rank_score:.3f}")
        if args.output:
            _write_artifact(args.output, rankings)
        return

    # --- evolve ---
    if args.command == "evolve":
        if args.input:
            specs = [AlphaSpec(**d) for d in _read_artifact(args.input)]
        elif args.goal:
            ideas = agent.generate(args.goal)
            specs = agent.formalize(ideas)
            reports = agent.validate(specs)
            specs = [s for s, r in zip(specs, reports) if r.quality_score >= 0.55]
        else:
            print("Error: --input or --goal required", file=sys.stderr)
            sys.exit(1)
        evolved = agent.evolve(specs)
        for spec in evolved:
            print(f"  {spec.name}: {spec.formula_expression[:60]}")
        if args.output:
            _write_artifact(args.output, evolved)
        return


if __name__ == "__main__":
    main()
