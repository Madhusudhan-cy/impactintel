import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.rag.hybrid import FusedEvidence


class ClaimVerification(BaseModel):
    claim: str
    status: str  # "Supported", "Partially supported", "Unsupported"
    matched_source: Optional[str] = None
    reason: str


class VerificationResult(BaseModel):
    is_verified: bool
    total_claims: int
    supported_claims: int
    unsupported_claims: List[str] = Field(default_factory=list)
    claims: List[ClaimVerification] = Field(default_factory=list)
    corrected_answer: Optional[str] = None


class EvidenceVerifier:
    """
    Evidence-grounded claim verifier for generated repository answers.
    Extracts factual claims and cross-references them against retrieved
    source code and graph relationships to prevent LLM hallucinations.
    """

    def verify_answer(
        self,
        answer: str,
        evidence: List[FusedEvidence]
    ) -> VerificationResult:
        if not answer.strip():
            return VerificationResult(
                is_verified=True,
                total_claims=0,
                supported_claims=0,
                unsupported_claims=[],
                claims=[]
            )

        # Build combined corpus of retrieved evidence text
        evidence_corpus = " ".join([f"{e.file_path} {e.symbol_name or ''} {e.content}" for e in evidence]).lower()
        graph_relationships = []
        for e in evidence:
            if e.graph_context:
                graph_relationships.append(f"{e.graph_context.get('node_id', '')} {e.graph_context.get('statement', '')}".lower())
        full_corpus = evidence_corpus + " " + " ".join(graph_relationships)

        # Split answer into sentence-level claims
        raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if len(s.strip()) > 15]

        claims: List[ClaimVerification] = []
        unsupported: List[str] = []

        for sentence in raw_sentences:
            # Extract technical terms, identifiers, and symbols mentioned in the sentence
            mentioned_identifiers = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", sentence)
            meaningful_identifiers = [
                tok.lower() for tok in mentioned_identifiers
                if len(tok) > 3 and tok.lower() not in (
                    "this", "that", "these", "those", "function", "method", "class",
                    "file", "calls", "called", "component", "returns", "based", "evidence",
                    "repository", "source", "which", "where", "shows", "defined"
                )
            ]

            if not meaningful_identifiers:
                claims.append(
                    ClaimVerification(
                        claim=sentence,
                        status="Supported",
                        reason="General explanatory sentence"
                    )
                )
                continue

            # Check presence of identifiers in the evidence corpus
            matches = [tok for tok in meaningful_identifiers if tok in full_corpus]
            match_ratio = len(matches) / len(meaningful_identifiers)

            if match_ratio >= 0.7:
                matched_file = next((e.file_path for e in evidence if any(tok in e.content.lower() for tok in matches)), None)
                claims.append(
                    ClaimVerification(
                        claim=sentence,
                        status="Supported",
                        matched_source=matched_file,
                        reason=f"Verified by identifiers: {', '.join(matches[:3])}"
                    )
                )
            elif match_ratio >= 0.3:
                claims.append(
                    ClaimVerification(
                        claim=sentence,
                        status="Partially supported",
                        reason=f"Partial identifier evidence found ({len(matches)}/{len(meaningful_identifiers)})"
                    )
                )
            else:
                unsupported.append(sentence)
                claims.append(
                    ClaimVerification(
                        claim=sentence,
                        status="Unsupported",
                        reason="No supporting code or graph evidence found in retrieved repository chunks"
                    )
                )

        is_verified = len(unsupported) == 0
        supported_count = sum(1 for c in claims if c.status == "Supported")

        # Generate corrected answer if unsupported claims were detected
        corrected = None
        if not is_verified:
            corrected = (
                f"{answer}\n\n"
                f"> **⚠️ Verification Note**: The following statement(s) could not be verified by repository evidence:\n"
                + "\n".join([f"> - *\"{u}\"*" for u in unsupported])
            )

        return VerificationResult(
            is_verified=is_verified,
            total_claims=len(claims),
            supported_claims=supported_count,
            unsupported_claims=unsupported,
            claims=claims,
            corrected_answer=corrected
        )
