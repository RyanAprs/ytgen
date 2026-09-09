"""CLI entrypoint (M1 skeleton)."""
from __future__ import annotations
import argparse
import sys
from rich.console import Console
from rich.table import Table

from .config import Config
from . import checks

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


def cmd_generate(args) -> int:
    cfg = Config.load(args.config)
    if not args.topic and not args.script:
        console.print("[red]Provide --topic or --script.[/]")
        return 2
    console.print(f"[bold]Pipeline plan[/] (topic={args.topic!r}, script={args.script!r})")
    table = Table()
    table.add_column("#")
    table.add_column("Stage")
    table.add_column("Description")
    table.add_column("Status")
    skip_research = args.no_research or bool(args.script)
    for i, (name, desc) in enumerate(STAGES, 1):
        status = "[dim]not implemented[/]"
        if name == "research" and skip_research:
            status = "[yellow]skipped[/]"
        table.add_row(str(i), name, desc, status)
    console.print(table)
    console.print(
        "\n[yellow]M1 skeleton:[/] pipeline stages are stubs. "
        "Implemented incrementally (M2 research next)."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ytgen", description="Faceless YouTube video generator")
    p.add_argument("--config", help="path to config.yaml", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("doctor", help="check environment/dependencies")
    d.set_defaults(func=cmd_doctor)

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
