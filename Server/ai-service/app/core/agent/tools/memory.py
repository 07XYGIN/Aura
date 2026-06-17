"""Memory tool module kept for compatibility.

Long-term memory persistence is handled directly in the graph flow. Keeping
this module avoids stale imports in older code paths while preventing nested
LLM calls from a save-memory tool.
"""
