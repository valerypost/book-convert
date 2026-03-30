from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

import fitz
from pdfminer.high_level import extract_text

CALLOUT_LABELS = {
    "TIP": "Tip",
    "NOTE": "Note",
    "WARNING": "Warning",
    "CAUTION": "Caution",
    "IMPORTANT": "Important",
}

PY_CODE_RE = re.compile(
    r"^(?:"
    r"from\s+\S+\s+import\s+.+|"
    r"import\s+\S+.*|"
    r"(?:def|class)\s+\w+.*:\s*|"
    r"(?:if|elif|else|for|while|with|try|except|finally)\b.*:\s*|"
    r"return\b.*|yield\b.*|raise\b.*|"
    r"[A-Za-z_][A-Za-z0-9_]*\s*=.+|"
    r"print\(.+\)"
    r")$"
)


def _next_output_dir(output_root: Path, book_name: str) -> Path:
    candidate = output_root / book_name
    if not candidate.exists():
        return candidate
    i = 1
    while True:
        candidate = output_root / f"{book_name}_{i}"
        if not candidate.exists():
            return candidate
        i += 1


def _normalize_lines(raw: str, page_number: int, page_total: int) -> list[str]:
    lines = [ln.rstrip() for ln in raw.replace("\x0c", "\n").splitlines()]
    out: list[str] = []
    for idx, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            out.append("")
            continue

        if re.fullmatch(r"\d+", s):
            n = int(s)
            near_edge = idx <= 2 or idx >= len(lines) - 3
            if near_edge and 1 <= n <= page_total:
                continue

        if re.fullmatch(r"(?i)page\s+\d+(?:\s+of\s+\d+)?", s):
            continue

        out.append(ln)

    collapsed: list[str] = []
    prev_blank = False
    for ln in out:
        blank = ln.strip() == ""
        if blank and prev_blank:
            continue
        collapsed.append(ln)
        prev_blank = blank
    return collapsed


def _is_list_line(s: str) -> bool:
    return bool(re.match(r"^(?:[-*•]|\d+[.)])\s+", s))


def _is_callout_label(s: str) -> bool:
    return re.sub(r"\s+", " ", s.strip().upper()) in CALLOUT_LABELS


def _looks_like_heading(s: str) -> bool:
    if not s or len(s) > 90:
        return False
    if s.endswith((".", ";", ":", "!")):
        return False
    if "," in s:
        return False
    if _is_list_line(s) or _is_callout_label(s):
        return False
    if s.startswith("Figure "):
        return False
    if s.startswith("Chapter "):
        return True

    words = re.findall(r"[A-Za-z][A-Za-z'-]*", s)
    if not words:
        return False
    if not words[0][0].isupper() and not (s == s.upper()):
        return False

    title_like = sum(1 for w in words if w[0].isupper()) / len(words) >= 0.5
    all_caps = s == s.upper() and any(ch.isalpha() for ch in s)
    if title_like and len(words) <= 6:
        return True
    return all_caps and len(words) <= 8


def _is_code_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if line.startswith("    ") or line.startswith("\t"):
        return True
    if PY_CODE_RE.match(stripped):
        return True
    if re.match(r"^[\[\](){},.:+\-/*%<>=!\"'\\]+$", stripped):
        return True
    return False


def _join_wrapped_lines(parts: Iterable[str]) -> str:
    parts = list(parts)
    if not parts:
        return ""
    out = parts[0].strip()
    for part in parts[1:]:
        nxt = part.strip()
        if out.endswith("-"):
            out = out[:-1] + nxt.lstrip()
        else:
            out = out + " " + nxt.lstrip()
    return out.strip()


def _extract_page_images(
    doc: fitz.Document, page: fitz.Page, images_dir: Path, page_number: int
) -> list[Path]:
    image_paths: list[Path] = []
    for idx, image_info in enumerate(page.get_images(full=True), start=1):
        xref = image_info[0]
        extracted = doc.extract_image(xref)
        image_bytes = extracted.get("image")
        if not image_bytes:
            continue
        ext = extracted.get("ext") or "png"
        image_name = f"page-{page_number:03d}-img-{idx:02d}.{ext}"
        image_path = images_dir / image_name
        image_path.write_bytes(image_bytes)
        image_paths.append(image_path)
    return image_paths


def check_pdf(pdf_path: Path, output_root: Path | None = None) -> tuple[Path, int]:
    output_root = output_root or pdf_path.parent
    if output_root.exists() and not output_root.is_dir():
        raise ValueError(f"Output root must be a directory: {output_root}")
    if not output_root.exists():
        parent = output_root.parent
        if not parent.exists() or not parent.is_dir():
            raise ValueError(f"Output root parent does not exist: {parent}")
    output_dir = _next_output_dir(output_root, pdf_path.stem)
    with fitz.open(pdf_path) as doc:
        page_total = doc.page_count
    return output_dir, page_total


def convert_pdf_to_markdown(
    pdf_path: Path,
    output_root: Path | None = None,
    include_images: bool = True,
) -> Path:
    output_root = output_root or pdf_path.parent
    if output_root.exists() and not output_root.is_dir():
        raise ValueError(f"Output root must be a directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    output_dir = _next_output_dir(output_root, pdf_path.stem)
    output_dir.mkdir(parents=True, exist_ok=False)
    images_dir = output_dir / "images"
    if include_images:
        images_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / f"{output_dir.name}.md"

    seen_code: dict[str, int] = {}
    title = pdf_path.stem
    out_lines: list[str] = [f"# {title}", ""]

    with fitz.open(pdf_path) as doc:
        page_total = doc.page_count
        for page_number in range(1, page_total + 1):
            raw = extract_text(str(pdf_path), page_numbers=[page_number - 1]) or ""
            lines = _normalize_lines(raw, page_number, page_total)

            i = 0
            while i < len(lines):
                ln = lines[i]
                s = ln.strip()

                if not s:
                    if out_lines and out_lines[-1] != "":
                        out_lines.append("")
                    i += 1
                    continue

                if _is_callout_label(s):
                    label = CALLOUT_LABELS[re.sub(r"\s+", " ", s.upper())]
                    i += 1
                    body: list[str] = []
                    while i < len(lines):
                        cur = lines[i].strip()
                        if not cur:
                            if body:
                                break
                            i += 1
                            continue
                        if _is_code_line(lines[i]) or _is_list_line(
                            cur
                        ) or _looks_like_heading(cur):
                            break
                        body.append(cur)
                        i += 1

                    out_lines.append(f"> **{label}**")
                    out_lines.append(">")
                    if body:
                        out_lines.append(f"> {_join_wrapped_lines(body)}")
                    out_lines.append("")
                    continue

                if _looks_like_heading(s):
                    out_lines.append(f"### {s}")
                    out_lines.append("")
                    i += 1
                    continue

                if _is_list_line(s):
                    out_lines.append(s)
                    i += 1
                    continue

                if _is_code_line(ln):
                    block = [ln]
                    i += 1

                    while i < len(lines):
                        cur = lines[i]
                        if cur.strip() == "":
                            j = i + 1
                            while j < len(lines) and lines[j].strip() == "":
                                j += 1
                            if j < len(lines) and _is_code_line(lines[j]):
                                block.append("")
                                i += 1
                                continue
                            break
                        if not _is_code_line(cur):
                            break
                        block.append(cur)
                        i += 1

                    while block and block[0] == "":
                        block.pop(0)
                    while block and block[-1] == "":
                        block.pop()

                    norm = "\n".join(x.rstrip() for x in block).strip()
                    key = (
                        hashlib.sha1(re.sub(r"\s+", " ", norm).encode()).hexdigest()
                        if norm
                        else None
                    )

                    if norm:
                        if key in seen_code:
                            out_lines.append(
                                f"> Code repeated from page {seen_code[key]}; omitted here."
                            )
                            out_lines.append("")
                        else:
                            seen_code[key] = page_number
                            out_lines.append("```python")
                            out_lines.extend(block)
                            out_lines.append("```")
                            out_lines.append("")
                    continue

                para = [s]
                i += 1
                while i < len(lines):
                    cur = lines[i].strip()
                    if (
                        not cur
                        or _is_code_line(lines[i])
                        or _is_list_line(cur)
                        or _is_callout_label(cur)
                        or _looks_like_heading(cur)
                    ):
                        break
                    para.append(cur)
                    i += 1

                out_lines.append(_join_wrapped_lines(para))
                out_lines.append("")

            if include_images:
                page = doc.load_page(page_number - 1)
                image_paths = _extract_page_images(doc, page, images_dir, page_number)
                if image_paths:
                    if out_lines and out_lines[-1] != "":
                        out_lines.append("")
                    for idx, image_path in enumerate(image_paths, start=1):
                        rel = f"images/{image_path.name}"
                        out_lines.append(f"![Page {page_number} image {idx}]({rel})")
                    out_lines.append("")

            while len(out_lines) >= 2 and out_lines[-1] == "" and out_lines[-2] == "":
                out_lines.pop()
            out_lines.append("")

    dest.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
    return dest
