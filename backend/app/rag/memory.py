from typing import List, Dict, Any, Optional
import uuid


class ConversationManager:
    """
    Manages short-term conversational memory for repository Q&A sessions.
    Strictly scoped to a single repository to prevent cross-repository context leakage.
    Resolves follow-up questions (anaphora resolution) using conversational history.
    """

    def __init__(self):
        # Map conversation_id -> dict(repository_id, messages, entities)
        self._conversations: Dict[str, Dict[str, Any]] = {}

    def get_or_create_conversation(self, conversation_id: Optional[str], repository_id: int) -> str:
        """Create a new conversation or validate repository scoping for existing one."""
        cid = conversation_id or str(uuid.uuid4())
        if cid in self._conversations:
            # Enforce repository boundary security
            if self._conversations[cid]["repository_id"] != repository_id:
                raise PermissionError("Access denied: Conversation belongs to a different repository.")
        else:
            self._conversations[cid] = {
                "repository_id": repository_id,
                "messages": [],
                "recent_entities": []
            }
        return cid

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        entities: Optional[List[str]] = None
    ) -> None:
        """Append a message turn to the conversation history."""
        if conversation_id not in self._conversations:
            return
        self._conversations[conversation_id]["messages"].append({"role": role, "content": content})
        if entities:
            # Update recent entities (store most recent first)
            self._conversations[conversation_id]["recent_entities"] = list(entities) + self._conversations[conversation_id]["recent_entities"]
            self._conversations[conversation_id]["recent_entities"] = self._conversations[conversation_id]["recent_entities"][:10]

    def get_history(self, conversation_id: str, repository_id: int) -> List[Dict[str, str]]:
        """Retrieve message history for authorized repository."""
        if conversation_id not in self._conversations:
            return []
        if self._conversations[conversation_id]["repository_id"] != repository_id:
            return []
        return list(self._conversations[conversation_id]["messages"])

    def resolve_followup_query(self, query: str, conversation_id: str) -> str:
        """
        Resolve anaphoric follow-up references using short-term conversational context.
        Example:
            User: 'What does the first one do?'
            Recent entities: ['Checkout', 'PaymentService']
            Resolves to: 'What does Checkout do?'
        """
        if conversation_id not in self._conversations:
            return query

        conv = self._conversations[conversation_id]
        recent = conv.get("recent_entities", [])
        if not recent:
            return query

        query_lower = query.lower()
        # Resolve 'the first one'
        if "first one" in query_lower and len(recent) >= 1:
            return query.replace("the first one", recent[0]).replace("first one", recent[0])

        # Resolve 'the second one'
        if "second one" in query_lower and len(recent) >= 2:
            return query.replace("the second one", recent[1]).replace("second one", recent[1])

        # Resolve vague pronouns like 'what does it do?'
        if query_lower.strip() in ("what does it do?", "what does this do?", "show its tests", "explain it"):
            return f"{query} (referring to {recent[0]})"

        return query
