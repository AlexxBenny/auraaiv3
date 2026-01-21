"""Post-Mortem Memory - Write-only storage of execution outcomes for learning

LOCKED INVARIANT (from v3 design - Invariant 2):
PostMortemMemory may be read ONLY before planning, never:
- During tool execution
- During tool selection
- During eligibility checks
- During effect evaluation

This is WRITE-ONLY during execution. No safety bypass allowed.

See: task_decomposition_agent_design_v3_final.md
"""

import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class PostMortemRecord:
    """Record of a subtask execution for learning."""
    
    timestamp: str
    subtask_description: str
    intent: str
    effects: List[Dict]
    tools_used: List[str]
    outcome: str  # "success" | "failure" | "refused" | "partial" | "information"
    failure_reason: Optional[str]
    user_input_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PostMortemMemory:
    """
    Stores execution outcomes for future learning.
    
    INVARIANTS (DO NOT VIOLATE):
    - Write-only during execution (no reads that affect current execution)
    - Non-blocking (failures are logged, not raised)
    - No safety bypass (data is for biasing future prompts, not overriding policy)
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = Path.home() / ".aura" / "postmortem.json"
        
        self.storage_path = storage_path
        self.records: List[PostMortemRecord] = []
        
        # Ensure directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing records
        self._load()
        
        logging.info(f"PostMortemMemory initialized: {len(self.records)} records loaded")
    
    def _load(self) -> None:
        """Load existing records from storage."""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data.get("records", []):
                    self.records.append(PostMortemRecord(
                        timestamp=item.get("timestamp", ""),
                        subtask_description=item.get("subtask_description", ""),
                        intent=item.get("intent", ""),
                        effects=item.get("effects", []),
                        tools_used=item.get("tools_used", []),
                        outcome=item.get("outcome", ""),
                        failure_reason=item.get("failure_reason"),
                        user_input_hash=item.get("user_input_hash", "")
                    ))
        except Exception as e:
            logging.warning(f"Failed to load PostMortemMemory: {e}")
    
    def _persist(self) -> None:
        """Persist records to storage."""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "version": "1.0",
                    "record_count": len(self.records),
                    "records": [r.to_dict() for r in self.records]
                }, f, indent=2, default=str)
        except Exception as e:
            logging.warning(f"Failed to persist PostMortemMemory: {e}")
    
    def record(self, subtask_description: str, intent: str,
               effects: List[Dict], tools_used: List[str],
               outcome: str, failure_reason: Optional[str] = None) -> None:
        """
        Record a subtask execution outcome.
        
        Called AFTER CriticAgent, never during execution.
        
        INVARIANT: Non-blocking. Failures are logged, not raised.
        """
        try:
            record = PostMortemRecord(
                timestamp=datetime.now().isoformat(),
                subtask_description=subtask_description,
                intent=intent,
                effects=effects,
                tools_used=tools_used,
                outcome=outcome,
                failure_reason=failure_reason,
                user_input_hash=hashlib.md5(subtask_description.encode()).hexdigest()[:8]
            )
            self.records.append(record)
            self._persist()
            logging.debug(f"PostMortem recorded: {outcome} for '{subtask_description[:50]}...'")
        except Exception as e:
            # Non-blocking — log and continue
            logging.warning(f"PostMortem record failed: {e}")
    
    # =========================================================================
    # FUTURE USE ONLY - NOT FOR EXECUTION TIME
    # =========================================================================
    # The following methods are for use BEFORE planning (prompt biasing),
    # NEVER during execution. This is enforced by design review, not code.
    # =========================================================================
    
    def get_recent_failures(self, limit: int = 10) -> List[PostMortemRecord]:
        """
        Retrieve recent failures for future planning bias.
        
        INVARIANT: Call BEFORE planning, not during execution.
        """
        failures = [r for r in self.records if r.outcome in ["failure", "refused"]]
        return failures[-limit:] if failures else []
    
    def get_similar_outcomes(self, description: str, limit: int = 5) -> List[PostMortemRecord]:
        """
        Retrieve similar past outcomes for future planning bias.
        
        INVARIANT: Call BEFORE planning, not during execution.
        
        Uses simple keyword matching. Future: vector similarity via Qdrant.
        """
        keywords = set(description.lower().split())
        
        scored = []
        for record in self.records:
            record_keywords = set(record.subtask_description.lower().split())
            overlap = len(keywords & record_keywords)
            if overlap > 0:
                scored.append((overlap, record))
        
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:limit]]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get summary statistics of recorded outcomes."""
        total = len(self.records)
        if total == 0:
            return {"total": 0}
        
        outcomes = {}
        for r in self.records:
            outcomes[r.outcome] = outcomes.get(r.outcome, 0) + 1
        
        return {
            "total": total,
            "outcomes": outcomes,
            "success_rate": outcomes.get("success", 0) / total if total > 0 else 0
        }
