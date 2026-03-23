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

    # --- Factor Governance ---

    # astack audit
    aud = sub.add_parser("audit", help="Audit existing factors")
    add_io(aud)

    # astack migrate
    mig = sub.add_parser("migrate", help="Migrate factors to standard AlphaSpec")
    add_io(mig)

    # astack improve
    imp = sub.add_parser("improve", help="Improve factors based on evaluation")
    add_io(imp)
    imp.add_argument("--reports", default=None, help="Reports JSON for improvement context")

    # astack decide
    dec = sub.add_parser("decide", help="Decide factor fate")
    add_io(dec)

    # astack govern — 完整治理 loop
    gov = sub.add_parser("govern", help="Run full governance loop on existing factors")
    add_io(gov)
    gov.add_argument("--symbol-set", default="default")

    # astack parse-report — 解析 AlphaGPT factor_report.json
    pr = sub.add_parser("parse-report", help="Parse AlphaGPT factor_report.json into astack artifacts")
    pr.add_argument("--input", "-i", required=True, help="Path to factor_report.json or directory")
    pr.add_argument("--output", "-o", default=None, help="Output directory for parsed artifacts")

    # astack ingest — 解析 + 导入 + 治理一步完成
    ing = sub.add_parser("ingest", help="Parse AlphaGPT report and run governance in one step")
    ing.add_argument("--input", "-i", required=True, help="Path to factor_report.json or directory")
    ing.add_argument("--output", "-o", default=None, help="Output directory")

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

    # =======================================================================
    # Factor Governance Commands
    # =======================================================================
    from astack.core.auditor import FactorAuditor
    from astack.core.migrator import FactorMigrator
    from astack.core.improver import FactorImprover
    from astack.core.decider import FactorDecider

    # --- audit ---
    if args.command == "audit":
        if not args.input:
            print("Error: --input required for audit", file=sys.stderr)
            sys.exit(1)
        specs = [AlphaSpec(**d) for d in _read_artifact(args.input)]
        auditor = FactorAuditor()
        audits = [auditor.audit(s) for s in specs]
        for a in audits:
            print(f"  {a.factor_name}: {a.suggested_action} | issues={len(a.potential_issues)} | type={a.factor_type}")
        if args.output:
            _write_artifact(args.output, audits)
        return

    # --- migrate ---
    if args.command == "migrate":
        if not args.input:
            print("Error: --input required for migrate", file=sys.stderr)
            sys.exit(1)
        specs = [AlphaSpec(**d) for d in _read_artifact(args.input)]
        auditor = FactorAuditor()
        migrator = FactorMigrator()
        migrated = []
        for s in specs:
            audit = auditor.audit(s)
            m = migrator.migrate(s, audit)
            migrated.append(m)
            print(f"  {s.name} -> {m.name}")
        if args.output:
            _write_artifact(args.output, migrated)
        return

    # --- improve ---
    if args.command == "improve":
        if not args.input:
            print("Error: --input required for improve", file=sys.stderr)
            sys.exit(1)
        specs = [AlphaSpec(**d) for d in _read_artifact(args.input)]
        # 获取 reports
        reports_path = getattr(args, "reports", None)
        if reports_path:
            reports = [ValidationReport(**d) for d in _read_artifact(reports_path)]
        else:
            reports = agent.validate(specs)
        improver = FactorImprover()
        improvements = []
        for s, r in zip(specs, reports):
            imp = improver.improve(s, r)
            improvements.append(imp)
            print(f"  {imp.original_name} -> {imp.improved_name}: {', '.join(imp.improvements)}")
        if args.output:
            _write_artifact(args.output, improvements)
        return

    # --- decide ---
    if args.command == "decide":
        if not args.input:
            print("Error: --input required for decide", file=sys.stderr)
            sys.exit(1)
        specs = [AlphaSpec(**d) for d in _read_artifact(args.input)]
        auditor = FactorAuditor()
        improver = FactorImprover()
        decider = FactorDecider()
        decisions = []
        reports = agent.validate(specs)
        for s, r in zip(specs, reports):
            audit = auditor.audit(s)
            imp = improver.improve(s, r)
            dec = decider.decide(s, audit, r, imp)
            decisions.append(dec)
            print(f"  {dec.factor_name}: {dec.decision} ({dec.reason[:60]})")
        if args.output:
            _write_artifact(args.output, decisions)
        return

    # --- govern (完整治理 loop) ---
    if args.command == "govern":
        if not args.input:
            print("Error: --input required for govern", file=sys.stderr)
            sys.exit(1)
        specs = [AlphaSpec(**d) for d in _read_artifact(args.input)]
        symbol_set = getattr(args, "symbol_set", "default")
        summary = agent.govern(specs, symbol_set=symbol_set)
        print(f"  Audited: {summary.total_audited}")
        print(f"  Decisions: {summary.by_decision}")
        if summary.top_issues:
            print(f"  Top issues: {', '.join(summary.top_issues[:3])}")
        if summary.recommendations:
            for rec in summary.recommendations:
                print(f"  -> {rec}")
        for dec in summary.decisions:
            print(f"  {dec.factor_name}: {dec.decision} | {dec.reason[:60]}")
        if args.output:
            _write_artifact(args.output, summary)
        return

    # --- parse-report (AlphaGPT factor_report.json → astack artifacts) ---
    if args.command == "parse-report":
        from astack.adapters.alphagpt_parser import AlphaGPTReportParser
        parser_obj = AlphaGPTReportParser()
        input_path = Path(args.input)

        if input_path.is_dir():
            results, summary = parser_obj.parse_directory(str(input_path))
            print(f"  Batch parsed {summary.total_factors} factors from {summary.total_files} files")
            print(f"  Avg quality: {summary.avg_quality:.3f} | Avg completeness: {summary.avg_completeness:.3f}")
            print(f"  Confidence: {summary.by_confidence}")
        else:
            results = parser_obj.parse_file(str(input_path))
            summary = None
            print(f"  Parsed {len(results)} factors from {args.input}")

        for pf in results:
            conf_tag = f"[{pf.confidence}]" if hasattr(pf, 'confidence') else ""
            r = pf.report if hasattr(pf, 'report') else pf[1]
            m = pf.metrics if hasattr(pf, 'metrics') else pf[2]
            n = pf.name if hasattr(pf, 'name') else pf[0]
            print(f"  {n}: quality={r.quality_score:.3f} IC={m.ic_mean} sharpe={m.sharpe} {conf_tag}")
            if r.warnings:
                for w in r.warnings:
                    print(f"    ! {w}")

        if args.output:
            out_dir = Path(args.output)
            out_dir.mkdir(parents=True, exist_ok=True)
            reports = [pf.report if hasattr(pf, 'report') else pf[1] for pf in results]
            metrics_list = [pf.metrics if hasattr(pf, 'metrics') else pf[2] for pf in results]
            _write_artifact(str(out_dir / "reports.json"), reports)
            _write_artifact(str(out_dir / "metrics.json"), metrics_list)
            if summary:
                _write_artifact(str(out_dir / "batch_summary.json"), summary.to_dict())
        return

    # --- ingest (parse + govern in one step) ---
    if args.command == "ingest":
        from astack.adapters.alphagpt_parser import AlphaGPTReportParser
        parser_obj = AlphaGPTReportParser()
        input_path = Path(args.input)

        if input_path.is_dir():
            results, batch_summary = parser_obj.parse_directory(str(input_path))
        else:
            results = parser_obj.parse_file(str(input_path))
            batch_summary = None

        print(f"  Parsed {len(results)} factors")
        summary = agent.ingest(results, batch_summary)
        print(f"  Decisions: {summary.by_decision}")
        for dec in summary.decisions:
            print(f"  {dec.factor_name}: {dec.decision} | {dec.reason[:70]}")
        if summary.recommendations:
            for rec in summary.recommendations:
                print(f"  -> {rec}")
        if args.output:
            _write_artifact(args.output, summary)
        return


if __name__ == "__main__":
    main()
