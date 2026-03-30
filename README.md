# book-convert

Convert PDF books into Markdown with extracted images.

## Quick Start

Option A (no CLI install, uses `PYTHONPATH`):

```sh
cd book-converter
python3 -m pip install -r requirements.txt
PYTHONPATH=src python3 -m book_converter /path/to/book.pdf
```

Option B (editable install, adds `book-convert`):

```sh
cd book-converter
python3 -m pip install -e .
book-convert /path/to/book.pdf
```

Option C (virtualenv + editable install):

```sh
cd book-converter
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
book-convert /path/to/book.pdf
```

## More Examples

With an explicit output root:

```sh
book-convert /path/to/book.pdf /path/archive
```

Skip images:

```sh
book-convert --no-images /path/to/book.pdf
```

Dry run:

```sh
book-convert --check /path/to/book.pdf /path/archive
```

Show version:

```sh
book-convert --version
```

## Output Layout

For `SomeBook.pdf`, the converter creates:

```
SomeBook/
  SomeBook.md
  images/
    page-001-img-01.png
    page-001-img-02.png
```

If a folder with the same name exists, it uses `SomeBook_1/`, `SomeBook_2/`, etc.

If you pass an output root, the `SomeBook/` folder is created inside that directory.

## Architecture

- `book_converter/cli.py`: CLI entry point and argument parsing.
- `book_converter/convert.py`: conversion pipeline.
  - Text extraction via `pdfminer.six`
  - Image extraction via `PyMuPDF`
  - Markdown formatting for headings, lists, callouts, and code blocks

## Notes

- Images are inserted near the end of each page’s extracted text as Markdown links.
- Large PDFs can take time; outputs are written after the full conversion finishes.
- `--check` performs a quick validation and does not write output files.
