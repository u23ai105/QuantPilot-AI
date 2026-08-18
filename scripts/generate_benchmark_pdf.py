"""Generate a deterministic synthetic 10-K report for evaluation."""

import os

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def generate_benchmark_pdf(output_path: str):
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter

    def add_page(title: str, lines: list[str]):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, height - 72, title)

        c.setFont("Helvetica", 12)
        y = height - 120
        for line in lines:
            c.drawString(72, y, line)
            y -= 20
        c.showPage()

    # Page 1: Overview
    add_page(
        "QuantPilot Synthetic Benchmark Report - FY 2023",
        [
            "Company: Acme Corp (Ticker: ACME)",
            "Fiscal Year: 2023",
            "This report provides an overview of the financial performance for Acme Corp.",
            "All figures are reported in USD unless otherwise specified.",
            "",
            "The company operates in three primary segments:",
            "1. Hardware Operations",
            "2. Cloud Services",
            "3. Autonomous Systems",
        ],
    )

    # Page 2: Revenue
    add_page(
        "Financial Highlights - Revenue",
        [
            "Total net sales revenue for Acme Corp in FY 2023 was $42.5 billion.",
            "This represents a 15% increase compared to the $36.9 billion reported in FY 2022.",
            "Cloud Services segment revenue was a significant driver, contributing $18.2 billion.",
            "Hardware Operations revenue remained flat at $20.1 billion.",
            "Autonomous Systems revenue saw explosive growth, reaching $4.2 billion.",
        ],
    )

    # Page 3: Profitability
    add_page(
        "Financial Highlights - Profitability",
        [
            "Gross profit margin improved to 42.1% in FY 2023.",
            "Operating income was $11.3 billion, yielding an operating margin of 26.5%.",
            "Net income for the year was $8.9 billion.",
            "Diluted earnings per share (EPS) stood at $4.15 per share.",
            "The company repurchased 15 million shares of common stock during the fiscal year.",
        ],
    )

    # Page 4: Balance Sheet
    add_page(
        "Balance Sheet & Liquidity",
        [
            "Total assets stood at $85.6 billion at the end of FY 2023.",
            "Cash and cash equivalents amounted to $12.4 billion.",
            "Total liabilities were reported at $45.2 billion.",
            "Long-term debt was reduced to $18.5 billion from $21.0 billion in the previous year.",
            "The company maintains a strong current ratio of 2.1x.",
        ],
    )

    # Page 5: Outlook
    add_page(
        "Future Outlook - FY 2024",
        [
            "Management expects total revenue to grow between 10% and 12% in FY 2024.",
            "Capital expenditures (CapEx) are projected to be $5.5 billion.",
            "The effective tax rate is anticipated to remain stable at approximately 21.0%.",
            "Research and development (R&D) investments will increase to $6.8 billion.",
            "The CEO stated: 'We are committed to aggressive expansion in autonomous capabilities.'",
        ],
    )

    c.save()


if __name__ == "__main__":
    fixtures_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests", "fixtures")
    os.makedirs(fixtures_dir, exist_ok=True)
    pdf_path = os.path.join(fixtures_dir, "benchmark_report.pdf")
    generate_benchmark_pdf(pdf_path)
    print(f"Generated benchmark PDF at {pdf_path}")
