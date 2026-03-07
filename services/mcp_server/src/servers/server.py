import asyncio
import requests
import os
import sys
import json
import solcx
import uuid
import sqlite3
from datetime import datetime
from typing import Annotated, List, Optional
from dotenv import load_dotenv
from pydantic import Field
from fastmcp import FastMCP, Client, Context
from solcx import install_solc, set_solc_version
from web3 import Web3
from fastmcp.server.middleware import Middleware, MiddlewareContext
from starlette.responses import JSONResponse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class LoggingMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        """Called for all MCP messages."""
        print(f"Processing {context.method} from {context.source}")
        
        result = await call_next(context)
        
        print(f"Completed {context.method}")
        return result

load_dotenv()

ethereum_sepolia_rpc = os.getenv('ETHEREUM_SEPOLIA_RPC')

try:
    solcx.install_solc('0.8.27')
    solcx.set_solc_version('0.8.27')
except Exception as e:
    print(f"Warning: Could not install solc: {e}")
    print("Solc will be installed on first use")

compilation_cache = {}

mcp = FastMCP(name="vergil_mcp")
mcp.add_middleware(LoggingMiddleware())

@mcp.tool(
    name="compile_contract",
    description="Compile Solidity code and return compilation ID"
)
async def compile_contract(
    solidity_code: Annotated[str, Field(
        description="Solidity source code to compile",
        min_length=1
    )]
) -> dict:
    try:
        print('here is the solidity code ', solidity_code)
        compiled = solcx.compile_source(
            solidity_code,
            output_values=["abi", "bin"],
            import_remappings=["@openzeppelin=/app/node_modules/@openzeppelin"],
            allow_paths="/app/node_modules"
        )

        # Pick the contract with the most bytecode — this is the main deployable
        # contract. Abstract contracts and interfaces have empty bytecode and would
        # be picked incorrectly by next(iter(...)) which is alphabetical order.
        contract_data = max(compiled.values(), key=lambda c: len(c.get('bin', '') or ''))
        abi = contract_data['abi']
        bytecode = contract_data['bin']
        
        compilation_id = str(uuid.uuid4())
        compilation_cache[compilation_id] = {
            "abi": abi,
            "bytecode": bytecode,
            "source_code": solidity_code
        }

        return {
            "compilation_id": compilation_id,
            "success": True,
            "abi": abi,
            "bytecode": bytecode,
            "message": "Contract compiled successfully."
        }
    except Exception as e:
        return {
            "compilation_id": None,
            "success": False,
            "message": f"Compilation failed: {str(e)}"
        }

@mcp.tool(
    name="get_abi",
    description="Get contract ABI using compilation ID"
)
async def get_abi(
    compilation_id: Annotated[str, Field(
        description="Compilation ID from compile_contract tool"
    )]
) -> dict:
    if compilation_id not in compilation_cache:
        return {
            "abi": None,
            "success": False,
            "message": "Invalid compilation ID"
        }
    
    return {
        "abi": compilation_cache[compilation_id]["abi"],
        "success": True,
        "message": "ABI retrieved successfully"
    }

@mcp.tool(
    name="get_bytecode",
    description="Get contract bytecode using compilation ID"
)
async def get_bytecode(
    compilation_id: Annotated[str, Field(
        description="Compilation ID from compile_contract tool"
    )]
) -> dict:
    if compilation_id not in compilation_cache:
        return {
            "bytecode": None,
            "success": False,
            "message": "Invalid compilation ID"
        }
    
    return {
        "bytecode": compilation_cache[compilation_id]["bytecode"],
        "success": True,
        "message": "Bytecode retrieved successfully"
    }

@mcp.tool(
    name="prepare_deployment_transaction",
    description="Prepare deployment transaction for user wallet signing"
)
async def prepare_deployment_transaction(
    compilation_id: Annotated[str, Field(
        description="Compilation ID from compile_contract tool"
    )],
    user_wallet_address: Annotated[str, Field(
        description="User's wallet address that will sign the transaction"
    )],
    gas_limit: Annotated[int, Field(
        description="Gas limit for deployment transaction",
        ge=21000, le=10000000
    )] = 2000000,
    gas_price_gwei: Annotated[int, Field(
        description="Gas price in Gwei",
        ge=1, le=1000
    )] = 10
) -> dict:
    """
    Prepares a deployment transaction that can be signed by the user's wallet.
    Returns unsigned transaction data for frontend to sign.
    """
    if compilation_id not in compilation_cache:
        return {
            "success": False,
            "message": "Invalid compilation ID",
            "transaction": None
        }

    try:
        # Reject zero/placeholder address immediately — no network calls needed
        zero_address = "0x0000000000000000000000000000000000000000"
        if not user_wallet_address or user_wallet_address.lower() == zero_address:
            return {
                "success": False,
                "message": "No wallet address provided. Please connect your wallet first before deploying.",
                "transaction": None
            }

        # Check if RPC is configured
        if not ethereum_sepolia_rpc:
            return {
                "success": False,
                "message": "Ethereum RPC URL not configured in environment variables",
                "transaction": None
            }
        
        print(f"[DEBUG] Preparing deployment transaction for user: {user_wallet_address}")
        w3 = Web3(Web3.HTTPProvider(ethereum_sepolia_rpc))
        
        # Test connection
        if not w3.is_connected():
            return {
                "success": False,
                "message": "Failed to connect to Ethereum network",
                "transaction": None
            }
        
        abi = compilation_cache[compilation_id]["abi"]
        bytecode = compilation_cache[compilation_id]["bytecode"]
        
        # Ensure user address is in proper checksum format
        user_address = w3.to_checksum_address(user_wallet_address)
        
        # Get nonce for user's address
        nonce = w3.eth.get_transaction_count(user_address)
        
        # Build constructor arguments based on ABI (same logic as deploy_contract)
        constructor_args = []
        constructor_inputs = []
        for item in abi:
            if item.get('type') == 'constructor':
                constructor_inputs = item.get('inputs', [])
                break
        
        print(f"[DEBUG] Constructor inputs: {constructor_inputs}")
        
        # Build constructor arguments based on actual ABI parameters
        if constructor_inputs:
            for input_param in constructor_inputs:
                param_name = input_param['name'].lower()
                param_type = input_param['type']
                
                print(f"[DEBUG] Processing constructor param: {param_name} ({param_type})")
                
                if param_type == 'address':
                    # Address parameters (like initialOwner)
                    if 'owner' in param_name or 'initial' in param_name:
                        constructor_args.append(user_address)
                    else:
                        constructor_args.append(user_address)  # Default to user address
                elif param_type == 'uint256':
                    # Handle uint256 parameters (like initial supply)
                    if 'supply' in param_name or 'amount' in param_name:
                        # Default initial supply if not specified otherwise
                        constructor_args.append(1000000 * 10**18)  # 1M tokens with 18 decimals
                    elif 'cap' in param_name or 'max' in param_name:
                        # Max supply cap
                        constructor_args.append(10000000 * 10**18)  # 10M tokens cap
                    else:
                        # Default uint256 value
                        constructor_args.append(0)
                elif param_type == 'string':
                    # String parameters (like token name/symbol)
                    if 'name' in param_name:
                        constructor_args.append("User Token")
                    elif 'symbol' in param_name:
                        constructor_args.append("UTK")
                    else:
                        constructor_args.append("")
                elif param_type == 'uint8':
                    # Usually decimals
                    constructor_args.append(18)
                else:
                    print(f"[WARNING] Unknown constructor parameter type: {param_type}")
                    # Try to provide a reasonable default
                    if param_type.startswith('uint'):
                        constructor_args.append(0)
                    elif param_type == 'bool':
                        constructor_args.append(False)
                    else:
                        constructor_args.append("")
        
        print(f"[DEBUG] Constructor args for user deployment: {constructor_args}")
        print(f"[DEBUG] User will be owner: {user_address}")
        
        # Create contract instance
        contract = w3.eth.contract(abi=abi, bytecode=bytecode)
        
        # Build unsigned transaction
        transaction = contract.constructor(*constructor_args).build_transaction({
            'from': user_address,
            'nonce': nonce,
            'gas': gas_limit,
            'gasPrice': w3.to_wei(gas_price_gwei, 'gwei'),
            'chainId': w3.eth.chain_id
        })
        
        # Estimate gas more accurately
        try:
            estimated_gas = w3.eth.estimate_gas(transaction)
            # Add 20% buffer to estimated gas
            recommended_gas = int(estimated_gas * 1.2)
            transaction['gas'] = recommended_gas
        except Exception as gas_error:
            print(f"[DEBUG] Gas estimation failed: {gas_error}, using provided gas_limit")
            recommended_gas = gas_limit
        
        # Cache the full prepared transaction for later retrieval via REST
        compilation_cache[compilation_id]["prepared_transaction"] = transaction

        # Convert transaction to JSON-safe dict (HexBytes/bytes aren't JSON-serializable)
        safe_transaction = {}
        for k, v in transaction.items():
            if isinstance(v, (bytes, bytearray)):
                hex_val = v.hex()
                safe_transaction[k] = hex_val if hex_val.startswith("0x") else "0x" + hex_val
            else:
                safe_transaction[k] = v

        return {
            "success": True,
            "transaction": safe_transaction,
            "compilation_id": compilation_id,
            "constructor_args": [str(a) for a in constructor_args],
            "estimated_gas": recommended_gas,
            "gas_price_gwei": gas_price_gwei,
            "chain_id": w3.eth.chain_id,
            "user_address": user_address,
            "message": "Transaction prepared for user signing"
        }
        
    except Exception as e:
        print(f"[DEBUG] Error preparing transaction: {e}")
        return {
            "success": False,
            "message": f"Transaction preparation failed: {str(e)}",
            "transaction": None
        }

@mcp.tool(
    name="broadcast_signed_transaction",
    description="Broadcast user's signed transaction to deploy contract"
)
async def broadcast_signed_transaction(
    signed_transaction_hex: Annotated[str, Field(
        description="Hex-encoded signed transaction data",
        min_length=1
    )]
) -> dict:
    """
    Broadcasts a signed transaction from the user's wallet.
    This completes the deployment process after user signing.
    """
    try:
        # Check if RPC is configured
        if not ethereum_sepolia_rpc:
            return {
                "contract_address": None,
                "transaction_hash": None,
                "success": False,
                "message": "Ethereum RPC URL not configured in environment variables"
            }
        
        print(f"[DEBUG] Broadcasting signed transaction from user wallet")
        w3 = Web3(Web3.HTTPProvider(ethereum_sepolia_rpc))
        
        # Test connection
        if not w3.is_connected():
            return {
                "contract_address": None,
                "transaction_hash": None,
                "success": False,
                "message": "Failed to connect to Ethereum network"
            }
        
        # Remove '0x' prefix if present and ensure proper format
        signed_hex = signed_transaction_hex
        if signed_hex.startswith('0x'):
            signed_hex = signed_hex[2:]
        
        # Convert hex string to bytes
        signed_transaction_bytes = bytes.fromhex(signed_hex)
        
        # Broadcast the signed transaction
        tx_hash = w3.eth.send_raw_transaction(signed_transaction_bytes)
        
        print(f"[DEBUG] Transaction broadcast, hash: {tx_hash.hex()}")
        print(f"[DEBUG] Waiting for transaction receipt...")
        
        # Wait for transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)  # 5 minute timeout
        
        print(f"[DEBUG] Transaction confirmed in block: {receipt.blockNumber}")
        print(f"[DEBUG] Contract deployed at: {receipt.contractAddress}")
        
        return {
            "contract_address": receipt.contractAddress,
            "transaction_hash": tx_hash.hex(),
            "success": True,
            "message": "Contract deployed successfully with user wallet",
            "gas_used": receipt.gasUsed,
            "block_number": receipt.blockNumber,
            "deployment_method": "user_wallet"
        }
        
    except Exception as e:
        print(f"[DEBUG] Error broadcasting transaction: {e}")
        return {
            "contract_address": None,
            "transaction_hash": None,
            "success": False,
            "message": f"Transaction broadcast failed: {str(e)}"
        }

@mcp.tool(
    name="verify_contract_code",
    description="Verify generated Solidity contract code for security and correctness using programmatic checks"
)
async def verify_contract_code(
    solidity_code: Annotated[str, Field(
        description="Solidity source code to verify",
        min_length=1
    )]
) -> dict:
    """
    Runs programmatic security and correctness checks on Solidity code.
    No LLM involved — pure regex/static analysis.
    """
    import re as _re

    issues = []
    source = solidity_code

    # 1. Pragma version check
    pragma_match = _re.search(r"pragma\s+solidity\s+[\^~>=]*\s*(0\.8)", source)
    if not pragma_match:
        issues.append("Missing or invalid pragma: expected pragma solidity ^0.8.x")

    # 2. Import validation — check @openzeppelin imports exist and paths look valid
    oz_imports = _re.findall(r'import\s+[^;]*["\'](@openzeppelin/contracts/[^"\']+)["\']', source)
    valid_oz_paths = [
        "token/ERC20", "token/ERC721", "access/Ownable", "access/AccessControl",
        "security/ReentrancyGuard", "security/Pausable", "utils/", "interfaces/",
        "token/ERC20/extensions/", "token/ERC721/extensions/",
        "governance/", "proxy/", "metatx/",
    ]
    for imp in oz_imports:
        path = imp.replace("@openzeppelin/contracts/", "")
        if not any(path.startswith(vp) for vp in valid_oz_paths):
            issues.append(f"Suspicious OpenZeppelin import path: {imp}")

    # 3. Access control check
    has_ownable = bool(_re.search(r"\bOwnable\b", source))
    has_access_control = bool(_re.search(r"\bAccessControl\b", source))
    has_only_owner = bool(_re.search(r"\bonlyOwner\b", source))
    has_access_modifier = has_ownable or has_access_control or has_only_owner

    # Check for sensitive functions without access control
    sensitive_fns = _re.findall(
        r"function\s+(mint|pause|unpause|burn|setBaseURI|withdraw|transferOwnership)\s*\([^)]*\)[^{]*\{",
        source
    )
    if sensitive_fns and not has_access_modifier:
        issues.append(
            f"Sensitive functions found ({', '.join(sensitive_fns)}) but no access control "
            f"(Ownable/AccessControl/onlyOwner) detected"
        )

    # 4. Require checks
    has_require = "require(" in source
    has_custom_errors = bool(_re.search(r"\berror\s+\w+\s*\(", source))
    has_revert = bool(_re.search(r"\brevert\s+\w+\s*\(", source))
    if not (has_require or has_custom_errors or has_revert):
        issues.append("No require() checks or custom errors found — input validation may be missing")

    # 5. Reentrancy check
    has_external_call = bool(_re.search(r"\.call\s*\{", source))
    has_reentrancy_guard = bool(_re.search(r"\bReentrancyGuard\b", source))
    has_nonreentrant = bool(_re.search(r"\bnonReentrant\b", source))
    if has_external_call and not (has_reentrancy_guard or has_nonreentrant):
        issues.append(
            "External .call{} detected without ReentrancyGuard — potential reentrancy vulnerability"
        )

    # 6. Event emissions
    has_emit = bool(_re.search(r"\bemit\s+\w+", source))
    if not has_emit:
        issues.append("No event emissions found — state changes should emit events")

    # 7. Constructor check
    has_constructor = bool(_re.search(r"\bconstructor\s*\(", source))
    if not has_constructor:
        issues.append("No constructor found — contract may not initialize properly")

    # 8. Extract function names (contract facts)
    function_names = _re.findall(r"function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source)
    has_transfer_fn = "transfer" in function_names

    # Determine risk level and pass/fail
    critical_keywords = [
        "reentrancy", "access control", "pragma", "constructor",
    ]
    critical_issues = [i for i in issues if any(k in i.lower() for k in critical_keywords)]

    if not issues:
        risk_level = "low"
        pass_verification = True
        summary = "All programmatic checks passed. Contract follows expected patterns."
    elif not critical_issues:
        risk_level = "medium"
        pass_verification = True
        summary = f"Minor issues found ({len(issues)}), but no critical problems."
    else:
        risk_level = "high"
        pass_verification = False
        summary = f"Critical issues found ({len(critical_issues)} critical, {len(issues)} total). Contract should be regenerated."

    return {
        "pass_verification": pass_verification,
        "risk_level": risk_level,
        "issues": issues,
        "contract_facts": {
            "functions": function_names,
            "has_transfer_function": has_transfer_fn,
            "has_access_control": has_access_modifier,
            "has_require_checks": has_require,
            "has_reentrancy_guard": has_reentrancy_guard or has_nonreentrant,
            "has_events": has_emit,
            "has_constructor": has_constructor,
            "openzeppelin_imports": oz_imports,
        },
        "summary": summary,
    }


def _convert_arg(value: str, abi_type: str):
    """Convert string argument to appropriate Python type based on Solidity ABI type."""
    try:
        if abi_type == "address":
            return Web3.to_checksum_address(value)
        elif abi_type.startswith("uint") or abi_type.startswith("int"):
            return int(value)
        elif abi_type == "bool":
            return value.lower() in ("true", "1", "yes")
        elif abi_type == "string":
            return value
        elif abi_type.startswith("bytes"):
            if value.startswith("0x"):
                return bytes.fromhex(value[2:])
            return value.encode()
        else:
            try:
                return int(value)
            except ValueError:
                return value
    except Exception:
        return value


def _build_converted_args(abi, function_name: str, function_args: list) -> list:
    """Convert string arguments to proper Python types based on ABI function inputs."""
    func_abi = next(
        (f for f in abi if f.get("type") == "function" and f.get("name") == function_name),
        None
    )
    if not func_abi or not function_args:
        return function_args
    inputs = func_abi.get("inputs", [])
    converted = []
    for i, arg in enumerate(function_args):
        if i < len(inputs):
            converted.append(_convert_arg(arg, inputs[i]["type"]))
        else:
            converted.append(arg)
    return converted


@mcp.tool(
    name="call_contract_function",
    description="Call a read-only (view/pure) contract function using eth_call — no gas, no signing required"
)
async def call_contract_function(
    contract_address: Annotated[str, Field(
        description="Deployed contract address"
    )],
    abi_json: Annotated[str, Field(
        description="Contract ABI as a JSON string"
    )],
    function_name: Annotated[str, Field(
        description="Name of the function to call"
    )],
    function_args: Annotated[Optional[str], Field(
        description="Function arguments as a JSON array string, e.g. '[\"0xAddress\", \"100\"]'"
    )] = None,
) -> dict:
    """Call a read-only contract function. Returns the result without any transaction."""
    try:
        if not ethereum_sepolia_rpc:
            return {"success": False, "message": "Ethereum RPC URL not configured"}

        w3 = Web3(Web3.HTTPProvider(ethereum_sepolia_rpc))
        if not w3.is_connected():
            return {"success": False, "message": "Failed to connect to Ethereum network"}

        abi = json.loads(abi_json)
        address = w3.to_checksum_address(contract_address)
        contract = w3.eth.contract(address=address, abi=abi)

        args: list = []
        if function_args:
            if isinstance(function_args, list):
                args = function_args
            else:
                try:
                    parsed = json.loads(function_args)
                    args = parsed if isinstance(parsed, list) else [str(parsed)]
                except json.JSONDecodeError:
                    args = [function_args]
        converted_args = _build_converted_args(abi, function_name, args)
        print(f"[MCP] call_contract_function: {function_name}({converted_args}) on {address}")

        result = contract.functions[function_name](*converted_args).call()

        # Serialize result
        if isinstance(result, (bytes, bytearray)):
            result_str = "0x" + result.hex()
        elif isinstance(result, (list, tuple)):
            result_str = str([str(r) for r in result])
        else:
            result_str = str(result)

        return {
            "success": True,
            "function_name": function_name,
            "return_value": result_str,
            "message": f"Called {function_name} successfully"
        }
    except Exception as e:
        print(f"[MCP] call_contract_function error: {e}")
        return {"success": False, "message": f"Contract call failed: {str(e)}"}


@mcp.tool(
    name="prepare_contract_call_transaction",
    description="Prepare an unsigned transaction for a state-changing contract function call, for user wallet signing"
)
async def prepare_contract_call_transaction(
    contract_address: Annotated[str, Field(
        description="Deployed contract address"
    )],
    abi_json: Annotated[str, Field(
        description="Contract ABI as a JSON string"
    )],
    function_name: Annotated[str, Field(
        description="Name of the function to call"
    )],
    function_args: Annotated[Optional[str], Field(
        description="Function arguments as a JSON array string, e.g. '[\"0xAddress\", \"100\"]'"
    )] = None,
    user_wallet_address: Annotated[str, Field(
        description="User's wallet address that will sign the transaction"
    )] = "",
    value_wei: Annotated[int, Field(
        description="ETH value in wei to send with the call (for payable functions)",
        ge=0
    )] = 0,
) -> dict:
    """Prepare an unsigned transaction for a contract function call. Returns a call_id for retrieval."""
    try:
        if not ethereum_sepolia_rpc:
            return {"success": False, "message": "Ethereum RPC URL not configured"}

        w3 = Web3(Web3.HTTPProvider(ethereum_sepolia_rpc))
        if not w3.is_connected():
            return {"success": False, "message": "Failed to connect to Ethereum network"}

        abi = json.loads(abi_json)
        address = w3.to_checksum_address(contract_address)
        contract = w3.eth.contract(address=address, abi=abi)

        user_address = w3.to_checksum_address(user_wallet_address) if user_wallet_address else None
        if not user_address:
            return {"success": False, "message": "user_wallet_address is required for write calls"}

        args: list = []
        if function_args:
            if isinstance(function_args, list):
                args = function_args
            else:
                try:
                    parsed = json.loads(function_args)
                    args = parsed if isinstance(parsed, list) else [str(parsed)]
                except json.JSONDecodeError:
                    args = [function_args]
        converted_args = _build_converted_args(abi, function_name, args)
        print(f"[MCP] prepare_contract_call_transaction: {function_name}({converted_args}) on {address}")

        nonce = w3.eth.get_transaction_count(user_address)

        tx_params = {
            "from": user_address,
            "nonce": nonce,
            "value": value_wei,
            "chainId": w3.eth.chain_id,
        }
        transaction = contract.functions[function_name](*converted_args).build_transaction(tx_params)

        # Estimate gas
        try:
            estimated_gas = w3.eth.estimate_gas(transaction)
            transaction["gas"] = int(estimated_gas * 1.2)
        except Exception as gas_err:
            print(f"[MCP] Gas estimation failed: {gas_err}")
            transaction["gas"] = 200000

        # Cache the full transaction for REST retrieval
        call_id = str(uuid.uuid4())
        compilation_cache[f"call_{call_id}"] = {"prepared_call": transaction}

        # Build safe metadata (no large data field) for LLM
        safe_tx_meta = {
            "gas": transaction.get("gas"),
            "gasPrice": str(transaction.get("gasPrice", 0)),
            "chainId": transaction.get("chainId"),
            "from": transaction.get("from"),
            "to": transaction.get("to"),
            "nonce": transaction.get("nonce"),
            "value": str(transaction.get("value", 0)),
        }

        return {
            "success": True,
            "call_id": call_id,
            "transaction": safe_tx_meta,
            "estimated_gas": transaction.get("gas"),
            "chain_id": w3.eth.chain_id,
            "user_address": user_address,
            "message": f"Transaction prepared for {function_name} — ready for wallet signing"
        }
    except Exception as e:
        print(f"[MCP] prepare_contract_call_transaction error: {e}")
        return {"success": False, "message": f"Transaction preparation failed: {str(e)}"}


@mcp.custom_route("/api/call/{call_id}", methods=["GET"])
async def get_cached_call(request):
    """Return the full prepared contract call transaction (with encoded data) for a call ID."""
    call_id = request.path_params["call_id"]
    cached = compilation_cache.get(f"call_{call_id}", {})
    tx = cached.get("prepared_call")
    if not tx:
        return JSONResponse({"success": False, "error": "Call transaction not found"}, status_code=404)
    safe_tx = {}
    for k, v in tx.items():
        if isinstance(v, (bytes, bytearray)):
            hex_val = v.hex()
            safe_tx[k] = hex_val if hex_val.startswith("0x") else "0x" + hex_val
        elif isinstance(v, (str, int, float, bool, type(None))):
            safe_tx[k] = v
        else:
            safe_tx[k] = str(v)
    return JSONResponse({"success": True, "transaction": safe_tx})


@mcp.custom_route("/api/transaction/{compilation_id}", methods=["GET"])
async def get_cached_transaction(request):
    """Return the full prepared transaction (with bytecode) for a compilation ID."""
    compilation_id = request.path_params["compilation_id"]
    cached = compilation_cache.get(compilation_id, {})
    tx = cached.get("prepared_transaction")
    if not tx:
        return JSONResponse({"success": False, "error": "Transaction not found"}, status_code=404)
    # Convert non-serializable types (HexBytes, bytes, etc.) to hex strings
    serializable_tx = {}
    for k, v in tx.items():
        # Skip 'to' for contract deployments (empty/None → omit entirely)
        if k == "to" and (v is None or v == "" or v == b"" or str(v) == "0x"):
            continue
        if isinstance(v, (bytes, bytearray)):
            hex_val = v.hex()
            serializable_tx[k] = hex_val if hex_val.startswith("0x") else "0x" + hex_val
        elif isinstance(v, (str, int, float, bool, type(None))):
            serializable_tx[k] = v
        else:
            serializable_tx[k] = str(v)
    return JSONResponse({"success": True, "transaction": serializable_tx})


@mcp.custom_route("/api/compilation/{compilation_id}", methods=["GET"])
async def get_cached_compilation(request):
    """Return cached compilation data (abi, bytecode, source_code) for a compilation ID."""
    compilation_id = request.path_params["compilation_id"]
    cached = compilation_cache.get(compilation_id)
    if not cached:
        return JSONResponse({"success": False, "error": "Compilation not found"}, status_code=404)
    return JSONResponse({
        "success": True,
        "abi": cached.get("abi"),
        "bytecode": cached.get("bytecode"),
        "source_code": cached.get("source_code"),
    })


if __name__ == '__main__':
    import os
    port = int(os.getenv("PORT", 8081))
    mcp.run(transport="http", host="0.0.0.0", port=port)
