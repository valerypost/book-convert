from pathlib import Path

import fitz

from book_convert import convert as conv


def _make_pdf(path: Path, text: str = "Hello PDF") -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def test_check_pdf_returns_output_dir_and_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "Sample.pdf"
    _make_pdf(pdf_path)
    output_root = tmp_path / "out"

    output_dir, page_total = conv.check_pdf(pdf_path, output_root)

    assert page_total == 1
    assert output_dir == output_root / "Sample"


def test_convert_without_images_creates_markdown_only(tmp_path: Path) -> None:
    pdf_path = tmp_path / "Book.pdf"
    _make_pdf(pdf_path)

    output_path = conv.convert_pdf_to_markdown(
        pdf_path,
        output_root=tmp_path,
        include_images=False,
    )

    assert output_path.exists()
    assert output_path.parent.name == "Book"
    assert not (output_path.parent / "images").exists()
    assert output_path.read_text(encoding="utf-8").startswith("# Book")


def test_convert_with_images_creates_images_dir(tmp_path: Path) -> None:
    pdf_path = tmp_path / "Images.pdf"
    _make_pdf(pdf_path)

    output_path = conv.convert_pdf_to_markdown(
        pdf_path,
        output_root=tmp_path,
        include_images=True,
    )

    assert output_path.exists()
    assert (output_path.parent / "images").is_dir()


def test_normalize_lines_removes_page_markers() -> None:
    raw = "Page 1\nSome text\n\n1\n"
    lines = conv._normalize_lines(raw, page_number=1, page_total=10)
    assert "Page 1" not in lines
    assert "1" not in [ln.strip() for ln in lines]
    assert "Some text" in lines


def test_join_wrapped_lines_merges_hyphenation() -> None:
    joined = conv._join_wrapped_lines(["Conver-", "sion", "works"])
    assert joined == "Conversion works"
