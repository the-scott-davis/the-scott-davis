"""``python -m profilecard.portrait`` -- photo in, portrait out.

Two modes, chosen by ``portrait.mode`` in config.yml:

* ``pixel`` (default) writes a small colour PNG at native art resolution.
* ``ascii`` writes a block of monospace characters.

Defaults come from the ``portrait:`` block.  Any flag overrides the file for
that one run, which is the fast way to dial a photo in: tweak, look, tweak
again, then write the numbers you settled on back into config.yml.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .ascii_art import RAMPS, PortraitOptions, image_to_ascii
from .analyze import analyze, format_report
from .config import Config, ConfigError
from .pixel_art import PixelOptions, image_to_pixels


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m profilecard.portrait",
        description="Convert a photo into the portrait used by the profile card.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python -m profilecard.portrait                      # rebuild from config.yml\n"
            "  python -m profilecard.portrait --preview            # look, write nothing\n"
            "  python -m profilecard.portrait --preview --width 80 --palette 48\n"
            "  python -m profilecard.portrait --mode ascii --preview\n"
            "  python -m profilecard.portrait --analyze shot.jpg   # will this work at all?\n"
            f"\nascii ramps: {', '.join(RAMPS)}\n"
        ),
    )
    p.add_argument("source", nargs="?", help="image file (default: portrait.source)")
    p.add_argument("-c", "--config", default="config.yml")
    p.add_argument("-o", "--output", help="write here instead of portrait.outputs")
    p.add_argument("--mode", choices=("pixel", "ascii"), help="override portrait.mode")
    p.add_argument("--preview", action="store_true", help="show the result, write no files")
    p.add_argument(
        "--analyze", action="store_true",
        help="report whether the source suits ascii or pixel mode, and exit",
    )

    g = p.add_argument_group("framing (both modes)")
    g.add_argument("--width", type=int, help="target width in art pixels / columns")
    g.add_argument("--height", type=int, help="target height (default: from aspect ratio)")
    g.add_argument(
        "--crop", type=float, nargs=4, metavar=("L", "T", "R", "B"),
        help="crop box as 0..1 fractions",
    )
    g.add_argument("--sharpen", type=float, help="unsharp mask before downsampling")

    x = p.add_argument_group("pixel mode")
    x.add_argument("--palette", type=int, help="number of colours to quantise to")
    x.add_argument("--dither", action="store_true", help="dither instead of flat regions")
    x.add_argument("--saturation", type=float)
    x.add_argument("--contrast", type=float)
    x.add_argument("--brightness", type=float)

    a = p.add_argument_group("ascii mode")
    a.add_argument("--ramp", help=f"named ramp ({', '.join(RAMPS)}) or a literal string")
    a.add_argument("--invert", action="store_true", help="for light backgrounds")
    a.add_argument("--cell-aspect", type=float, help="character cell width / height")
    a.add_argument("--gamma", type=float)
    a.add_argument("--black-point", type=float)
    a.add_argument("--white-point", type=float)
    a.add_argument("--autocontrast", type=float, metavar="PCT")
    a.add_argument("--vignette", type=float, help="0 off .. 1 fully dark corners")
    a.add_argument("--vignette-power", type=float)
    a.add_argument("--floor", type=float, help="levels below this become empty")
    a.add_argument("--no-trim", dest="trim", action="store_false", default=None)
    return p


def _apply_flags(args, opts):
    """Layer explicitly-passed CLI flags over ``opts``, ignoring the other mode's."""
    merged = type(opts)(**vars(opts))
    for name, value in vars(args).items():
        if value is None or not hasattr(merged, name):
            continue
        setattr(merged, name, tuple(value) if name == "crop" else value)
    if args.invert and hasattr(merged, "invert"):
        merged.invert = True
    if args.dither and hasattr(merged, "dither"):
        merged.dither = True
    return merged


def _resolve(args, cfg: Config):
    """Returns (source, mode, [(name, path, options), ...])."""
    pc = cfg.portrait
    source = args.source or (pc.source if pc else None)
    if not source:
        raise ConfigError("no image given: pass one as an argument or set portrait.source")

    mode = args.mode or (pc.mode if pc else "pixel")
    default = PixelOptions() if mode == "pixel" else PortraitOptions()

    # A --mode that differs from the config file cannot reuse its options, since
    # the two modes share almost no keys.
    if pc and mode == pc.mode:
        outputs = [(o.name, o.path, _apply_flags(args, o.options)) for o in pc.outputs]
    else:
        suffix = ".png" if mode == "pixel" else ".txt"
        outputs = [("main", f"assets/portrait{suffix}", _apply_flags(args, default))]

    if args.output:
        outputs = [("main", args.output, outputs[0][2])]
    return source, mode, outputs


def _describe(art) -> str:
    if isinstance(art, str):
        rows = art.count("\n") + 1
        cols = max((len(l) for l in art.split("\n")), default=0)
        return f"{cols} x {rows} chars"
    return f"{art.width} x {art.height} px, {len(art.getcolors(1 << 16) or [])} colours"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = Config.load(args.config)
        source, mode, outputs = _resolve(args, cfg)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if not Path(source).exists():
        print(f"error: {source} not found", file=sys.stderr)
        return 1

    if args.analyze:
        crop = getattr(outputs[0][2], "crop", None) if outputs else None
        print(f"{source}:")
        print(format_report(analyze(source, crop, columns=getattr(outputs[0][2], "width", 72))))
        return 0

    convert = image_to_pixels if mode == "pixel" else image_to_ascii

    if args.preview:
        art = convert(source, outputs[0][2])
        if mode == "ascii":
            print(art)
        else:
            # A PNG cannot be printed, so write it somewhere and say where.
            preview_path = Path("portrait-preview.png")
            art.resize((art.width * 6, art.height * 6), 0).save(preview_path)
            print(f"wrote {preview_path} (6x nearest-neighbour, not committed)")
        print(f"-- {_describe(art)} --", file=sys.stderr)
        return 0

    if not outputs:
        print("error: nothing to write -- set portrait.outputs or pass --output", file=sys.stderr)
        return 1

    for name, path, opts in outputs:
        art = convert(source, opts)
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if mode == "ascii":
            out.write_text(art + "\n", encoding="utf-8")
        else:
            art.save(out, optimize=True)
        print(f"wrote {out}  ({_describe(art)}, {name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
