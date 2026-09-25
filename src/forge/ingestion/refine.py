"""REFINE: plain-language contract generation, corrections, and signature."""

from __future__ import annotations

import hashlib

from pydantic import Field, model_validator

from forge.providers.model_provider import CallReceipt, Capability, ModelProvider
from forge.trust_kernel import ActionKind, AuthorityGrant, TrustKernel

from .decompose import Decomposition, decompose
from .models import ContractStatus, ReceiptLedger, StrictModel

JARGON_DENYLIST = frozenset({"orm", "schema", "endpoint", "multi-tenant", "microservice"})


class AcceptedAssumption(StrictModel):
    model_config = {"extra": "forbid", "frozen": True}
    id: str
    plain: str
    confidence: float = Field(ge=0, le=1)
    lineage: tuple[str, ...] = Field(min_length=1)


class OwnerSignature(StrictModel):
    model_config = {"extra": "forbid", "frozen": True}
    approved_by: str
    approved_at: str
    contract_hash: str
    receipt_hash: str


class OwnerApproval(StrictModel):
    """Owner metadata bound to the trusted AuthorityGrant receipt."""

    approved_by: str
    contract_hash: str

    @classmethod
    def issue(
        cls, contract: OwnerContract, approved_by: str, *, signing_key: bytes
    ) -> OwnerApproval:
        if not approved_by.strip() or not signing_key:
            raise ValueError("owner identity and signing key are required")
        # signing_key is retained only for source compatibility. The grant is
        # the sole cryptographic owner proof and is verified by TrustKernel.
        del signing_key
        return cls(approved_by=approved_by, contract_hash=_contract_hash(contract))

    def verify(
        self,
        contract: OwnerContract,
        authority: TrustKernel,
        grant: AuthorityGrant,
    ) -> None:
        if (
            self.contract_hash != _contract_hash(contract)
            or self.approved_by != grant.owner_ref
            or grant.scope_digest != self.contract_hash
        ):
            raise ValueError("owner approval cannot be verified for this contract")
        try:
            authority.authorize(ActionKind.ROUTINE, grant, scope_digest=self.contract_hash)
        except Exception as exc:
            raise ValueError("owner approval cannot be verified for this contract") from exc


class OwnerContract(StrictModel):
    model_config = {"extra": "forbid", "frozen": True}
    mission_id: str
    north_star_plain: str = Field(max_length=800)
    in_scope: tuple[str, ...] = Field(min_length=1)
    out_of_scope: tuple[str, ...] = Field(min_length=1)
    finish_contract_plain: str
    assumptions_accepted: tuple[AcceptedAssumption, ...]
    known_unknowns_registered: tuple[str, ...]
    polish_round: int = Field(ge=0, le=3)
    status: ContractStatus = ContractStatus.VALID
    owner_signature: OwnerSignature | None = None

    @model_validator(mode="after")
    def enforce_plain_honest_contract(self) -> OwnerContract:
        text = " ".join(
            (
                self.north_star_plain,
                *self.in_scope,
                *self.out_of_scope,
                self.finish_contract_plain,
            )
        ).lower()
        found = sorted(word for word in JARGON_DENYLIST if word in text)
        if found:
            raise ValueError(f"owner-facing contract contains jargon: {', '.join(found)}")
        if not any(
            marker in self.finish_contract_plain.lower()
            for marker in (
                "done means",
                "can ",
                "shows ",
                "when ",
                "verify",
                "check",
            )
        ):
            raise ValueError("finish contract must describe a verifiable first-version slice")
        return self


SYSTEM = """Produce a short owner contract in everyday language from the provisional outline.
Never use engineering jargon. Name both included and excluded work. The finish statement must
describe one end-to-end, observable first-version example, not the whole category product.
Preserve assumption lineage and unresolved unknown identifiers. Do not sign the contract."""


def refine(
    decomposition: Decomposition,
    provider: ModelProvider,
    *,
    correction: str | None = None,
    raw_intent: str | None = None,
    polish_round: int = 0,
    ledger: ReceiptLedger | None = None,
    packet_id: str = "FORGE-ING-001",
) -> tuple[OwnerContract, CallReceipt, Decomposition]:
    """Generate a contract; corrections re-enter DECOMPOSE, at most three times."""
    if correction:
        if polish_round >= 3:
            raise ValueError("maximum of three correction rounds reached")
        combined = f"{raw_intent or decomposition.north_star_plain}\nOwner correction: {correction}"
        decomposition, _ = decompose(combined, provider, ledger=ledger, packet_id=packet_id)
        polish_round += 1
        if ledger:
            ledger.append(
                "OWNER_CORRECTION",
                {
                    "correction": correction,
                    "round": polish_round,
                    "lineage": [raw_intent or decomposition.north_star_plain, correction],
                },
            )
    contract, receipt = provider.call(
        Capability.HIGH_REASONING,
        OwnerContract,
        SYSTEM,
        decomposition.model_dump_json(),
        caller_role="architect",
        packet_id=packet_id,
    )
    if contract.owner_signature is not None:
        raise ValueError("model cannot sign for the owner")
    if contract.polish_round != polish_round:
        contract = contract.model_copy(update={"polish_round": polish_round})
    if ledger:
        ledger.append("REFINE_COMPLETED", {"contract": contract.model_dump(mode="json")})
    return contract, receipt, decomposition


def sign_contract(
    contract: OwnerContract,
    approval: OwnerApproval,
    ledger: ReceiptLedger,
    *,
    trusted_authority: TrustKernel,
    authority_grant: AuthorityGrant,
) -> OwnerContract:
    """Record explicit owner approval and bind it to the exact unsigned contract."""
    if not isinstance(approval, OwnerApproval):
        raise ValueError("verified owner approval evidence is required")
    if contract.owner_signature:
        raise ValueError("contract is already signed")
    snapshot = OwnerContract.model_validate(contract.model_dump(mode="python"))
    approval.verify(snapshot, trusted_authority, authority_grant)
    contract_hash = _contract_hash(snapshot)
    if authority_grant.scope_digest != contract_hash:
        raise ValueError("owner approval is not bound to this contract")
    receipt = ledger.append(
        "OWNER_SIGNATURE",
        {
            **approval.model_dump(),
            "authority_grant": {
                "authority": authority_grant.authority.value,
                "action": authority_grant.action.value,
                "scope_digest": authority_grant.scope_digest,
                "owner_ref": authority_grant.owner_ref,
                "issuer_signature": authority_grant.issuer_signature,
            },
        },
    )
    signature = OwnerSignature(
        approved_by=approval.approved_by,
        approved_at=receipt.recorded_at,
        contract_hash=contract_hash,
        receipt_hash=receipt.receipt_hash,
    )
    return snapshot.model_copy(update={"owner_signature": signature})


def _contract_hash(contract: OwnerContract) -> str:
    return hashlib.sha256(
        contract.model_dump_json(exclude={"owner_signature"}).encode()
    ).hexdigest()
