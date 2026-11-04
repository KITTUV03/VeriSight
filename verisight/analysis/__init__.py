"""Deterministic failure-analysis helpers for VeriSight.

Pure, LLM-free functions that give the pipeline an evidence-based notion of
*which* failure is causally first and *what stage* (compile / elaboration /
runtime) a run failed at. Used by the log parser and Agent 2 to stop treating
the first-printed or most-prominent message as the root cause.
"""
