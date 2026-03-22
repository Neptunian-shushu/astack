# AlphaStack v0.2

AlphaStack is a framework-agnostic alpha research engine for generating, formalizing, critiquing, evolving, deduplicating, and exporting adapter-ready alpha ideas.

This v0.2 scaffold is designed for your current crypto framework via adapters, future portability to other backtesting or execution stacks, and Claude or Codex skills as a front-end orchestration layer.

## Core design

- Framework-agnostic core
- High-standard alpha production
- Memory-guided search
- Skill-first UX

## v0.2 pipeline

```text
research goal
  -> generator
  -> formalizer
  -> validator
  -> deduper
  -> ranker
  -> memory update
  -> evolver
  -> exporter
```

## Why this design

This structure borrows ideas from recent alpha-mining work:
- CogAlpha emphasizes deeper search, multi-stage quality control, and mutation or crossover over code-level alpha representations. fileciteturn1file0
- FactorMiner emphasizes modular skill architecture, experience memory, a global factor-library perspective, and multi-stage evaluation. fileciteturn1file8turn1file6

AlphaStack differs by emphasizing:
- cleaner separation between core logic and host framework
- cleaner separation between research engine and Claude/Codex skill
- reusable schemas and adapters for long-term maintainability

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
alphastack run --goal "Generate 10 short-horizon crypto alpha ideas around volume dislocation and volatility compression"
```

## What is real vs. placeholder

Already included:
- package structure
- core interfaces
- schemas
- pipeline orchestration
- JSON memory store
- basic ranking, dedup, and evolution stubs
- exporter and example adapter
- Claude and Codex skill stubs

Still placeholders that you should replace:
- LLM provider integration
- your real backtest adapter
- your real factor evaluation engine
- your real market data connector
- your real prompt tuning and admission thresholds
