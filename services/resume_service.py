import PyPDF2
from docx import Document


def extract_resume_text(uploaded_file):
    filename = uploaded_file.filename.lower()

    if filename.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="ignore")

    elif filename.endswith(".pdf"):
        reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()

    elif filename.endswith(".docx"):
        doc = Document(uploaded_file)
        return "\n".join([p.text for p in doc.paragraphs]).strip()

    else:
        raise ValueError("Unsupported file format. Please upload PDF, DOCX, or TXT.")