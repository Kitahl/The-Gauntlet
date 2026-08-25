"""Versioned, deterministic mutation operators for the FOIL R1.6 pilot.

The operators consume only a question and a gold *solution artifact* while the
mutation set is constructed.  They never invoke FOIL.  Scanner execution happens
later, after the operator rows and their digests have been frozen.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Callable

import foil_r16_no_oracle_discovery_pilot as protocol


def _plus_one(value: str) -> str:
    return protocol._canonical_number(Fraction(value) + 1)


def _render(answer: str, rows: list[protocol.Annotation], final: str) -> str:
    rendered = answer
    matches = list(protocol.ANNOTATION_RE.finditer(rendered))
    if len(matches) != len(rows):
        raise ValueError("annotation count changed before rendering")
    for match, row in reversed(list(zip(matches, rows, strict=True))):
        token = f"<<{row.expression}={row.result}>>{row.result}"
        rendered = rendered[: match.start()] + token + rendered[match.end() :]
    return protocol._replace_final(rendered, final)


def _replace_values(expression: str, replacements: dict[str, str]) -> str:
    changed = expression
    for source, target in replacements.items():
        try:
            changed = protocol._replace_number_token(
                changed, source, target, first_only=False
            )
        except ValueError:
            continue
    return changed


def _prompt_numbers(question: str) -> tuple[str, ...]:
    seen: list[str] = []
    for match in protocol.EXPR_NUMBER_RE.finditer(question):
        try:
            value = protocol._canonical_number(match.group(0))
        except (ValueError, ZeroDivisionError):
            continue
        if value not in seen:
            seen.append(value)
    return tuple(seen)


def _attempt(
    question_sha256: str,
    operator_id: str,
    original: str,
    builder: Callable[[], str],
) -> protocol.MutationAttempt:
    label = protocol.OPERATOR_TO_LABEL[operator_id]
    try:
        mutant = builder()
    except LookupError as exc:
        return protocol.MutationAttempt(
            question_sha256,
            operator_id,
            label,
            "UNSUPPORTED",
            protocol.sha256_text(original),
            None,
            None,
            str(exc) or "operator prerequisite absent",
        )
    except (ArithmeticError, SyntaxError, TypeError, ValueError) as exc:
        return protocol.MutationAttempt(
            question_sha256,
            operator_id,
            label,
            "INVALID",
            protocol.sha256_text(original),
            None,
            None,
            f"{type(exc).__name__}:{exc}",
        )
    if mutant == original:
        return protocol.MutationAttempt(
            question_sha256,
            operator_id,
            label,
            "EQUIVALENT",
            protocol.sha256_text(original),
            protocol.sha256_text(mutant),
            None,
            "rendered mutation is byte-identical",
        )
    return protocol.MutationAttempt(
        question_sha256,
        operator_id,
        label,
        "EXECUTED",
        protocol.sha256_text(original),
        protocol.sha256_text(mutant),
        mutant,
        "operator prerequisites and non-equivalence checks passed",
    )


def _result_corruption(answer: str) -> str:
    rows = list(protocol.parse_annotations(answer))
    if not rows:
        raise LookupError("no arithmetic annotation")
    rows[0] = replace(rows[0], result=_plus_one(rows[0].result))
    final = protocol.final_value(answer)
    if final is None:
        raise LookupError("final A: value absent")
    return _render(answer, rows, final)


def _final_corruption(answer: str) -> str:
    final = protocol.final_value(answer)
    if final is None:
        raise LookupError("final A: value absent")
    return protocol._replace_final(answer, _plus_one(final))


def _operand_corruption(answer: str) -> str:
    rows = list(protocol.parse_annotations(answer))
    for index, row in enumerate(rows):
        operands = protocol.expression_numbers(row.expression)
        if operands:
            expression = protocol._replace_number_token(
                row.expression, operands[0], _plus_one(operands[0]), first_only=True
            )
            rows[index] = replace(row, expression=expression)
            final = protocol.final_value(answer)
            if final is None:
                raise LookupError("final A: value absent")
            return _render(answer, rows, final)
    raise LookupError("no literal operand")


def _swap_operator(answer: str) -> str:
    rows = list(protocol.parse_annotations(answer))
    for index, row in enumerate(rows):
        changed = protocol._different_operator(row.expression)
        if changed is not None:
            rows[index] = replace(row, expression=changed[0])
            final = protocol.final_value(answer)
            if final is None:
                raise LookupError("final A: value absent")
            return _render(answer, rows, final)
    raise LookupError("no supported binary operator")


def _consistent_local(answer: str) -> str:
    rows = list(protocol.parse_annotations(answer))
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        changed = protocol._different_operator(row.expression)
        if changed is None:
            continue
        new_result = protocol.evaluate_expression(changed[0])
        if new_result == row.result:
            continue
        rows[index] = replace(row, expression=changed[0], result=new_result)
        if index != len(rows) - 1:
            raise LookupError("last changed annotation is not the final dependency")
        return _render(answer, rows, new_result)
    raise LookupError("no non-equivalent final binary rewrite")


def _drop_step(answer: str) -> str:
    original_rows = list(protocol.parse_annotations(answer))
    if len(original_rows) < 3:
        raise LookupError("fewer than three annotations")
    for drop_index, dropped in enumerate(original_rows[:-1]):
        inputs = protocol.expression_numbers(dropped.expression)
        if not inputs:
            continue
        used_later = any(
            dropped.result in protocol.expression_numbers(row.expression)
            for row in original_rows[drop_index + 1 :]
        )
        if not used_later:
            continue
        replacements = {dropped.result: inputs[0]}
        rebuilt: list[protocol.Annotation] = []
        for index, row in enumerate(original_rows):
            if index == drop_index:
                continue
            expression = _replace_values(row.expression, replacements)
            result = protocol.evaluate_expression(expression)
            replacements[row.result] = result
            rebuilt.append(replace(row, expression=expression, result=result))
        rendered = answer
        matches = list(protocol.ANNOTATION_RE.finditer(rendered))
        rendered = rendered[: matches[drop_index].start()] + rendered[matches[drop_index].end() :]
        return _render(rendered, rebuilt, rebuilt[-1].result)
    raise LookupError("no contributing annotation suitable for deterministic bypass")


def _consistent_global(question: str, answer: str) -> str:
    rows = list(protocol.parse_annotations(answer))
    if len(rows) < 3:
        raise LookupError("fewer than three annotations")
    prompt_values = _prompt_numbers(question)
    used = {
        item
        for row in rows
        for item in protocol.expression_numbers(row.expression)
    }
    source = next((value for value in prompt_values if value in used), None)
    if source is None:
        raise LookupError("no prompt-derived root used by annotations")
    target = next((value for value in prompt_values if value != source), None)
    if target is None:
        raise LookupError("no distinct replacement prompt quantity")
    replacements = {source: target}
    rebuilt: list[protocol.Annotation] = []
    for row in rows:
        expression = _replace_values(row.expression, replacements)
        result = protocol.evaluate_expression(expression)
        replacements[row.result] = result
        rebuilt.append(replace(row, expression=expression, result=result))
    if rebuilt[-1].result == rows[-1].result:
        raise LookupError("global rewrite leaves final result equivalent")
    return _render(answer, rebuilt, rebuilt[-1].result)


def mutate(
    question_sha256: str,
    question: str,
    answer: str,
    operator_id: str,
) -> protocol.MutationAttempt:
    """Attempt exactly one frozen operator and retain its denominator status."""

    if operator_id not in protocol.OPERATORS:
        raise ValueError("unknown R1.6 operator")
    builders: dict[str, Callable[[], str]] = {
        "M1_RESULT": lambda: _result_corruption(answer),
        "M2_FINAL": lambda: _final_corruption(answer),
        "M3_OPERAND": lambda: _operand_corruption(answer),
        "M4_DROPSTEP": lambda: _drop_step(answer),
        "M5_SWAPOP": lambda: _swap_operator(answer),
        "M7_CONSISTENT": lambda: _consistent_local(answer),
        "M9_CONSISTENT_BIG": lambda: _consistent_global(question, answer),
    }
    return _attempt(question_sha256, operator_id, answer, builders[operator_id])


def attempt_all(
    question_sha256: str, question: str, answer: str
) -> tuple[protocol.MutationAttempt, ...]:
    return tuple(mutate(question_sha256, question, answer, item) for item in protocol.OPERATORS)


def conservation(attempts: tuple[protocol.MutationAttempt, ...]) -> dict[str, object]:
    by_status = {
        status: sum(item.status == status for item in attempts)
        for status in protocol.ATTEMPT_STATUSES
    }
    by_operator: dict[str, dict[str, int]] = {}
    for operator in protocol.OPERATORS:
        rows = tuple(item for item in attempts if item.operator_id == operator)
        counts = {
            status: sum(item.status == status for item in rows)
            for status in protocol.ATTEMPT_STATUSES
        }
        counts["attempted"] = len(rows)
        counts["conserved"] = int(len(rows) == sum(counts[s] for s in protocol.ATTEMPT_STATUSES))
        by_operator[operator] = counts
    return {
        "attempted": len(attempts),
        "by_status": by_status,
        "conserved": len(attempts) == sum(by_status.values()),
        "by_operator": by_operator,
    }
