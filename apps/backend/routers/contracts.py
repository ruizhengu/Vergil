import uuid
import sys
import os

from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps.assistant import get_assistant

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
router = APIRouter(prefix="/api/contracts", tags=["contracts"])

class ERC20Request(BaseModel):
    name: str = "MyToken"
    symbol: str = "MTK" 
    initial_supply: int = 1000000
    decimals: int = 18
    mintable: bool = False
    burnable: bool = False
    pausable: bool = False
    ownable: bool = False

class ContractResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

@router.post("/erc20/generate", response_model=ContractResponse)
async def generate_erc20_contract(request: ERC20Request, assistant = Depends(get_assistant)):

    try:
        contract_id = uuid.uuid4().hex
        
        print(f"Backend API: Generating ERC20 contract: {request.name} ({request.symbol})")
        
        if assistant:
            # Use MCP tools for generation
            print("Backend API: Using MCP tools for contract generation")
            
            # Here you would call the MCP tool directly
            # For now, return a structured response
            response_data = {
                "contract_id": contract_id,
                "name": request.name,
                "symbol": request.symbol,
                "initial_supply": request.initial_supply,
                "decimals": request.decimals,
                "features": {
                    "mintable": request.mintable,
                    "burnable": request.burnable,
                    "pausable": request.pausable,
                    "ownable": request.ownable
                },
                "solidity_code": f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
{("import \"@openzeppelin/contracts/access/Ownable.sol\";" if request.ownable else "")}

contract {request.name.replace(' ', '')} is ERC20{(", Ownable" if request.ownable else "")} {{
    constructor() ERC20("{request.name}", "{request.symbol}") {{
        _mint(msg.sender, {request.initial_supply} * 10**decimals());
    }}
    
    {("function mint(address to, uint256 amount) public onlyOwner { _mint(to, amount); }" if request.mintable else "")}
    {("function burn(uint256 amount) public { _burn(msg.sender, amount); }" if request.burnable else "")}
}}""",
                "timestamp": datetime.now().isoformat(),
                "backend_mode": "mcp_connected"
            }
        else:
            # Fallback template generation
            print("Backend API: Using fallback template generation")
            
            response_data = {
                "contract_id": contract_id,
                "name": request.name,
                "symbol": request.symbol,
                "initial_supply": request.initial_supply,
                "decimals": request.decimals,
                "features": {
                    "mintable": request.mintable,
                    "burnable": request.burnable,
                    "pausable": request.pausable,
                    "ownable": request.ownable
                },
                "solidity_code": f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract {request.name.replace(' ', '')} is ERC20 {{
    constructor() ERC20("{request.name}", "{request.symbol}") {{
        _mint(msg.sender, {request.initial_supply} * 10**decimals());
    }}
}}""",
                "timestamp": datetime.now().isoformat(),
                "backend_mode": "fallback_template"
            }
        
        return ContractResponse(
            success=True,
            data=response_data
        )
        
    except Exception as e:
        print(f"Backend API: Error generating ERC20 contract: {e}")
        return ContractResponse(
            success=False,
            error=str(e)
        )

@router.post("/compile")
async def compile_contract(solidity_code: str, assistant = Depends(get_assistant)):
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        if not assistant:
            raise HTTPException(status_code=503, detail="MCP tools not available for compilation")
        
        # Here you would call the MCP compile tool
        compilation_id = uuid.uuid4().hex
        
        return {
            "success": True,
            "compilation_id": compilation_id,
            "message": "Contract compilation initiated",
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/templates/erc20")
async def get_erc20_template():
    """Get a basic ERC20 contract template"""
    template = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MyToken is ERC20 {
    constructor() ERC20("MyToken", "MTK") {
        _mint(msg.sender, 1000000 * 10**decimals());
    }
}"""
    
    return {
        "success": True,
        "template": template,
        "description": "Basic ERC20 token contract",
        "parameters": {
            "name": "Token name",
            "symbol": "Token symbol", 
            "initial_supply": "Initial token supply"
        }
    }

@router.get("/templates/erc721")
async def get_erc721_template():
    template = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";

contract MyNFT is ERC721 {
    uint256 private _tokenIdCounter;
    
    constructor() ERC721("MyNFT", "MNFT") {}
    
    function mint(address to) public {
        _safeMint(to, _tokenIdCounter);
        _tokenIdCounter++;
    }
}"""
    
    return {
        "success": True,
        "template": template,
        "description": "Basic ERC721 NFT contract",
        "parameters": {
            "name": "NFT collection name",
            "symbol": "NFT symbol"
        }
    }