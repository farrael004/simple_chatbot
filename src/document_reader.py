import io
from pypdf import PdfReader
from docx import Document


def extract_text_from_pdf(file_bytes: bytes) -> str:
    with io.BytesIO(file_bytes) as f:
        reader = PdfReader(f)
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(pages)


def extract_text_from_docx(file_bytes: bytes) -> str:
    with io.BytesIO(file_bytes) as f:
        doc = Document(f)
        return "\n".join([p.text for p in doc.paragraphs])


def extract_text_from_txt(file_bytes: bytes) -> str:
    # Attempt to decode gracefully
    for enc in ["utf-8", "utf-16", "latin-1"]:
        try:
            return file_bytes.decode(enc)
        except Exception:
            continue
    return file_bytes.decode("utf-8", errors="ignore")


def read_uploaded_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    data = uploaded_file.read()
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        text = extract_text_from_pdf(data)
    elif name.endswith(".docx"):
        text = extract_text_from_docx(data)
    elif name.endswith(".txt"):
        text = extract_text_from_txt(data)
    else:
        text = ""
    # No hard cap; downstream code should handle chunking/limits.
    return text
