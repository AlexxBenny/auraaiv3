"""FactsMemory - Episodic memory for tool-derived facts

INVARIANTS:
1. Only ExtractedFacts go in, never raw results or prose
2. All entries have timestamp and provenance
3. Thread-safe, non-blocking
4. Automatic daily rotation
5. NO summaries stored (generate at recall time)
6. Schema versioning for forward compatibility

Storage: ~/.aura/facts/YYYY-MM-DD.json
"""

import json
import logging
import threading
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.response.fact_extractor import ExtractedFacts


@dataclass
class StoredFact:
    """A single stored fact entry.
    
    INVARIANTS:
    - facts are the raw extracted facts dict
    - fact_keys is deterministic (sorted keys)
    - No summaries stored
    """
    fact_id: str              # UUID
    timestamp: str            # ISO format for JSON serialization
    tool: str                 # Source tool
    query: str                # Original user query
    facts: Dict[str, Any]     # ExtractedFacts.facts
    fact_keys: List[str]      # Sorted keys present (deterministic)
    session_id: str           # Session for grouping
    schema_version: int = 1   # For forward compatibility
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StoredFact':
        # Handle schema migrations here
        version = data.get('schema_version', 1)
        if version < 1:
            # Future migration logic
            pass
        return cls(**data)


class FactsMemory:
    """Episodic memory for tool-derived facts.
    
    INVARIANTS:
    - Only ExtractedFacts go in, never raw results
    - All entries have timestamp and provenance
    - Thread-safe, non-blocking
    - Automatic daily rotation
    - NO summaries stored (generate at recall)
    
    Queries are BOUNDED by default to prevent accidental over-recall:
    - key-based filtering
    - tool filtering
    - time window (default 2 hours)
    - session filtering
    """
    
    RETENTION_DAYS = 30
    MAX_FACTS_PER_DAY = 1000
    DEFAULT_MAX_AGE_MINUTES = 120  # 2 hours default
    CURRENT_SCHEMA_VERSION = 1
    
    def __init__(self, storage_dir: Optional[Path] = None):
        if storage_dir is None:
            # Store in project root's .aura folder for development
            storage_dir = Path(__file__).parent.parent / ".aura" / "facts"
        
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache for current day (avoids repeated disk reads)
        self._today_cache: List[StoredFact] = []
        self._cache_date: Optional[str] = None
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Load today's facts into cache
        self._load_today()
        
        logging.warning(f"DEBUG: FactsMemory initialized: {self.storage_dir}, cache={len(self._today_cache)}")
    
    def store(self, extracted: ExtractedFacts, query: str, session_id: str) -> str:
        """Store extracted facts with full provenance.
        
        Args:
            extracted: ExtractedFacts from ResponsePipeline
            query: Original user query
            session_id: Current session ID
            
        Returns:
            fact_id: UUID of stored fact
            
        INVARIANT: Only accepts ExtractedFacts, never raw dicts.
        """
        if not isinstance(extracted, ExtractedFacts):
            raise TypeError("Only ExtractedFacts can be stored")
        
        # Skip storing if no meaningful facts
        if not extracted.facts or extracted.status != "success":
            logging.debug(f"FactsMemory: skipping non-success or empty facts")
            return ""
        
        fact_id = str(uuid.uuid4())
        now = datetime.now()
        
        stored = StoredFact(
            fact_id=fact_id,
            timestamp=now.isoformat(),
            tool=extracted.tool,
            query=query,
            facts=extracted.facts,
            fact_keys=sorted(extracted.facts.keys()),  # Deterministic
            session_id=session_id,
            schema_version=self.CURRENT_SCHEMA_VERSION
        )
        
        with self._lock:
            # Rotate if day changed
            today = now.strftime("%Y-%m-%d")
            if self._cache_date != today:
                self._flush_cache()
                self._cache_date = today
                self._today_cache = []
            
            # Enforce daily limit
            if len(self._today_cache) >= self.MAX_FACTS_PER_DAY:
                logging.warning("FactsMemory: daily limit reached, skipping store")
                return ""
            
            self._today_cache.append(stored)
            self._persist_today()
        
        logging.warning(f"DEBUG: FactsMemory.store() - stored {fact_id[:8]}, cache now={len(self._today_cache)}")
        return fact_id
    
    def query_by_keys(
        self,
        keys: List[str],
        tool: Optional[str] = None,
        max_age_minutes: Optional[int] = None,
        session_id: Optional[str] = None,
        limit: int = 20
    ) -> List[StoredFact]:
        """Query facts by key presence with bounded defaults.
        
        Args:
            keys: Required keys that must be present
            tool: Optional tool filter
            max_age_minutes: Max age (default 2 hours)
            session_id: Optional session filter
            limit: Max results to return
            
        Returns:
            List of matching StoredFact (newest first)
        """
        if max_age_minutes is None:
            max_age_minutes = self.DEFAULT_MAX_AGE_MINUTES
        
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        results = []
        
        with self._lock:
            logging.warning(f"DEBUG: query loop - cache_size={len(self._today_cache)}, cutoff={cutoff}")
            # Search today's cache first
            for fact in reversed(self._today_cache):
                if self._matches(fact, keys, tool, session_id, cutoff):
                    results.append(fact)
                    if len(results) >= limit:
                        break
            
            # If we need more and time window extends to previous days
            if len(results) < limit and max_age_minutes > 24 * 60:
                results.extend(self._search_historical(
                    keys, tool, session_id, cutoff, limit - len(results)
                ))
        
        logging.warning(f"DEBUG: query_by_keys(keys={keys}, tool={tool}, age={max_age_minutes}) -> {len(results)} results from cache={len(self._today_cache)}")
        return results
    
    def query_by_tool(
        self,
        tool_name: str,
        max_age_minutes: Optional[int] = None,
        limit: int = 10
    ) -> List[StoredFact]:
        """Query facts by tool name."""
        return self.query_by_keys(
            keys=[],
            tool=tool_name,
            max_age_minutes=max_age_minutes,
            limit=limit
        )
    
    def query_recent(
        self,
        minutes: int = 30,
        limit: int = 20
    ) -> List[StoredFact]:
        """Query recent facts within time window."""
        return self.query_by_keys(
            keys=[],
            max_age_minutes=minutes,
            limit=limit
        )
    
    def _matches(
        self,
        fact: StoredFact,
        keys: List[str],
        tool: Optional[str],
        session_id: Optional[str],
        cutoff: datetime
    ) -> bool:
        """Check if fact matches all filters."""
        # Time check
        try:
            ts = datetime.fromisoformat(fact.timestamp)
            if ts < cutoff:
                logging.warning(f"DEBUG: _matches FAIL: ts={ts} < cutoff={cutoff}")
                return False
        except ValueError:
            return False
        
        # Tool check
        if tool and fact.tool != tool:
            return False
        
        # Session check
        if session_id and fact.session_id != session_id:
            return False
        
        # Key check (all keys must be present)
        if keys:
            for key in keys:
                if key not in fact.fact_keys:
                    return False
        
        logging.warning(f"DEBUG: _matches PASS: ts={ts}")
        return True
    
    def _search_historical(
        self,
        keys: List[str],
        tool: Optional[str],
        session_id: Optional[str],
        cutoff: datetime,
        limit: int
    ) -> List[StoredFact]:
        """Search historical fact files."""
        results = []
        
        # Get all fact files sorted by date (newest first)
        files = sorted(self.storage_dir.glob("*.json"), reverse=True)
        
        for file in files[1:]:  # Skip today (already searched)
            try:
                date_str = file.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                # Skip if file is entirely before cutoff
                if file_date.date() < cutoff.date():
                    break
                
                with open(file, 'r') as f:
                    data = json.load(f)
                
                for item in reversed(data.get("facts", [])):
                    fact = StoredFact.from_dict(item)
                    if self._matches(fact, keys, tool, session_id, cutoff):
                        results.append(fact)
                        if len(results) >= limit:
                            return results
                            
            except Exception as e:
                logging.debug(f"FactsMemory: failed to read {file}: {e}")
        
        return results
    
    def _load_today(self):
        """Load today's facts into cache."""
        today = datetime.now().strftime("%Y-%m-%d")
        today_file = self.storage_dir / f"{today}.json"
        
        self._cache_date = today
        self._today_cache = []
        
        if today_file.exists():
            try:
                with open(today_file, 'r') as f:
                    data = json.load(f)
                
                for item in data.get("facts", []):
                    self._today_cache.append(StoredFact.from_dict(item))
                
                logging.debug(f"FactsMemory: loaded {len(self._today_cache)} facts for today")
            except Exception as e:
                logging.warning(f"FactsMemory: failed to load today's facts: {e}")
    
    def _persist_today(self):
        """Persist today's cache to disk."""
        if not self._cache_date:
            return
        
        today_file = self.storage_dir / f"{self._cache_date}.json"
        
        try:
            data = {
                "date": self._cache_date,
                "schema_version": self.CURRENT_SCHEMA_VERSION,
                "count": len(self._today_cache),
                "facts": [f.to_dict() for f in self._today_cache]
            }
            
            with open(today_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logging.error(f"FactsMemory: failed to persist: {e}")
    
    def _flush_cache(self):
        """Flush cache before day rotation."""
        if self._today_cache and self._cache_date:
            self._persist_today()
    
    def prune_old_facts(self):
        """Remove facts older than retention period."""
        cutoff = datetime.now() - timedelta(days=self.RETENTION_DAYS)
        
        for file in self.storage_dir.glob("*.json"):
            try:
                date_str = file.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                if file_date < cutoff:
                    file.unlink()
                    logging.info(f"FactsMemory: pruned {file.name}")
                    
            except Exception as e:
                logging.debug(f"FactsMemory: prune error for {file}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        with self._lock:
            files = list(self.storage_dir.glob("*.json"))
            return {
                "today_count": len(self._today_cache),
                "total_files": len(files),
                "storage_dir": str(self.storage_dir),
                "retention_days": self.RETENTION_DAYS
            }


# Singleton instance
_facts_memory: Optional[FactsMemory] = None


def get_facts_memory() -> FactsMemory:
    """Get or create the global FactsMemory instance."""
    global _facts_memory
    if _facts_memory is None:
        logging.warning("DEBUG: Creating NEW FactsMemory singleton")
        _facts_memory = FactsMemory()
        logging.warning(f"DEBUG: NEW singleton id={id(_facts_memory)}")
    else:
        logging.warning(f"DEBUG: Reusing singleton id={id(_facts_memory)}, cache={len(_facts_memory._today_cache)}")
    return _facts_memory
