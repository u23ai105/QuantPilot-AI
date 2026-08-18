import re
from typing import Any


class EvalService:
    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text for deterministic matching.
        Strips whitespace, lowers case, removes currency, commas.
        """
        if not text:
            return ""
        # Lowercase
        t = text.lower()
        # Remove currency symbols
        t = t.replace("$", "").replace("€", "").replace("£", "")
        # Remove commas
        t = t.replace(",", "")
        # Strip all extra whitespace
        t = " ".join(t.split())
        return t

    @staticmethod
    def parse_all_numerics(text: str) -> list[float]:
        """
        Attempt to parse all numeric values from the text, handling negative signs and K/M/B suffixes.
        """
        t = EvalService.normalize_text(text)
        matches = re.finditer(r"(-?[\d\.]+)\s*(k|m|b|billion|million|thousand)?", t)
        vals = []
        for match in matches:
            val_str = match.group(1)
            suffix = match.group(2)
            try:
                if val_str in [".", "-.", "-"]:
                    continue
                val = float(val_str)
            except ValueError:
                continue

            if suffix:
                if suffix in ["k", "thousand"]:
                    val *= 1_000
                elif suffix in ["m", "million"]:
                    val *= 1_000_000
                elif suffix in ["b", "billion"]:
                    val *= 1_000_000_000
            vals.append(val)
        return vals

    @staticmethod
    def evaluate_answer_quality(expected: str, generated: str, tolerance: float = 0.05) -> bool:
        """
        Deterministically evaluate if the generated answer contains the expected answer.
        Uses numeric tolerance for numbers, checking all candidates. Or exact normalized string matching for text.
        """
        if not expected or not generated:
            return False

        norm_expected = EvalService.normalize_text(expected)
        norm_generated = EvalService.normalize_text(generated)

        # Check if the expected answer is purely a numeric fact
        num_expected_list = EvalService.parse_all_numerics(expected)
        num_generated_list = EvalService.parse_all_numerics(generated)

        if num_expected_list and num_generated_list:
            num_expected = num_expected_list[0]

            for num_generated in num_generated_list:
                diff = abs(num_expected - num_generated)
                if num_expected == 0:
                    if diff <= tolerance:
                        return True
                else:
                    if (diff / abs(num_expected)) <= tolerance:
                        return True
            return False

        # Fallback to string inclusion matching
        return norm_expected in norm_generated

    @staticmethod
    def evaluate_citation(expected_doc: str, expected_page: int, generated_answer: str) -> bool:
        """
        Check if the exact expected document and page are cited in the generated answer
        using supported wrappers (e.g. [ ] or 【 】) and structured fields.
        """
        if not generated_answer:
            return False
        # Matches brackets, 'Source:', filename, 'Page:', number
        pattern = r"[\[【]\s*source\s*:\s*([^,\]】]+?)\s*,\s*page\s*:\s*(\d+)\s*[\]】]"
        matches = re.finditer(pattern, generated_answer, re.IGNORECASE)
        for match in matches:
            filename = match.group(1).strip()
            page = int(match.group(2).strip())
            if filename.lower() == expected_doc.lower() and page == expected_page:
                return True
        return False

    @staticmethod
    def evaluate_canonical_format(expected_doc: str, expected_page: int, generated_answer: str) -> bool:
        """
        Check if the model used the strictly canonical bracket format:
        [Source: <filename>, Page: <page_number>]
        """
        if not generated_answer:
            return False
        escaped_doc = re.escape(expected_doc)
        pattern = rf"\[\s*source:\s*{escaped_doc}\s*,\s*page:\s*{expected_page}\s*\]"
        if re.search(pattern, generated_answer, re.IGNORECASE):
            return True
        return False

    @staticmethod
    def evaluate_retrieval(expected_doc: str, expected_page: int, retrieved_chunks: list[dict[str, Any]]) -> bool:
        """
        Evaluate Retrieval Hit@K based on chunks retrieved.
        """
        for chunk in retrieved_chunks:
            if chunk.get("filename") == expected_doc and chunk.get("page_number") == expected_page:
                return True
        return False
