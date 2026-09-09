"""CLI entrypoint (M1 skeleton)."""
from __future__ import annotations
import argparse
import sys
from rich.console import Console
from rich.table import Table

from .config import Config
from . import checks
from . import research as research_mod
from . import script as script_mod
from . import llm as llm_mod

console = Console()

# Pipeline stages (built incrementally per milestone)
STAGES = [
    ("research", "Web search + extract cited facts"),
    ("script", "Generate grounded script"),
    ("scenes", "Split script into scenes"),
    ("tts", "Synthesize voiceover"),
    ("visuals", "Source stock clips/images"),
    ("captions", "Word-synced subtitles"),
    ("assemble", "ffmpeg render"),
    ("output", "mp4 + thumbnail + metadata"),
]


def cmd_doctor(args) -> int:
    cfg = Config.load(args.config)
    results = checks.run_all(cfg)
    table = Table(title="ytgen doctor — environment check")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    all_ok = True
    for c in results:
        status = "[green]OK[/]" if c.ok else "[red]FAIL[/]"
        if not c.ok and c.name.endswith("_API_KEY"):
            status = "[yellow]WARN[/]"  # keys optional until that stage
        elif not c.ok:
            all_ok = False
        table.add_row(c.name, status, c.detail)
    console.print(table)
    if not all_ok:
        console.print("[red]Critical dependency missing.[/] Fix above, re-run.")
        return 1
    console.print("[green]Core deps OK.[/] Missing API keys only warn until their stage runs.")
    return 0


def cmd_research(args) -> int:
    cfg = Config.load(args.config)
    max_sources = args.max_sources or cfg.get("research.max_sources", 6)
    console.print(f"[bold]Researching[/] {args.topic!r} (max_sources={max_sources})...")
    with console.status("searching + extracting..."):
        data = research_mod.run(args.topic, cfg.cache_dir, max_sources=max_sources)
    console.print(
        f"[green]Done.[/] {len(data['sources'])} sources, {len(data['facts'])} facts "
        f"→ {cfg.cache_dir / 'research.json'}"
    )
    table = Table(title="Sources")
    table.add_column("#"); table.add_column("Title"); table.add_column("URL")
    for i, s in enumerate(data["sources"], 1):
        table.add_row(str(i), (s["title"] or "")[:50], s["url"][:60])
    console.print(table)
    if data["facts"]:
        console.print("\n[bold]Sample facts:[/]")
        for f in data["facts"][:5]:
            console.print(f"  • {f['claim'][:120]}")
    return 0


def cmd_generate(args) -> int:
    cfg = Config.load(args.config)
    if not args.topic and not args.script:
        console.print("[red]Provide --topic or --script.[/]")
        return 2
    console.print(f"[bold]Pipeline plan[/] (topic={args.topic!r}, script={args.script!r})")
    skip_research = args.no_research or bool(args.script)
    research_data = None
    if not skip_research:
        max_sources = cfg.get("research.max_sources", 6)
        console.print(f"[bold cyan]▶ Stage 1 research[/] (max_sources={max_sources})...")
        with console.status("searching + extracting..."):
            research_data = research_mod.run(args.topic, cfg.cache_dir, max_sources=max_sources)
        console.print(
            f"  [green]✓[/] {len(research_data['sources'])} sources, "
            f"{len(research_data['facts'])} facts → cache/research.json"
        )
    table = Table()
    table.add_column("#")
    table.add_column("Stage")
    table.add_column("Description")
    table.add_column("Status")
    for i, (name, desc) in enumerate(STAGES, 1):
        status = "[dim]not implemented[/]"
        if name == "research":
            status = "[yellow]skipped[/]" if skip_research else "[green]done[/]"
        table.add_row(str(i), name, desc, status)
    console.print(table)

    # ---- Stage 2-3: script + scenes (M3) ----
    provider = cfg.get("llm.provider", "groq")
    model = cfg.get("llm.model")
    if args.script:
        script_text = open(args.script).read().strip()
        script_data = {"topic": args.topic or "custom", "title": args.topic or "Untitled",
                       "script": script_text, "word_count": len(script_text.split())}
        (cfg.cache_dir / "script.json").write_text(
            __import__("json").dumps(script_data, indent=2, ensure_ascii=False))
        console.print("  [green]✓[/] script loaded from file → cache/script.json")
    else:
        console.print(f"[bold cyan]▶ Stage 2 script[/] ({provider}/{model})...")
        try:
            with console.status("writing grounded script..."):
                script_data = script_mod.generate_script(
                    args.topic, research_data or {}, cfg, cfg.cache_dir)
        except llm_mod.LLMError as e:
            console.print(f"  [red]✗ LLM error:[/] {e}")
            return 3
        console.print(
            f"  [green]✓[/] '{script_data['title']}' — "
            f"{script_data['word_count']} words → cache/script.json")

    console.print("[bold cyan]▶ Stage 3 scenes[/] (splitting)...")
    try:
        with console.status("segmenting into scenes..."):
            scenes_data = script_mod.split_scenes(script_data["script"], cfg, cfg.cache_dir)
    except llm_mod.LLMError as e:
        console.print(f"  [red]✗ LLM error:[/] {e}")
        return 3
    total = sum(s["est_duration_sec"] for s in scenes_data["scenes"])
    console.print(
        f"  [green]✓[/] {len(scenes_data['scenes'])} scenes, "
        f"~{total:.0f}s total → cache/scenes.json")

    console.print("\n[yellow]M3:[/] script + scenes done. TTS (M4) next.")
    return 0


def cmd_script(args) -> int:
    cfg = Config.load(args.config)
    research_path = cfg.cache_dir / "research.json"
    research_data = {}
    if research_path.exists():
        research_data = __import__("json").loads(research_path.read_text())
    elif not args.no_research:
        console.print("[yellow]No research.json — running research first...[/]")
        research_data = research_mod.run(
            args.topic, cfg.cache_dir, max_sources=cfg.get("research.max_sources", 6))
    provider = cfg.get("llm.provider", "groq")
    model = cfg.get("llm.model")
    console.print(f"[bold]Script gen[/] ({provider}/{model}) for {args.topic!r}")
    try:
        with console.status("writing script..."):
            sd = script_mod.generate_script(args.topic, research_data, cfg, cfg.cache_dir)
        with console.status("splitting scenes..."):
            scd = script_mod.split_scenes(sd["script"], cfg, cfg.cache_dir)
    except llm_mod.LLMError as e:
        console.print(f"[red]LLM error:[/] {e}")
        return 3
    console.print(f"\n[bold]Title:[/] {sd['title']}")
    console.print(f"[bold]Words:[/] {sd['word_count']}\n")
    console.print(sd["script"][:500] + ("..." if len(sd["script"]) > 500 else ""))
    console.print(f"\n[bold]{len(scd['scenes'])} scenes:[/]")
    for s in scd["scenes"][:6]:
        kw = ", ".join(s["visual_keywords"])
        console.print(f"  [{s['index']}] ({s['est_duration_sec']}s) [dim]{kw}[/]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ytgen", description="Faceless YouTube video generator")
    p.add_argument("--config", help="path to config.yaml", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("doctor", help="check environment/dependencies")
    d.set_defaults(func=cmd_doctor)

    r = sub.add_parser("research", help="run research stage only (test)")
    r.add_argument("--topic", required=True, help="topic to research")
    r.add_argument("--max-sources", type=int, default=None, dest="max_sources")
    r.set_defaults(func=cmd_research)

    sc = sub.add_parser("script", help="run script+scenes stage only (test)")
    sc.add_argument("--topic", required=True, help="topic")
    sc.add_argument("--no-research", action="store_true", help="skip research if no cache")
    sc.set_defaults(func=cmd_script)

    g = sub.add_parser("generate", help="generate a video")
    g.add_argument("--topic", help="topic to generate a video about")
    g.add_argument("--script", help="path to an existing script file")
    g.add_argument("--no-research", action="store_true", help="skip research stage")
    g.set_defaults(func=cmd_generate)

    return p


def app(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(app())
