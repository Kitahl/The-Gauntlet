"""Independent post-score audit for the exact HLE array item used by hard-two.

This intentionally does not import the benchmark harness or its private answer key.
It mechanically executes every answer option from the public question and checks
both the visible cells and the four declared hidden cells.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "benchmark_runs" / "2026-08-25" / "rps_v060_hle_hard_two" / "items.json"


def scale(array: list[list[str]], factor: int) -> list[list[str]]:
    return [
        [value for value in row for _ in range(factor)]
        for row in array
        for _ in range(factor)
    ]


def roll(array: list[list[str]], axis: int, amount: int) -> list[list[str]]:
    rows, cols = len(array), len(array[0])
    result = [row[:] for row in array]
    layers = min(rows, cols) // 2
    if axis == 0:
        for layer in range(layers):
            shift = (layer * amount) % rows
            for column in {layer, cols - 1 - layer}:
                for i in range(rows):
                    result[(i + shift) % rows][column] = array[i][column]
    else:
        for layer in range(layers):
            shift = (layer * amount) % cols
            for row in {layer, rows - 1 - layer}:
                for j in range(cols):
                    result[row][(j + shift) % cols] = array[row][j]
    return result


def rotate(array: list[list[str]], direction: str) -> list[list[str]]:
    if direction == "clockwise":
        return [list(row) for row in zip(*array[::-1])]
    return [list(row) for row in zip(*array)][::-1]


def flip(array: list[list[str]], direction: str) -> list[list[str]]:
    return array[::-1] if direction == "ud" else [row[::-1] for row in array]


def transpose(array: list[list[str]]) -> list[list[str]]:
    return [list(row) for row in zip(*array)]


def antidiagonal_transpose(array: list[list[str]]) -> list[list[str]]:
    # Match the reference implementation: np.rot90(tile, k=-1).T[:, ::-1].
    return [row[::-1] for row in transpose(rotate(array, "clockwise"))]


def apply_command(array: list[list[str]], command: str) -> list[list[str]]:
    parts = command.split()
    if parts[0] == "scale":
        return scale(array, int(parts[1]))
    if parts[0] == "roll":
        return roll(array, int(parts[1]), int(parts[2]))
    if parts[0] == "rotate":
        return rotate(array, parts[1])
    if parts[0] == "flip":
        return flip(array, parts[1])
    if parts[0] == "transpose":
        return transpose(array)
    if parts[0] == "antidiagonal_transpose":
        return antidiagonal_transpose(array)
    raise AssertionError(f"unknown command: {command}")


def simulate(
    initial: list[list[str]],
    commands: list[str],
    replacements: dict[str, str],
    *,
    chunk_offset: int = 0,
    row_offset: int = 0,
    sequential: bool = False,
) -> list[list[str]]:
    array = initial
    replacement_items = list(replacements.items())
    row_counter = row_offset
    for command_index, command in enumerate(commands):
        array = apply_command(array, command)
        chunk_start = ((command_index + chunk_offset) % 5) * 5
        replacement_chunk = replacement_items[chunk_start : chunk_start + 5]
        substitutions = dict(replacement_chunk)
        row_index = row_counter % len(array)
        if sequential:
            for old, new in replacement_chunk:
                array[row_index] = [new if value == old else value for value in array[row_index]]
        else:
            array[row_index] = [substitutions.get(value, value) for value in array[row_index]]
        row_counter = (row_counter + 1) % len(array)
    return array


def parse_question(question: str) -> tuple[list[list[str]], dict[str, str], list[list[str]], dict[str, tuple[list[str], dict[tuple[int, int], str]]]]:
    initial_text = re.search(r"initial_array = (\[.*?\n\])\n\nAnd given", question, re.S)
    replacements_text = re.search(r"replacements_dict = (\{.*?\})\n\nThe five", question, re.S)
    final_text = re.search(r"Below is a final array.*?\n\n(\[.*?\n\])\n\nWhich list", question, re.S)
    assert initial_text and replacements_text and final_text
    initial = ast.literal_eval(initial_text.group(1))
    replacements = ast.literal_eval(replacements_text.group(1))
    final = ast.literal_eval(final_text.group(1))

    option_blocks = re.findall(
        r"(?:^|\n)([A-F])\. (.*?)(?=\n\n[A-F]\. |\Z)", question, re.S
    )
    options: dict[str, tuple[list[str], dict[tuple[int, int], str]]] = {}
    for letter, block in option_blocks:
        command_text, hidden_text = block.split("\n\nHidden value", 1)
        commands = [part.strip() for part in command_text.split(",")]
        hidden_pairs = re.findall(
            r"(?:Hidden value)?\s*at \[\((\d+), (\d+)\)\] is: (.)", "Hidden value" + hidden_text
        )
        hidden = {(int(i), int(j)): value for i, j, value in hidden_pairs}
        options[letter] = (commands, hidden)
    assert set(options) == set("ABCDEF")
    return initial, replacements, final, options


def main() -> None:
    items = json.loads(ITEMS.read_text(encoding="utf-8"))["items"]
    question = next(item["question"] for item in items if item["category"] == "Math")
    initial, replacements, final, options = parse_question(question)

    exact_matches: list[tuple[int, int, bool, str]] = []
    best: list[tuple[int, int, int, bool, str, int, int]] = []
    for chunk_offset in range(5):
        for row_offset in range(4):
            for sequential in (False, True):
                for letter, (commands, hidden) in options.items():
                    actual = simulate(
                        initial,
                        commands,
                        replacements,
                        chunk_offset=chunk_offset,
                        row_offset=row_offset,
                        sequential=sequential,
                    )
                    visible_mismatches = sum(
                        actual[i][j] != expected
                        for i, row in enumerate(final)
                        for j, expected in enumerate(row)
                        if expected != "0"
                    )
                    hidden_mismatches = sum(
                        actual[i][j] != expected for (i, j), expected in hidden.items()
                    )
                    best.append(
                        (
                            visible_mismatches + hidden_mismatches,
                            chunk_offset,
                            row_offset,
                            sequential,
                            letter,
                            visible_mismatches,
                            hidden_mismatches,
                        )
                    )
                    if visible_mismatches == 0 and hidden_mismatches == 0:
                        exact_matches.append((chunk_offset, row_offset, sequential, letter))

    print("best interpretations:")
    for row in sorted(best)[:10]:
        print(row)
    print(f"exact_matches={exact_matches}")
    assert exact_matches == [(0, 0, True, "E")], (
        "the official sequential, first-chunk, row-zero interpretation must "
        f"uniquely identify E; got {exact_matches}"
    )
    print("PASS: the public rules mechanically and uniquely identify option E")


if __name__ == "__main__":
    main()
