from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from db import repository as db_repo

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/contracts/{conversation_id}")
def list_contracts(conversation_id: str, db: Session = Depends(get_db)):
    """List all contracts saved for a conversation."""
    contracts = db_repo.get_contracts_by_conversation(db, conversation_id)
    return {
        "success": True,
        "contracts": [
            {
                "id": c.id,
                "conversation_id": c.conversation_id,
                "contract_name": c.contract_name,
                "contract_type": c.contract_type,
                "solidity_code": c.solidity_code,
                "parameters": c.parameters,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in contracts
        ],
    }


@router.get("/compilations/{compilation_id}")
def get_compilation(compilation_id: str, db: Session = Depends(get_db)):
    """Get a compilation by its MCP compilation ID."""
    comp = db_repo.get_compilation_by_mcp_id(db, compilation_id)
    if not comp:
        return {"success": False, "error": "Compilation not found"}
    return {
        "success": True,
        "compilation": {
            "id": comp.id,
            "contract_id": comp.contract_id,
            "compilation_id": comp.compilation_id,
            "abi": comp.abi,
            "bytecode": comp.bytecode,
            "success": comp.success,
            "errors": comp.errors,
            "created_at": comp.created_at.isoformat() if comp.created_at else None,
        },
    }


@router.get("/deployments/{conversation_id}")
def list_deployments(conversation_id: str, db: Session = Depends(get_db)):
    """List deployments related to a conversation (via contracts → compilations → deployments)."""
    contracts = db_repo.get_contracts_by_conversation(db, conversation_id)
    deployments = []
    for contract in contracts:
        compilations = db_repo.get_compilations_by_contract(db, contract.id)
        for comp in compilations:
            deps = db_repo.get_deployments_by_compilation(db, comp.id)
            for d in deps:
                deployments.append(
                    {
                        "id": d.id,
                        "compilation_id_ref": d.compilation_id_ref,
                        "transaction_hash": d.transaction_hash,
                        "contract_address": d.contract_address,
                        "chain_id": d.chain_id,
                        "deployer_address": d.deployer_address,
                        "status": d.status,
                        "gas_used": d.gas_used,
                        "created_at": d.created_at.isoformat() if d.created_at else None,
                    }
                )
    return {"success": True, "deployments": deployments}
