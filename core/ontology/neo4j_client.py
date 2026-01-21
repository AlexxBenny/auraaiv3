"""Neo4j Client - Connection management and constraint queries

This module is the ONLY interface between AURA and Neo4j.
All constraint queries go through here.

Principle: Neo4j is the source of truth for tool eligibility.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from contextlib import contextmanager

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable, AuthError
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    GraphDatabase = None
    ServiceUnavailable = Exception
    AuthError = Exception


# Default connection settings
DEFAULT_URI = "bolt://localhost:7687"
DEFAULT_USER = "neo4j"
DEFAULT_PASSWORD = "password"  # From Docker NEO4J_AUTH=neo4j/password


@dataclass
class ConstraintInfo:
    """Single constraint from Neo4j"""
    name: str
    constraint_type: str
    blocking: bool
    resolvable: bool
    resolution_hint: str


@dataclass
class ToolConstraints:
    """Constraints for a single tool"""
    tool: str
    blocking_constraints: List[ConstraintInfo]
    soft_constraints: List[ConstraintInfo]
    found: bool  # Whether tool exists in Neo4j


class Neo4jConnectionError(Exception):
    """Raised when Neo4j connection fails"""
    pass


class Neo4jClient:
    """
    Neo4j client for tool ontology queries.
    
    FAIL CLOSED: If Neo4j is unavailable, queries return error state.
    Planner must refuse execution when this happens.
    """
    
    # The eligibility query - queries ONLY REQUIRES relationships
    # ENABLES is explicitly NOT queried for safety decisions
    CONSTRAINT_QUERY = """
    MATCH (t:Tool {name: $tool_name})
    OPTIONAL MATCH (t)-[:REQUIRES]->(c:Constraint)
    WITH t, collect({
        name: c.name,
        constraint_type: c.constraint_type,
        blocking: c.blocking,
        resolvable: c.resolvable,
        resolution_hint: c.resolution_hint
    }) AS constraints
    RETURN t.name AS tool,
           [c IN constraints WHERE c.blocking = true] AS blocking_constraints,
           [c IN constraints WHERE c.blocking = false] AS soft_constraints
    """
    
    def __init__(
        self,
        uri: str = DEFAULT_URI,
        user: str = DEFAULT_USER,
        password: str = DEFAULT_PASSWORD
    ):
        self._uri = uri
        self._user = user
        self._password = password
        self._driver = None
        self._connected = False
        
        if not NEO4J_AVAILABLE:
            logging.error("Neo4j driver not installed. Run: pip install neo4j")
    
    def connect(self) -> bool:
        """
        Establish connection to Neo4j.
        
        Returns:
            True if connected, False otherwise
        """
        if not NEO4J_AVAILABLE:
            logging.error("Neo4j driver not available")
            return False
        
        try:
            self._driver = GraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password)
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            self._connected = True
            logging.info(f"Connected to Neo4j at {self._uri}")
            return True
        except AuthError as e:
            logging.error(f"Neo4j authentication failed: {e}")
            self._connected = False
            return False
        except ServiceUnavailable as e:
            logging.error(f"Neo4j service unavailable: {e}")
            self._connected = False
            return False
        except Exception as e:
            logging.error(f"Neo4j connection failed: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Close Neo4j connection"""
        if self._driver:
            self._driver.close()
            self._driver = None
            self._connected = False
            logging.info("Disconnected from Neo4j")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Neo4j"""
        return self._connected and self._driver is not None
    
    @contextmanager
    def session(self):
        """Get a Neo4j session with automatic cleanup"""
        if not self.is_connected:
            if not self.connect():
                raise Neo4jConnectionError("Cannot connect to Neo4j")
        
        session = self._driver.session()
        try:
            yield session
        finally:
            session.close()
    
    def query_tool_constraints(self, tool_name: str) -> ToolConstraints:
        """
        Query constraints for a specific tool.
        
        This is the core eligibility query.
        
        Args:
            tool_name: Fully qualified tool name (e.g., "system.input.mouse.click")
            
        Returns:
            ToolConstraints with blocking and soft constraints
            
        Raises:
            Neo4jConnectionError: If Neo4j is unavailable (FAIL CLOSED)
        """
        try:
            with self.session() as session:
                result = session.run(self.CONSTRAINT_QUERY, tool_name=tool_name)
                record = result.single()
                
                if record is None:
                    # Tool not found in Neo4j
                    logging.warning(f"Tool '{tool_name}' not found in Neo4j ontology")
                    return ToolConstraints(
                        tool=tool_name,
                        blocking_constraints=[],
                        soft_constraints=[],
                        found=False
                    )
                
                # Parse blocking constraints
                blocking = []
                for c in record["blocking_constraints"]:
                    if c["name"] is not None:  # Filter out null entries
                        blocking.append(ConstraintInfo(
                            name=c["name"],
                            constraint_type=c["constraint_type"] or "unknown",
                            blocking=True,
                            resolvable=c["resolvable"] or False,
                            resolution_hint=c["resolution_hint"] or ""
                        ))
                
                # Parse soft constraints
                soft = []
                for c in record["soft_constraints"]:
                    if c["name"] is not None:
                        soft.append(ConstraintInfo(
                            name=c["name"],
                            constraint_type=c["constraint_type"] or "unknown",
                            blocking=False,
                            resolvable=c["resolvable"] or False,
                            resolution_hint=c["resolution_hint"] or ""
                        ))
                
                logging.debug(
                    f"Tool '{tool_name}': {len(blocking)} blocking, {len(soft)} soft constraints"
                )
                
                return ToolConstraints(
                    tool=tool_name,
                    blocking_constraints=blocking,
                    soft_constraints=soft,
                    found=True
                )
                
        except Neo4jConnectionError:
            raise  # Re-raise connection errors
        except Exception as e:
            logging.error(f"Neo4j query failed for '{tool_name}': {e}")
            raise Neo4jConnectionError(f"Query failed: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check Neo4j health and return status.
        
        Returns:
            Dict with connected status and any error message
        """
        try:
            if not self.is_connected:
                if not self.connect():
                    return {"connected": False, "error": "Connection failed"}
            
            # Run a simple query to verify
            with self.session() as session:
                result = session.run("RETURN 1 AS test")
                record = result.single()
                if record and record["test"] == 1:
                    return {"connected": True, "error": None}
                else:
                    return {"connected": False, "error": "Health check query failed"}
                    
        except Exception as e:
            return {"connected": False, "error": str(e)}


# Singleton instance
_client: Optional[Neo4jClient] = None


def get_neo4j_client() -> Neo4jClient:
    """
    Get the singleton Neo4j client.
    
    Returns:
        Neo4jClient instance
    """
    global _client
    if _client is None:
        _client = Neo4jClient()
    return _client


def query_tool_constraints(tool_name: str) -> ToolConstraints:
    """
    Convenience function to query tool constraints.
    
    Args:
        tool_name: Tool name to query
        
    Returns:
        ToolConstraints for the tool
        
    Raises:
        Neo4jConnectionError: If Neo4j unavailable
    """
    return get_neo4j_client().query_tool_constraints(tool_name)
