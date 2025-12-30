"""Procedural Memory - Stores tool proposals and learned skills"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class ProceduralMemory:
    """Stores tool proposals, approved tools, and skill metadata"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = Path.home() / ".aura" / "procedural_memory.json"
        
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing memory
        self.memory = self._load_memory()
        
        logging.info(f"ProceduralMemory initialized: {len(self.memory.get('tools', []))} tools stored")
    
    def _load_memory(self) -> Dict[str, Any]:
        """Load procedural memory from disk"""
        if not self.storage_path.exists():
            return {
                "tools": [],
                "proposals": [],
                "rejected": [],
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "version": "1.0"
                }
            }
        
        try:
            with open(self.storage_path, 'r') as f:
                content = f.read().strip()
                if not content:
                    # Empty file, return default
                    return {
                        "tools": [],
                        "proposals": [],
                        "rejected": [],
                        "metadata": {
                            "created_at": datetime.now().isoformat(),
                            "version": "1.0"
                        }
                    }
                return json.loads(content)
        except json.JSONDecodeError as e:
            logging.warning(f"Invalid JSON in procedural memory, resetting: {e}")
            return {
                "tools": [],
                "proposals": [],
                "rejected": [],
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "version": "1.0"
                }
            }
        except Exception as e:
            logging.error(f"Error loading procedural memory: {e}")
            return {
                "tools": [],
                "proposals": [],
                "rejected": [],
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "version": "1.0"
                }
            }
    
    def _save_memory(self):
        """Save procedural memory to disk"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving procedural memory: {e}")
    
    def store_proposal(self, proposal: Dict[str, Any], goal: str, validation_result: Dict[str, Any]) -> str:
        """Store a tool proposal
        
        Args:
            proposal: Tool proposal from LimitationAnalysisAgent
            goal: Original user goal
            validation_result: Validation result from SkillGate
            
        Returns:
            Proposal ID
        """
        proposal_id = f"proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        record = {
            "id": proposal_id,
            "status": "proposed",
            "proposed_tool": proposal.get("proposed_tool", {}),
            "rationale": proposal.get("rationale", ""),
            "alternative_approaches": proposal.get("alternative_approaches", []),
            "created_from_goal": goal,
            "created_at": datetime.now().isoformat(),
            "validation": validation_result,
            "approved": False,
            "implemented": False
        }
        
        self.memory["proposals"].append(record)
        self._save_memory()
        
        logging.info(f"Proposal stored: {proposal_id} - {proposal.get('proposed_tool', {}).get('name', 'unknown')}")
        return proposal_id
    
    def approve_proposal(self, proposal_id: str, implementation_path: Optional[str] = None):
        """Mark a proposal as approved and implemented"""
        for proposal in self.memory["proposals"]:
            if proposal["id"] == proposal_id:
                proposal["approved"] = True
                proposal["implemented"] = True
                proposal["implementation_path"] = implementation_path
                proposal["approved_at"] = datetime.now().isoformat()
                
                # Move to tools list
                tool_record = {
                    "name": proposal["proposed_tool"]["name"],
                    "description": proposal["proposed_tool"]["description"],
                    "category": proposal["proposed_tool"].get("category", "other"),
                    "created_from_proposal": proposal_id,
                    "registered_at": datetime.now().isoformat()
                }
                self.memory["tools"].append(tool_record)
                
                self._save_memory()
                logging.info(f"Proposal approved: {proposal_id}")
                return
        
        raise ValueError(f"Proposal not found: {proposal_id}")
    
    def reject_proposal(self, proposal_id: str, reason: str):
        """Mark a proposal as rejected"""
        for proposal in self.memory["proposals"]:
            if proposal["id"] == proposal_id:
                proposal["status"] = "rejected"
                proposal["rejection_reason"] = reason
                proposal["rejected_at"] = datetime.now().isoformat()
                
                # Move to rejected list
                self.memory["rejected"].append(proposal)
                self.memory["proposals"].remove(proposal)
                
                self._save_memory()
                logging.info(f"Proposal rejected: {proposal_id} - {reason}")
                return
        
        raise ValueError(f"Proposal not found: {proposal_id}")
    
    def get_pending_proposals(self) -> List[Dict[str, Any]]:
        """Get all pending proposals"""
        return [
            p for p in self.memory["proposals"]
            if p["status"] == "proposed" and not p["approved"]
        ]
    
    def get_approved_tools(self) -> List[Dict[str, Any]]:
        """Get all approved/implemented tools"""
        return self.memory.get("tools", [])
    
    def find_similar_proposal(self, goal: str) -> Optional[Dict[str, Any]]:
        """Find similar proposals for a goal"""
        # Simple similarity check (can be enhanced)
        goal_lower = goal.lower()
        for proposal in self.memory["proposals"]:
            proposal_goal = proposal.get("created_from_goal", "").lower()
            if goal_lower in proposal_goal or proposal_goal in goal_lower:
                return proposal
        return None

