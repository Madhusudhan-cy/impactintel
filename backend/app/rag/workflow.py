from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from app.rag.hybrid import HybridRetriever, FusedEvidence
from app.rag.generator import AnswerGenerator
from app.rag.verifier import EvidenceVerifier, VerificationResult
from app.rag.memory import ConversationManager


class RAGWorkflowState(TypedDict):
    query: str
    repository_id: int
    conversation_id: str
    history: List[Dict[str, str]]
    resolved_query: str
    identified_entities: List[str]
    graph_retrieval_results: List[Dict[str, Any]]
    bm25_results: List[Dict[str, Any]]
    vector_search_results: List[Dict[str, Any]]
    fused_evidence: List[Dict[str, Any]]
    reranked_evidence: List[Dict[str, Any]]
    generated_answer: str
    verification: Dict[str, Any]
    is_verified: bool
    retry_count: int
    unsupported_feedback: List[str]
    final_response: Dict[str, Any]


class ConversationalRAGOrchestrator:
    """
    Coordinates the multi-stage LangGraph workflow for Conversational Repository Intelligence:
        Query Understanding
        ➔ Parallel Hybrid Retrieval (Graph RAG + BM25 + Vector Search)
        ➔ LLM Answer Generation
        ➔ Evidence-Based Claim Verification
        ➔ Bounded Conditional Retry
        ➔ Final Grounded Response
    """

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        answer_generator: Optional[AnswerGenerator] = None,
        verifier: Optional[EvidenceVerifier] = None,
        memory_manager: Optional[ConversationManager] = None
    ):
        self.retriever = hybrid_retriever
        self.generator = answer_generator or AnswerGenerator()
        self.verifier = verifier or EvidenceVerifier()
        self.memory = memory_manager or ConversationManager()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(RAGWorkflowState)

        # 1. Add Nodes
        builder.add_node("query_understanding", self._query_understanding_node)
        builder.add_node("hybrid_retrieval", self._hybrid_retrieval_node)
        builder.add_node("generation", self._generation_node)
        builder.add_node("verification", self._verification_node)
        builder.add_node("finish", self._finish_node)

        # 2. Add Edges
        builder.set_entry_point("query_understanding")
        builder.add_edge("query_understanding", "hybrid_retrieval")
        builder.add_edge("hybrid_retrieval", "generation")
        builder.add_edge("generation", "verification")

        # 3. Conditional Retry Edge
        builder.add_conditional_edges(
            "verification",
            self._should_retry_or_finish,
            {
                "retry": "generation",
                "finish": "finish"
            }
        )
        builder.add_edge("finish", END)

        return builder.compile()

    # --- Node Implementations ---

    def _query_understanding_node(self, state: RAGWorkflowState) -> Dict[str, Any]:
        cid = state["conversation_id"]
        raw_query = state["query"]
        history = self.memory.get_history(cid, state["repository_id"])

        # Resolve anaphora (e.g. 'what does the first one do?')
        resolved_query = self.memory.resolve_followup_query(raw_query, cid)

        return {
            "resolved_query": resolved_query,
            "history": history,
            "retry_count": 0,
            "unsupported_feedback": []
        }

    def _hybrid_retrieval_node(self, state: RAGWorkflowState) -> Dict[str, Any]:
        query = state["resolved_query"]
        repo_id = state["repository_id"]

        fused_items: List[FusedEvidence] = self.retriever.retrieve(
            query=query,
            top_k=5,
            repository_id=repo_id
        )

        identified = []
        for f in fused_items:
            if f.symbol_name and f.symbol_name not in identified:
                identified.append(f.symbol_name)

        return {
            "fused_evidence": [f.model_dump() for f in fused_items],
            "identified_entities": identified
        }

    def _generation_node(self, state: RAGWorkflowState) -> Dict[str, Any]:
        fused_objects = [FusedEvidence(**item) for item in state["fused_evidence"]]
        answer = self.generator.generate_answer(
            query=state["resolved_query"],
            evidence=fused_objects,
            history=state["history"],
            unsupported_feedback=state.get("unsupported_feedback")
        )
        return {"generated_answer": answer}

    def _verification_node(self, state: RAGWorkflowState) -> Dict[str, Any]:
        fused_objects = [FusedEvidence(**item) for item in state["fused_evidence"]]
        res: VerificationResult = self.verifier.verify_answer(
            answer=state["generated_answer"],
            evidence=fused_objects
        )

        current_retry = state.get("retry_count", 0)
        new_retry = current_retry if res.is_verified else current_retry + 1

        corrected_ans = res.corrected_answer
        if not res.is_verified and not corrected_ans:
            corrected_ans = (
                f"{state['generated_answer']}\n\n"
                f"> **⚠️ Verification Note**: The following claim(s) could not be verified by repository evidence:\n"
                + "\n".join([f"> - *\"{u}\"*" for u in res.unsupported_claims])
            )

        return {
            "verification": res.model_dump(),
            "is_verified": res.is_verified,
            "retry_count": new_retry,
            "unsupported_feedback": res.unsupported_claims,
            "generated_answer": corrected_ans if corrected_ans else state["generated_answer"]
        }

    def _should_retry_or_finish(self, state: RAGWorkflowState) -> str:
        # Bounded retry: maximum 2 retries to prevent infinite loops
        if state["is_verified"] or state.get("retry_count", 0) >= 2:
            return "finish"
        return "retry"

    def _finish_node(self, state: RAGWorkflowState) -> Dict[str, Any]:
        final_answer = state["generated_answer"]
        cid = state["conversation_id"]

        # Record conversation turn in memory
        self.memory.add_message(cid, "user", state["query"])
        self.memory.add_message(
            cid,
            "assistant",
            final_answer,
            entities=state.get("identified_entities", [])
        )

        final_response = {
            "conversation_id": cid,
            "query": state["query"],
            "resolved_query": state["resolved_query"],
            "answer": final_answer,
            "is_verified": state["is_verified"],
            "verification": state["verification"],
            "retrieval_evidence": state["fused_evidence"],
            "identified_entities": state["identified_entities"]
        }
        return {"final_response": final_response}

    def ask(self, query: str, repository_id: int, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute the LangGraph workflow and return the verified repository answer."""
        cid = self.memory.get_or_create_conversation(conversation_id, repository_id)
        init_state: RAGWorkflowState = {
            "query": query,
            "repository_id": repository_id,
            "conversation_id": cid,
            "history": [],
            "resolved_query": query,
            "identified_entities": [],
            "graph_retrieval_results": [],
            "bm25_results": [],
            "vector_search_results": [],
            "fused_evidence": [],
            "reranked_evidence": [],
            "generated_answer": "",
            "verification": {},
            "is_verified": False,
            "retry_count": 0,
            "unsupported_feedback": [],
            "final_response": {}
        }

        output = self.graph.invoke(init_state)
        return output["final_response"]
