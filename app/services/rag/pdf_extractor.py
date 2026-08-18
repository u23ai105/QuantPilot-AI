import fitz  # PyMuPDF


class PDFExtractor:
    @staticmethod
    def extract_pages(file_path: str) -> list[tuple[int, str]]:
        """Extract text from a PDF file.

        Returns a list of tuples: (page_number (1-indexed), text).
        """
        pages = []
        try:
            doc = fitz.open(file_path)
            for i in range(len(doc)):
                page = doc.load_page(i)
                text = page.get_text("text")
                # 1-indexed page numbers
                pages.append((i + 1, text.strip()))
            doc.close()
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}") from e

        return pages
