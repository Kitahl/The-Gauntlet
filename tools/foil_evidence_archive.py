"""Content-addressed raw evidence archive for FOIL v2.

Public tool/evidence traces intentionally contain digests.  This archive is the
separate, explicit boundary that persists the fetched passages needed to audit
those digests.  Files are written atomically before a runtime may report success.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from egrt_types import digest
from foil_tool_contract_v2 import ToolContractV2, ToolReceiptV2


@dataclass(frozen=True)
class EvidenceArchiveReceipt:
    archive_id: str
    path: str
    payload_digest: str
    contract_digest: str
    tool_receipt_digest: str
    raw_passages: int

    def trace(self) -> dict[str, object]:
        return {
            "schema": "foil.raw-evidence-archive-receipt.v1",
            "archive_id": self.archive_id,
            "path": self.path,
            "payload_sha256": self.payload_digest,
            "contract_sha256": self.contract_digest,
            "tool_receipt_sha256": self.tool_receipt_digest,
            "raw_passages": self.raw_passages,
            "raw_evidence_stored": True,
        }


class RawEvidenceArchive:
    def __init__(self, root: Path):
        if not isinstance(root, Path):
            raise TypeError("root must be pathlib.Path")
        self.root = root.resolve()

    def store(
        self,
        contract: ToolContractV2,
        receipt: ToolReceiptV2,
    ) -> EvidenceArchiveReceipt:
        if not isinstance(contract, ToolContractV2):
            raise TypeError("contract must be ToolContractV2")
        if not isinstance(receipt, ToolReceiptV2):
            raise TypeError("receipt must be ToolReceiptV2")
        receipt.validate_against(contract)
        public = receipt.trace(include_raw=False)
        raw = receipt.trace(include_raw=True)
        payload: dict[str, object] = {
            "schema": "foil.raw-evidence-archive.v1",
            "contract": contract.trace(),
            "public_receipt_sha256": public["receipt_sha256"],
            "raw_receipt": raw,
        }
        payload["payload_sha256"] = digest(payload)
        archive_id = f"evidence-{contract.contract_digest[:16]}-{str(raw['receipt_sha256'])[:16]}"
        target = (self.root / f"{archive_id}.json").resolve()
        if target.parent != self.root:
            raise ValueError("archive target escaped root")
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.root / f".{archive_id}.{os.getpid()}.tmp"
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2)
        try:
            temporary.write_text(encoded, encoding="utf-8")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        loaded = json.loads(target.read_text(encoding="utf-8"))
        supplied = loaded.pop("payload_sha256")
        if supplied != digest(loaded):
            raise OSError("evidence archive verification failed after persistence")
        loaded["payload_sha256"] = supplied
        return EvidenceArchiveReceipt(
            archive_id,
            str(target),
            str(payload["payload_sha256"]),
            contract.contract_digest,
            str(public["receipt_sha256"]),
            len(receipt.passages),
        )

    @staticmethod
    def verify(receipt: EvidenceArchiveReceipt) -> None:
        if not isinstance(receipt, EvidenceArchiveReceipt):
            raise TypeError("receipt must be EvidenceArchiveReceipt")
        path = Path(receipt.path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        supplied = payload.pop("payload_sha256", None)
        if supplied != receipt.payload_digest or supplied != digest(payload):
            raise ValueError("raw evidence archive digest mismatch")
        contract = payload.get("contract")
        if not isinstance(contract, dict) or contract.get("contract_sha256") != receipt.contract_digest:
            raise ValueError("raw evidence archive contract mismatch")
        raw = payload.get("raw_receipt")
        if not isinstance(raw, dict) or raw.get("raw_evidence_stored") is not bool(raw.get("passages")):
            raise ValueError("raw evidence archive storage marker mismatch")
