#!/usr/bin/env python3
"""CI wrapper for canonical BBEH family identifiers."""
import build_package as bp

bp.FORMAL_FAMILIES = [
    "bbeh_boolean_expressions",
    "bbeh_boardgame_qa",
    "bbeh_causal_understanding",
    "bbeh_dyck_languages",
    "bbeh_multistep_arithmetic",
    "bbeh_temporal_sequence",
    "bbeh_web_of_lies",
    "bbeh_zebra_puzzles",
    "bbeh_buggy_tables",
    "bbeh_spatial_reasoning",
]

import validate_package as validator
validator.bp.FORMAL_FAMILIES = bp.FORMAL_FAMILIES

if __name__ == "__main__":
    validator.main()
