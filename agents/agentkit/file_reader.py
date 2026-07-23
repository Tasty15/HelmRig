"""File reader — läs PDF, DOCX, och textfiler.

Används som skill i agent.yaml:
    skills:
      - name: file_reader
        module: agentkit.file_reader
        description: "Läs PDF-, DOCX- och text-filer"
        side_effect: false

Anropas med: file_reader(path="/sökväg/till/fil.pdf")
"""

from pathlib import Path


def run(**kwargs) -> dict:
    """Läs en fil och returnera textinnehållet.

    Args:
        path: Absolut eller relativ sökväg till filen

    Returns:
        Dict med content (eller error)
    """
    path_str = kwargs.get("path", "")
    if not path_str:
        return {"error": "path krävs", "status": "error"}

    path = Path(path_str)
    if not path.exists():
        return {"error": f"filen '{path}' finns inte", "status": "error"}

    suffix = path.suffix.lower()

    try:
        if suffix == ".pdf":
            return _read_pdf(path)
        elif suffix in (".docx", ".doc"):
            return _read_docx(path)
        elif suffix in (".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".py", ".js", ".ts"):
            return _read_text(path)
        else:
            # Fallback: försök som text
            return _read_text(path)
    except Exception as e:
        return {"error": str(e)[:300], "status": "error"}


def _read_pdf(path: Path) -> dict:
    """Extrahera text från PDF."""
    import pymupdf  # PyMuPDF

    doc = pymupdf.open(str(path))
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    text = "\n\n".join(pages).strip()
    return {
        "content": text,
        "pages": len(pages),
        "chars": len(text),
        "status": "ok",
    }


def _read_docx(path: Path) -> dict:
    """Extrahera text från DOCX."""
    import docx

    doc = docx.Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs]
    text = "\n".join(paragraphs).strip()
    return {
        "content": text,
        "paragraphs": len(paragraphs),
        "chars": len(text),
        "status": "ok",
    }


def _read_text(path: Path) -> dict:
    """Läs vanlig textfil."""
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    return {
        "content": text,
        "chars": len(text),
        "status": "ok",
    }
