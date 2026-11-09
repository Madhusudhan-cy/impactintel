from typing import List, Dict, Any, Optional
import httpx

from app.rag.hybrid import FusedEvidence


class AnswerGenerator:
    """
    Evidence-grounded answer generator for repository questions.
    Synthesizes structural Graph RAG facts, exact source lines, and code chunks.
    Supports local LLMs (Ollama / local inference endpoints) with a robust grounded synthesizer fallback.
    """

    def __init__(self, local_llm_url: Optional[str] = None, model_name: str = "qwen2.5-coder"):
        self.local_llm_url = local_llm_url
        self.model_name = model_name

    def generate_answer(
        self,
        query: str,
        evidence: List[FusedEvidence],
        history: Optional[List[Dict[str, str]]] = None,
        unsupported_feedback: Optional[List[str]] = None
    ) -> str:
        if not evidence:
            return (
                f"I could not find sufficient repository evidence to answer the question: '{query}'. "
                "The requested symbols or components do not appear to exist in this repository's indexed codebase."
            )

        # 1. Attempt local LLM call if endpoint is active
        if self.local_llm_url:
            try:
                return self._call_local_llm(query, evidence, history, unsupported_feedback)
            except Exception:
                pass  # Fall back to grounded evidence synthesizer

        # 2. Deterministic Evidence-Grounded Synthesizer
        return self._synthesize_grounded_answer(query, evidence, history)

    def _call_local_llm(
        self,
        query: str,
        evidence: List[FusedEvidence],
        history: Optional[List[Dict[str, str]]],
        unsupported_feedback: Optional[List[str]]
    ) -> str:
        prompt_lines = [
            "You are a repository impact intelligence assistant. Answer the user query using ONLY the provided code evidence.",
            "Do NOT speculate, guess, or invent functions, routes, or relationships that are not in the evidence.",
            "\nEVIDENCE:"
        ]
        for e in evidence:
            prompt_lines.append(f"--- File: {e.file_path} (Lines {e.start_line}-{e.end_line}) ---")
            if e.symbol_name:
                prompt_lines.append(f"Symbol: {e.symbol_type} {e.symbol_name}")
            prompt_lines.append(e.content)
            if e.graph_context:
                prompt_lines.append(f"Graph Relation: {e.graph_context.get('relation_type')} with {e.graph_context.get('node_id')}")

        if unsupported_feedback:
            prompt_lines.append(f"\nWARNING: In the previous attempt, these claims were unsupported: {', '.join(unsupported_feedback)}. Do not make them again.")

        prompt_lines.append(f"\nUSER QUESTION: {query}")
        prompt_lines.append("ANSWER (with file:line citations):")

        full_prompt = "\n".join(prompt_lines)

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                self.local_llm_url,
                json={"model": self.model_name, "prompt": full_prompt, "stream": False}
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", data.get("content", ""))

    def _synthesize_grounded_answer(
        self,
        query: str,
        evidence: List[FusedEvidence],
        history: Optional[List[Dict[str, str]]]
    ) -> str:
        """
        Generate a fully grounded explanation directly citing file:line references
        and graph relationships.
        """
        parts = []

        # Target symbols identified
        target_symbols = [e.symbol_name for e in evidence if e.symbol_name and e.symbol_type != "File"]
        top_chunk = evidence[0]

        parts.append(f"Based on the repository source code and structural knowledge graph:")

        # Explain primary matching symbol
        if top_chunk.symbol_name:
            parts.append(
                f"- **`{top_chunk.symbol_name}`** ({top_chunk.symbol_type}) is defined in "
                f"`{top_chunk.file_path}` (lines {top_chunk.start_line}–{top_chunk.end_line})."
            )

        # Explain Graph RAG structural relationships
        graph_callers = []
        graph_callees = []
        graph_renders = []
        graph_tests = []

        for e in evidence:
            ctx = e.graph_context
            if ctx:
                rel = ctx.get("relation_type", "")
                direction = ctx.get("direction", "")
                node = ctx.get("node_id", "")
                if direction == "caller" or rel in ("calls", "imports"):
                    graph_callers.append(node)
                elif direction == "dependency":
                    graph_callees.append(node)
                elif rel == "renders":
                    graph_renders.append(node)
                elif rel == "tests" or direction == "test":
                    graph_tests.append(node)

        if graph_callers:
            clean_callers = sorted(list(set(graph_callers)))
            parts.append(f"- **Callers / Invocations**: It is called by {', '.join([f'`{c}`' for c in clean_callers])}.")

        if graph_callees:
            clean_callees = sorted(list(set(graph_callees)))
            parts.append(f"- **Dependencies**: It depends on / calls {', '.join([f'`{c}`' for c in clean_callees])}.")

        if graph_renders:
            clean_renders = sorted(list(set(graph_renders)))
            parts.append(f"- **Component Rendering**: Rendered hierarchically by {', '.join([f'`{r}`' for r in clean_renders])}.")

        if graph_tests:
            clean_tests = sorted(list(set(graph_tests)))
            parts.append(f"- **Connected Tests**: Verified by {', '.join([f'`{t}`' for t in clean_tests])}.")

        # Add code snippet citation
        parts.append(f"\n**Source Implementation Snippet** (`{top_chunk.file_path}:{top_chunk.start_line}`):")
        snippet_lines = top_chunk.content.splitlines()[:6]
        parts.append("```" + (top_chunk.language or "javascript"))
        parts.append("\n".join(snippet_lines))
        parts.append("```")

        return "\n".join(parts)
