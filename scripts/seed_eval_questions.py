import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select

from app.ai.embedding import GeminiEmbeddingAdapter
from app.core.db import async_session_maker
from app.models.document import Document, DocumentChunk
from app.models.eval import EvalQuestion
from app.models.user import User
from app.services.auth_service import get_password_hash
from app.services.rag.pdf_extractor import PDFExtractor
from app.services.rag.text_chunker import TextChunker

BENCHMARK_PDF = "benchmark_report.pdf"

QUESTIONS = [
    {
        "question": "What was the total net sales revenue for Acme Corp in FY 2023?",
        "expected_answer": "$42.5 billion",
        "expected_page": 2,
    },
    {
        "question": "What was the revenue for the Cloud Services segment?",
        "expected_answer": "$18.2 billion",
        "expected_page": 2,
    },
    {
        "question": "How much did Autonomous Systems revenue reach in FY 2023?",
        "expected_answer": "$4.2 billion",
        "expected_page": 2,
    },
    {
        "question": "What was the gross profit margin in FY 2023?",
        "expected_answer": "42.1%",
        "expected_page": 3,
    },
    {
        "question": "What was the operating income for the year?",
        "expected_answer": "$11.3 billion",
        "expected_page": 3,
    },
    {
        "question": "What was the diluted earnings per share (EPS)?",
        "expected_answer": "$4.15",
        "expected_page": 3,
    },
    {
        "question": "How many shares of common stock were repurchased?",
        "expected_answer": "15 million",
        "expected_page": 3,
    },
    {
        "question": "What were the total assets at the end of FY 2023?",
        "expected_answer": "$85.6 billion",
        "expected_page": 4,
    },
    {
        "question": "How much cash and cash equivalents did the company have?",
        "expected_answer": "$12.4 billion",
        "expected_page": 4,
    },
    {
        "question": "What were the total liabilities reported at?",
        "expected_answer": "$45.2 billion",
        "expected_page": 4,
    },
    {
        "question": "What was the long-term debt reduced to?",
        "expected_answer": "$18.5 billion",
        "expected_page": 4,
    },
    {
        "question": "What is the current ratio maintained by the company?",
        "expected_answer": "2.1x",
        "expected_page": 4,
    },
    {
        "question": "What is the projected CapEx for FY 2024?",
        "expected_answer": "$5.5 billion",
        "expected_page": 5,
    },
    {
        "question": "What is the anticipated effective tax rate for FY 2024?",
        "expected_answer": "21.0%",
        "expected_page": 5,
    },
    {
        "question": "How much will Research and development (R&D) investments increase to?",
        "expected_answer": "$6.8 billion",
        "expected_page": 5,
    },
]


async def seed_data():
    async with async_session_maker() as session:
        # Create a dummy user for the document
        stmt = select(User).filter_by(email="eval_user@example.com")
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            user = User(email="eval_user@example.com", hashed_password=get_password_hash("password123"))
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # Check if benchmark report exists
        stmt = select(Document).filter_by(filename=BENCHMARK_PDF, user_id=user.id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc:
            print("Uploading and embedding benchmark PDF...")
            pdf_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests", "fixtures", BENCHMARK_PDF)

            doc = Document(
                user_id=user.id,
                filename=BENCHMARK_PDF,
                storage_path=pdf_path,  # Point directly to fixture
                status="PROCESSING",
                file_size=os.path.getsize(pdf_path),
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)

            # Embed synchronously
            extractor = PDFExtractor()
            chunker = TextChunker(max_chars=1000)
            adapter = GeminiEmbeddingAdapter()

            pages = extractor.extract_pages(pdf_path)
            chunks_dicts = chunker.chunk_pages(pages)

            texts = [c["chunk_text"] for c in chunks_dicts]
            embeddings = await adapter.embed_documents(texts)

            db_chunks = []
            for i, chunk_data in enumerate(chunks_dicts):
                db_chunks.append(
                    DocumentChunk(
                        document_id=doc.id,
                        page_number=chunk_data["page_number"],
                        chunk_index=chunk_data["chunk_index"],
                        chunk_text=chunk_data["chunk_text"],
                        embedding=embeddings[i],
                    )
                )

            session.add_all(db_chunks)
            doc.status = "READY"
            await session.commit()
            print("Benchmark document ingested successfully.")

        # Insert EvalQuestions
        for q_data in QUESTIONS:
            stmt = select(EvalQuestion).filter_by(question_text=q_data["question"])
            res = await session.execute(stmt)
            if not res.scalar_one_or_none():
                q = EvalQuestion(
                    question_text=q_data["question"],
                    expected_answer=q_data["expected_answer"],
                    expected_document_filename=BENCHMARK_PDF,
                    expected_page_number=q_data["expected_page"],
                )
                session.add(q)

        await session.commit()
        print(f"Seeded {len(QUESTIONS)} evaluation questions.")


if __name__ == "__main__":
    asyncio.run(seed_data())
