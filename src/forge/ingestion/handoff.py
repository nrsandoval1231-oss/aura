"""HANDOFF: deterministic signed contract conversion for the existing loop."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from forge.execution_loop import BuildPacket
from forge.product_brain import ProductBrain
from forge.trust_kernel import ActionKind, Authority, AuthorityGrant, TrustKernel

from .models import ReceiptLedger
from .refine import OwnerApproval, OwnerContract, _contract_hash


@dataclass(frozen=True, slots=True)
class Mission:
    mission_id: str
    owner_contract: OwnerContract
    specification_hash: str
    known_unknowns: tuple[str, ...]
    build_packet: BuildPacket
    signature_receipt_hash: str


def handoff(
    contract: OwnerContract,
    product_brain: ProductBrain,
    build_packet: BuildPacket,
    ledger: ReceiptLedger,
    *,
    trusted_authority: TrustKernel,
) -> Mission:
    """Freeze identity and emit the exact BuildPacket accepted by ExecutionLoop."""
    snapshot = OwnerContract.model_validate(contract.model_dump(mode="python"))
    signature = snapshot.owner_signature
    if signature is None:
        raise ValueError("owner signature is required before handoff")
    ledger.verify()
    matching = [
        item
        for item in ledger.receipts
        if item.event == "OWNER_SIGNATURE" and item.receipt_hash == signature.receipt_hash
    ]
    if len(matching) != 1:
        raise ValueError("owner signature receipt is missing from the ledger")
    receipt = matching[0]
    approval = OwnerApproval.model_validate(
        {key: value for key, value in receipt.payload.items() if key != "authority_grant"}
    )
    try:
        grant = AuthorityGrant(
            authority=Authority(receipt.payload["authority_grant"]["authority"]),
            action=ActionKind(receipt.payload["authority_grant"]["action"]),
            scope_digest=receipt.payload["authority_grant"]["scope_digest"],
            owner_ref=receipt.payload["authority_grant"]["owner_ref"],
            issuer_signature=receipt.payload["authority_grant"]["issuer_signature"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("owner approval authority grant is malformed") from exc
    if (
        signature.contract_hash != _contract_hash(snapshot)
        or signature.contract_hash != approval.contract_hash
        or signature.approved_by != approval.approved_by
        or signature.approved_at != receipt.recorded_at
    ):
        raise ValueError("owner contract or signature fields disagree with approval receipt")
    approval.verify(snapshot, trusted_authority, grant)
    if build_packet.specification_hash != product_brain.specification_hash:
        raise ValueError("build packet is not bound to the current Product Brain")
    frozen_hash = product_brain.specification_hash
    if build_packet.base_candidate.repository_digest != trusted_authority.repository.digest:
        raise ValueError("build packet is not bound to the trusted authority repository")
    mission = Mission(
        mission_id=snapshot.mission_id,
        owner_contract=snapshot,
        specification_hash=frozen_hash,
        known_unknowns=tuple(snapshot.known_unknowns_registered),
        build_packet=build_packet,
        signature_receipt_hash=signature.receipt_hash,
    )
    ledger.append(
        "MISSION_HANDED_OFF",
        {
            "mission_id": mission.mission_id,
            "specification_hash": frozen_hash,
            "known_unknowns": list(mission.known_unknowns),
            "build_packet_digest": hashlib.sha256(repr(build_packet).encode()).hexdigest(),
            "signature_receipt_hash": signature.receipt_hash,
        },
    )
    return mission
