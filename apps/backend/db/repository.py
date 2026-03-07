import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from db.models import Contract, Compilation, Deployment


def save_contract(
    session: Session,
    conversation_id: str,
    contract_name: str,
    solidity_code: str,
    contract_type: Optional[str] = None,
    parameters: Optional[dict] = None,
) -> Contract:
    contract = Contract(
        id=uuid.uuid4().hex,
        conversation_id=conversation_id,
        contract_name=contract_name,
        contract_type=contract_type,
        solidity_code=solidity_code,
        parameters=parameters,
    )
    session.add(contract)
    session.commit()
    session.refresh(contract)
    return contract


def save_compilation(
    session: Session,
    compilation_id: str,
    contract_id: Optional[str] = None,
    abi: Optional[dict] = None,
    bytecode: Optional[str] = None,
    success: bool = False,
    errors: Optional[dict] = None,
) -> Compilation:
    compilation = Compilation(
        id=uuid.uuid4().hex,
        contract_id=contract_id,
        compilation_id=compilation_id,
        abi=abi,
        bytecode=bytecode,
        success=success,
        errors=errors,
    )
    session.add(compilation)
    session.commit()
    session.refresh(compilation)
    return compilation


def save_deployment(
    session: Session,
    compilation_id_ref: Optional[str] = None,
    transaction_hash: Optional[str] = None,
    contract_address: Optional[str] = None,
    deployer_address: Optional[str] = None,
    chain_id: int = 11155111,
    status: str = "pending",
    gas_used: Optional[int] = None,
) -> Deployment:
    deployment = Deployment(
        id=uuid.uuid4().hex,
        compilation_id_ref=compilation_id_ref,
        transaction_hash=transaction_hash,
        contract_address=contract_address,
        deployer_address=deployer_address,
        chain_id=chain_id,
        status=status,
        gas_used=gas_used,
    )
    session.add(deployment)
    session.commit()
    session.refresh(deployment)
    return deployment


def get_contract(session: Session, contract_id: str) -> Optional[Contract]:
    return session.query(Contract).filter(Contract.id == contract_id).first()


def get_compilation_by_mcp_id(session: Session, compilation_id: str) -> Optional[Compilation]:
    return session.query(Compilation).filter(Compilation.compilation_id == compilation_id).first()


def get_contracts_by_conversation(session: Session, conversation_id: str) -> List[Contract]:
    return (
        session.query(Contract)
        .filter(Contract.conversation_id == conversation_id)
        .order_by(Contract.created_at.desc())
        .all()
    )


def get_compilations_by_contract(session: Session, contract_id: str) -> List[Compilation]:
    return (
        session.query(Compilation)
        .filter(Compilation.contract_id == contract_id)
        .order_by(Compilation.created_at.desc())
        .all()
    )


def get_deployments_by_conversation(
    session: Session,
    conversation_id: str,
    deployer_address: Optional[str] = None,
) -> list:
    """
    Return list of deployed contract info for a given conversation.
    Primary path: contracts (conversation_id) → compilations → deployments.
    Fallback path: if the primary path finds nothing (no Contract row saved),
    query deployments directly by deployer_address.
    """
    contracts = (
        session.query(Contract)
        .filter(Contract.conversation_id == conversation_id)
        .all()
    )
    results = []
    seen_addresses: set = set()

    for contract in contracts:
        for compilation in contract.compilations:
            if not compilation.abi:
                continue
            for deployment in compilation.deployments:
                if deployment.contract_address and deployment.status == "deployed":
                    seen_addresses.add(deployment.contract_address)
                    results.append({
                        "contract_name": contract.contract_name,
                        "contract_type": contract.contract_type,
                        "contract_address": deployment.contract_address,
                        "compilation_id": compilation.compilation_id,
                        "abi": compilation.abi,
                    })

    # Fallback: no Contract row exists for this conversation (e.g. deploy-only flow).
    # Query deployments directly by deployer_address.
    if not results and deployer_address:
        deployments = (
            session.query(Deployment)
            .filter(
                Deployment.deployer_address == deployer_address,
                Deployment.contract_address.isnot(None),
                Deployment.status == "deployed",
            )
            .order_by(Deployment.created_at.desc())
            .all()
        )
        for dep in deployments:
            if dep.contract_address in seen_addresses:
                continue
            comp = dep.compilation
            if comp and comp.abi:
                contract_name = comp.contract.contract_name if comp.contract else "Contract"
                contract_type = comp.contract.contract_type if comp.contract else None
                results.append({
                    "contract_name": contract_name,
                    "contract_type": contract_type,
                    "contract_address": dep.contract_address,
                    "compilation_id": comp.compilation_id,
                    "abi": comp.abi,
                })

    return results


def get_deployments_by_compilation(session: Session, compilation_id_ref: str) -> List[Deployment]:
    return (
        session.query(Deployment)
        .filter(Deployment.compilation_id_ref == compilation_id_ref)
        .order_by(Deployment.created_at.desc())
        .all()
    )
