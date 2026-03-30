from __future__ import annotations

import argparse
from pathlib import Path

from .convert import convert_pdf_to_markdown, check_pdf
from . import __version__


def main(argv: list[str] | None = None) -> None:
    description = (
        "TLDR: Convert a PDF book into Markdown and extract images.\n\n"
        "Creates a per-book folder with a .md file and an images/ directory."
    )
    epilog = (
        "Examples:\n"
        "  book-convert /path/to/book.pdf\n"
        "  book-convert /path/to/book.pdf /path/archive\n"
    )
    parser = argparse.ArgumentParser(
        prog="book-convert",
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pdf", type=Path, help="Input PDF file")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Optional output directory root",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip extracting and linking images",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry run: validate input/output and exit",
    )
    args = parser.parse_args(argv)

    pdf_path: Path = args.pdf
    if not pdf_path.exists():
        raise SystemExit(f"Input PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise SystemExit(f"Input file must be a .pdf: {pdf_path}")

    if args.check:
        try:
            output_dir, page_total = check_pdf(pdf_path, args.output)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        print(f"OK: {pdf_path} pages={page_total} output={output_dir}")
        return

    try:
        output_path = convert_pdf_to_markdown(
            pdf_path,
            args.output,
            include_images=not args.no_images,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"WROTE: {output_path}")


if __name__ == "__main__":
    main()
