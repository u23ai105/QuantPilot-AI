import asyncio
import os
import sys

from sqlalchemy import select

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


from langchain_core.messages import HumanMessage

# Import the context var from ai.tools.documents where it is defined,
# or define it locally and mock it out if needed.
# Since we need to pass user_id to the tools, let's look at how test_rag.py does it.
from app.ai.tools.documents import _current_user_id
from app.core.db import async_session_maker
from app.models.eval import EvalQuestion, EvalRun
from app.models.user import User
from app.services.eval_service import EvalService
from app.services.retrieval_service import RetrievalService


async def run_evaluation(only_unscored: bool = False, question_ids: list[int] | None = None):
    async with async_session_maker() as session:
        # Get the dummy eval user created by the seed script
        stmt = select(User).filter_by(email="eval_user@example.com")
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user:
            print("Eval user not found! Please run 'python scripts/seed_eval_questions.py' first.")
            return

        # Fetch questions.  Default: all of them.  --questions filters to explicit
        # IDs; --only-unscored skips questions that already have a *scored* run, so a
        # re-run scores just the remaining ones without appending duplicate rows
        # (question_id is not unique, so re-running would otherwise INSERT dupes).
        stmt = select(EvalQuestion).order_by(EvalQuestion.id)
        if question_ids:
            stmt = stmt.where(EvalQuestion.id.in_(question_ids))
        elif only_unscored:
            # "Scored" = has a run with a non-empty generated answer.  API-failed
            # rows (empty answer) don't count, so a quota-interrupted run resumes
            # cleanly on the next --only-unscored invocation.
            scored = select(EvalRun.question_id).where(EvalRun.generated_answer.isnot(None), EvalRun.generated_answer != "")
            stmt = stmt.where(EvalQuestion.id.notin_(scored))
        questions = (await session.execute(stmt)).scalars().all()
        if not questions:
            if question_ids:
                print(f"No eval questions matched IDs {question_ids}.")
            elif only_unscored:
                print("No unscored questions — every eval question already has an eval_runs row. Nothing to do.")
            else:
                print("No evaluation questions found! Please run 'python scripts/seed_eval_questions.py' first.")
            return

        print(f"Loaded {len(questions)} evaluation questions.")

        # Set the user ID for tools to use
        _current_user_id.set(user.id)

        retrieval_service = RetrievalService(session=session)

        # Build the evaluation agent from the SAME production wiring the app
        # uses (app/ai/service.py: AgentService) so eval measures what ships.
        from langgraph.checkpoint.memory import MemorySaver

        from app.ai.graph import build_graph
        from app.ai.provider import GeminiLLMAdapter
        from app.ai.service import ALL_TOOLS

        # GeminiLLMAdapter reads settings.gemini_model, so eval runs on the same
        # model the app ships (env-overridable). Rate limits are handled by the
        # fixed inter-question pacing and the 429 backoff loop below.
        model_with_tools = GeminiLLMAdapter().bind_tools(ALL_TOOLS)
        graph = build_graph(model_with_tools, ALL_TOOLS)
        compiled_graph = graph.compile(checkpointer=MemorySaver())

        results = []

        for q in questions:
            print(f"Evaluating Q{q.id}: {q.question_text}")

            try:
                retrieved_chunks = await retrieval_service.search(user_id=user.id, query=q.question_text, limit=5)

                formatted_chunks = []
                for c in retrieved_chunks:
                    formatted_chunks.append(
                        {
                            "filename": c.filename,
                            "page_number": c.page_number,
                            "chunk_index": c.chunk_index,
                            "text": c.chunk_text,
                            "similarity_score": c.similarity_score,
                        }
                    )

                retrieval_hit = EvalService.evaluate_retrieval(q.expected_document_filename, q.expected_page_number, formatted_chunks)
            except Exception as e:
                print(f"Retrieval error: {e}")
                retrieval_hit = False
                formatted_chunks = []

            # 2. Agent Execution
            inputs = {
                "messages": [
                    HumanMessage(
                        content="You are QuantPilot AI. Always use the search_documents tool to "
                        "find the exact figures in the user's documents. Explicitly cite "
                        "the document filename and page number in your final response using the exact format: "
                        "[Source: <filename>, Page: <page_number>]. Never invent citations. "
                        "Always include the citation when using document information."
                    ),
                    HumanMessage(content=q.question_text),
                ]
            }
            config = {"configurable": {"thread_id": f"eval_run_{q.id}"}}

            agent_response = ""
            is_api_failure = False

            # Rate limit backoff loop
            max_retries = 3
            for attempt in range(max_retries + 1):
                try:
                    async for event in compiled_graph.astream(inputs, config, stream_mode="values"):
                        last_message = event["messages"][-1]
                        if last_message.type == "ai":
                            if isinstance(last_message.content, str):
                                agent_response = last_message.content
                            elif isinstance(last_message.content, list):
                                # Extract text from list of blocks
                                text_blocks = [b.get("text", "") for b in last_message.content if isinstance(b, dict) and "text" in b]
                                if text_blocks:
                                    agent_response = " ".join(text_blocks)
                                else:
                                    agent_response = str(last_message.content)

                    if not agent_response:
                        is_api_failure = True
                    else:
                        is_api_failure = False
                    break  # Success, exit retry loop

                except Exception as e:
                    print(f"Agent error (attempt {attempt + 1}): {e}")
                    agent_response = ""
                    if "429" in str(e) or "rate limit" in str(e).lower() or "RESOURCE_EXHAUSTED" in str(e):
                        if attempt < max_retries:
                            delay = 2**attempt * 5  # 5s, 10s, 20s
                            print(f"Rate limited. Retrying in {delay}s...")
                            await asyncio.sleep(delay)
                        else:
                            is_api_failure = True
                    else:
                        is_api_failure = True  # Other unhandled errors
                        break

            # 3. Citation Evaluation
            citation_hit = EvalService.evaluate_citation(q.expected_document_filename, q.expected_page_number, agent_response)
            canonical_format_hit = EvalService.evaluate_canonical_format(q.expected_document_filename, q.expected_page_number, agent_response)

            # 4. Answer Quality Evaluation
            answer_hit = EvalService.evaluate_answer_quality(q.expected_answer, agent_response, tolerance=0.05)

            # 5. Persist EvalRun
            run = EvalRun(
                question_id=q.id,
                retrieval_hit=retrieval_hit,
                citation_hit=citation_hit,
                canonical_format_hit=canonical_format_hit,
                answer_hit=answer_hit,
                generated_answer=agent_response,
                retrieved_sources_json={
                    "top_5": [
                        {
                            "document_id": c["filename"],
                            "page_number": c["page_number"],
                            "chunk_index": c["chunk_index"],
                            "similarity_score": c["similarity_score"],
                        }
                        for c in formatted_chunks
                    ]
                },
            )
            session.add(run)
            await session.commit()

            results.append(
                {
                    "id": q.id,
                    "retrieval": retrieval_hit,
                    "citation": citation_hit,
                    "canonical": canonical_format_hit,
                    "answer": answer_hit,
                    "api_failure": is_api_failure,
                }
            )

            # Proactive pacing between questions to respect free-tier RPM limits
            # (complements the reactive 429 backoff above). Skip after the last question.
            if q is not questions[-1]:
                print("Waiting 5s to avoid rate limits...")
                await asyncio.sleep(5)

        # 6. Terminal Report
        print("\n================ EVALUATION REPORT ================")
        print(f"{'Question':<10} {'Status':<15} {'Retrieval@5':<15} {'Citation':<12} {'Canonical':<12} {'Answer':<10}")
        print("-" * 78)

        ret_hits = 0
        cit_hits = 0
        can_hits = 0
        ans_hits = 0
        api_failures = 0
        success_count = 0

        for r in results:
            ret_mark = "✓" if r["retrieval"] else "✗"

            if r["api_failure"]:
                status = "API_FAILURE"
                cit_mark = "N/A"
                can_mark = "N/A"
                ans_mark = "N/A"
                api_failures += 1
            else:
                status = "SUCCESS"
                cit_mark = "✓" if r["citation"] else "✗"
                can_mark = "✓" if r["canonical"] else "✗"
                ans_mark = "✓" if r["answer"] else "✗"
                success_count += 1
                cit_hits += 1 if r["citation"] else 0
                can_hits += 1 if r["canonical"] else 0
                ans_hits += 1 if r["answer"] else 0

            ret_hits += 1 if r["retrieval"] else 0

            print(f"Q{r['id']:<9} {status:<15} {ret_mark:<15} {cit_mark:<12} {can_mark:<12} {ans_mark:<10}")

        print("\n================ AGGREGATE METRICS ================")
        total = len(results)
        print("ALL QUESTIONS:")
        print(f"Questions attempted: {total}")
        print(f"Retrieval Hit@5:   {ret_hits}/{total} ({(ret_hits / total) * 100:.1f}%)")
        print(f"API failures:      {api_failures}")
        print(f"\nSUCCESSFUL GENERATIONS: {success_count}/{total}")
        if success_count > 0:
            print(f"Citation Accuracy:                     {cit_hits}/{success_count} ({(cit_hits / success_count) * 100:.1f}%)")
            print(f"Canonical Citation Format Compliance:  {can_hits}/{success_count} ({(can_hits / success_count) * 100:.1f}%)")
            print(f"Answer Quality:                        {ans_hits}/{success_count} ({(ans_hits / success_count) * 100:.1f}%)")
        else:
            print("Citation Accuracy:                     N/A (0 successful generations)")
            print("Canonical Citation Format Compliance:  N/A (0 successful generations)")
            print("Answer Quality:                        N/A (0 successful generations)")
        print("===================================================\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the RAG eval harness (deterministic scoring).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--only-unscored",
        action="store_true",
        help="Only run questions with no existing eval_runs row (skip already-scored ones).",
    )
    group.add_argument(
        "--questions",
        help="Comma-separated EvalQuestion IDs to run, e.g. --questions 10,11,12.",
    )
    _args = parser.parse_args()
    _ids = [int(x) for x in _args.questions.split(",") if x.strip()] if _args.questions else None

    asyncio.run(run_evaluation(only_unscored=_args.only_unscored, question_ids=_ids))
