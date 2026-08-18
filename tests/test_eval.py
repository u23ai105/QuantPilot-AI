from app.services.eval_service import EvalService


def test_retrieval_hit():
    chunks = [
        {"filename": "other.pdf", "page_number": 1},
        {"filename": "benchmark_report.pdf", "page_number": 2},
    ]
    assert EvalService.evaluate_retrieval("benchmark_report.pdf", 2, chunks) is True


def test_retrieval_miss():
    chunks = [
        {"filename": "other.pdf", "page_number": 1},
        {"filename": "benchmark_report.pdf", "page_number": 3},  # Wrong page
    ]
    assert EvalService.evaluate_retrieval("benchmark_report.pdf", 2, chunks) is False
    assert EvalService.evaluate_retrieval("missing.pdf", 2, chunks) is False


def test_citation_accuracy():
    # A. Citation Accuracy PASS
    assert EvalService.evaluate_citation("benchmark_report.pdf", 3, "Ans [Source: benchmark_report.pdf, Page: 3]") is True
    # B. Citation Accuracy PASS (Alternative brackets)
    assert EvalService.evaluate_citation("benchmark_report.pdf", 3, "Ans 【Source: benchmark_report.pdf, Page: 3】") is True
    # C. Citation Accuracy FAIL (Wrong page)
    assert EvalService.evaluate_citation("benchmark_report.pdf", 3, "Ans [Source: benchmark_report.pdf, Page: 2]") is False
    # D. Citation Accuracy FAIL (Wrong file)
    assert EvalService.evaluate_citation("benchmark_report.pdf", 3, "Ans [Source: other.pdf, Page: 3]") is False
    # E. Citation Accuracy FAIL (Not in wrapper)
    assert EvalService.evaluate_citation("benchmark_report.pdf", 3, "According to benchmark_report.pdf, page 3...") is False
    # H. Whitespace variations
    assert EvalService.evaluate_citation("benchmark_report.pdf", 3, "Ans [ source : benchmark_report.pdf , page : 3 ]") is True
    # I. Case normalization
    assert EvalService.evaluate_citation("benchmark_report.pdf", 3, "Ans [SOURCE: BENCHMARK_REPORT.pdf, PAGE: 3]") is True


def test_canonical_format_compliance():
    # F. Canonical Format Compliance PASS
    assert EvalService.evaluate_canonical_format("benchmark_report.pdf", 3, "Ans [Source: benchmark_report.pdf, Page: 3]") is True
    # G. Canonical Format Compliance FAIL (Wrong brackets)
    assert EvalService.evaluate_canonical_format("benchmark_report.pdf", 3, "Ans 【Source: benchmark_report.pdf, Page: 3】") is False
    # Case normalization is allowed for text but not brackets
    assert EvalService.evaluate_canonical_format("benchmark_report.pdf", 3, "Ans [SOURCE: BENCHMARK_REPORT.PDF, PAGE: 3]") is True


def test_correct_numerical_answer():
    # Exact text match fallback
    assert EvalService.evaluate_answer_quality("Some string", "This is some string generated.") is True

    # Numeric parsing and tolerance
    # $42.5 billion = 42500000000
    assert EvalService.evaluate_answer_quality("42.5 billion", "In FY 2023, revenue was $42.5 billion.") is True
    assert EvalService.evaluate_answer_quality("42.5 billion", "Revenue increased in 2023 to $42,500,000,000.") is True
    assert EvalService.evaluate_answer_quality("1.25 billion", "FY2024 revenue was approximately $1.26 billion.") is True  # Within 5%
    assert EvalService.evaluate_answer_quality("-5.5 million", "The net loss was -5.4 million in 2023.") is True


def test_incorrect_numerical_answer():
    # Outside 5% tolerance
    assert EvalService.evaluate_answer_quality("42.5 billion", "The report covers 2023. Revenue was $38 billion.") is False
    assert EvalService.evaluate_answer_quality("42.5 billion", "The revenue was 45 billion.") is False


def test_numeric_normalization():
    assert EvalService.normalize_text("$42.5 billion") == "42.5 billion"
    assert EvalService.parse_all_numerics("$42.5 billion") == [42_500_000_000.0]
    assert EvalService.parse_all_numerics("In 2023, 42,500,000,000") == [2023.0, 42_500_000_000.0]
    assert EvalService.parse_all_numerics("1.5M") == [1_500_000.0]
    assert EvalService.parse_all_numerics("-1,500k") == [-1_500_000.0]


def test_numeric_tolerance():
    # 5% of 100 = 5. So 95 to 105 is valid.
    assert EvalService.evaluate_answer_quality("100", "96") is True
    assert EvalService.evaluate_answer_quality("100", "104") is True
    assert EvalService.evaluate_answer_quality("100", "94") is False
    assert EvalService.evaluate_answer_quality("100", "106") is False


def test_partial_score_scenarios():
    retrieval = EvalService.evaluate_retrieval("doc.pdf", 1, [{"filename": "doc.pdf", "page_number": 1}])
    citation = EvalService.evaluate_citation("doc.pdf", 1, "The answer is 100 in doc.pdf pg 2")  # miss due to strict format
    answer = EvalService.evaluate_answer_quality("100", "The answer is 100 in doc.pdf pg 2")  # hit

    assert retrieval is True
    assert citation is False
    assert answer is True
