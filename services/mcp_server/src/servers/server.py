import asyncio
import requests
import os
import sys
import json
import solcx
import uuid
import sqlite3
from datetime import datetime
from typing import Annotated
from dotenv import load_dotenv
from pydantic import Field
from fastmcp import FastMCP, Client, Context
from jinja2 import Environment, FileSystemLoader
from solcx import install_solc, set_solc_version
from web3 import Web3
from fastmcp.server.middleware import Middleware, MiddlewareContext

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class LoggingMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        """Called for all MCP messages."""
        print(f"Processing {context.method} from {context.source}")
        
        result = await call_next(context)
        
        print(f"Completed {context.method}")
        return result

load_dotenv()

private_key = os.getenv('METAMASK_PRIVATE_KEY')
ethereum_sepolia_rpc = os.getenv('ETHEREUM_SEPOLIA_RPC')

solcx.install_solc('0.8.27')
solcx.set_solc_version('0.8.27')

compilation_cache = {}

mcp = FastMCP(name="crypto_mcp", log_level="DEBUG")
mcp.add_middleware(LoggingMiddleware())

@mcp.tool(
    name="generate_erc20_contract",
    description="Generate an ERC20 token contract with advanced features"
)
async def generate_erc20_contract(
    contract_name: Annotated[str, Field(
        description="Name of the contract class (e.g., 'MyToken')",
        min_length=1, max_length=50
    )],
    token_name: Annotated[str, Field(
        description="Display name of the token (e.g., 'My Token')", 
        min_length=1, max_length=100
    )],
    token_symbol: Annotated[str, Field(
        description="Token symbol (3-10 characters, uppercase recommended)",
        min_length=1, max_length=10
    )],
    initial_supply: Annotated[int, Field(
        description="Initial token supply (0 for no initial mint)",
        ge=0
    )] = 0,
    decimals: Annotated[int, Field(
        description="Number of decimal places (typically 18)",
        ge=0, le=77
    )] = 18,
    mintable: Annotated[bool, Field(
        description="Enable minting capability (requires ownable)"
    )] = False,
    burnable: Annotated[bool, Field(
        description="Enable burning capability"
    )] = False,
    pausable: Annotated[bool, Field(
        description="Enable pause functionality (requires ownable)"
    )] = False,
    permit: Annotated[bool, Field(
        description="Enable EIP-2612 permit functionality"
    )] = False,
    ownable: Annotated[bool, Field(
        description="Enable ownership controls (auto-enabled for mintable/pausable)"
    )] = False,
    capped: Annotated[bool, Field(
        description="Enable supply cap (requires ownable)"
    )] = False,
    max_supply: Annotated[int, Field(
        description="Maximum token supply for capped tokens (0 = unlimited)",
        ge=0
    )] = 0
) -> dict:
    """Generate ERC20 contract with strict parameter validation."""
    
    # Auto-enable ownable for features that require it
    ownable_final = ownable
    if mintable or pausable or capped:
        ownable_final = True

    env = Environment(loader=FileSystemLoader("/app/src"))
    template = env.get_template("contracts/erc20.sol")
    solidity_code = template.render(
        CONTRACT_NAME=contract_name,
        TOKEN_NAME=token_name,
        TOKEN_SYMBOL=token_symbol,
        INITIAL_SUPPLY=initial_supply,
        DECIMALS=decimals,
        mintable=mintable,
        burnable=burnable,
        pausable=pausable,
        permit=permit,
        ownable=ownable_final,
        capped=capped,
        max_supply=max_supply
    )

    return {
        "solidity_code": solidity_code,
        "contract_type": "ERC20",
        "contract_name": contract_name,
        "token_name": token_name,
        "token_symbol": token_symbol,
        "initial_supply": initial_supply,
        "features": {
            "mintable": mintable,
            "burnable": burnable, 
            "pausable": pausable,
            "permit": permit,
            "ownable": ownable_final,
            "capped": capped
        }
    }

@mcp.tool(
    name="generate_erc721_contract",
    description="Generate an ERC721 NFT contract with advanced features"
)
async def generate_erc721_contract(
    contract_name: Annotated[str, Field(
        description="Name of the contract class (e.g., 'MyNFT')",
        min_length=1, max_length=50
    )],
    token_name: Annotated[str, Field(
        description="Name of the NFT collection (e.g., 'My NFT Collection')",
        min_length=1, max_length=100
    )],
    token_symbol: Annotated[str, Field(
        description="NFT collection symbol (e.g., 'MNFT')",
        min_length=1, max_length=10
    )],
    base_uri: Annotated[str, Field(
        description="Base URI for token metadata (e.g., 'https://api.mynfts.com/metadata/')"
    )] = "",
    mintable: Annotated[bool, Field(
        description="Enable minting capability"
    )] = True,
    burnable: Annotated[bool, Field(
        description="Enable burning capability"
    )] = False,
    enumerable: Annotated[bool, Field(
        description="Enable token enumeration (increases gas costs)"
    )] = False,
    uri_storage: Annotated[bool, Field(
        description="Enable per-token URI storage"
    )] = False,
    ownable: Annotated[bool, Field(
        description="Enable ownership controls"
    )] = True,
    royalty: Annotated[bool, Field(
        description="Enable EIP-2981 royalty support"
    )] = False,
    royalty_percentage: Annotated[int, Field(
        description="Royalty percentage in basis points (250 = 2.5%, max 100%)",
        ge=0, le=10000
    )] = 250,
    max_supply: Annotated[int, Field(
        description="Maximum NFT supply (0 = unlimited)",
        ge=0
    )] = 0
) -> dict:
    """Generate ERC721 NFT contract with strict parameter validation."""

    env = Environment(loader=FileSystemLoader("/app/src"))
    template = env.get_template("contracts/erc721.sol")
    solidity_code = template.render(
        CONTRACT_NAME=contract_name,
        TOKEN_NAME=token_name,
        TOKEN_SYMBOL=token_symbol,
        base_uri=base_uri,
        mintable=mintable,
        burnable=burnable,
        enumerable=enumerable,
        uri_storage=uri_storage,
        ownable=ownable,
        royalty=royalty,
        royalty_percentage=royalty_percentage,
        max_supply=max_supply
    )

    return {
        "solidity_code": solidity_code,
        "contract_type": "ERC721", 
        "contract_name": contract_name,
        "token_name": token_name,
        "token_symbol": token_symbol,
        "base_uri": base_uri,
        "features": {
            "mintable": mintable,
            "burnable": burnable,
            "enumerable": enumerable,
            "uri_storage": uri_storage,
            "ownable": ownable,
            "royalty": royalty,
            "max_supply": max_supply
        }
    }

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
            import_remappings=["@openzeppelin=node_modules/@openzeppelin"],
            allow_paths="."
        )

        _, contract_data = next(iter(compiled.items()))
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
            "message": "Contract compiled successfully. Use get_abi and get_bytecode tools to retrieve data."
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
    name="deploy_contract",
    description="Deploy compiled contract to Ethereum network using compilation ID"
)
async def deploy_contract(
    compilation_id: Annotated[str, Field(
        description="Compilation ID from compile_contract tool"
    )],
    initial_owner: Annotated[str, Field(
        description="Initial owner wallet address (must be valid Ethereum address)"
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
    """Deploy contract using server wallet with strict parameter validation."""
    if compilation_id not in compilation_cache:
        return {
            "contract_address": None,
            "transaction_hash": None,
            "success": False,
            "message": "Invalid compilation ID"
        }
    
    try:
        # Check environment variables first
        if not private_key:
            return {
                "contract_address": None,
                "transaction_hash": None,
                "success": False,
                "message": "Private key not configured in environment variables"
            }
        
        if not ethereum_sepolia_rpc:
            return {
                "contract_address": None,
                "transaction_hash": None,
                "success": False,
                "message": "Ethereum RPC URL not configured in environment variables"
            }
        
        abi = compilation_cache[compilation_id]["abi"]
        bytecode = compilation_cache[compilation_id]["bytecode"]

        print("contract abi", abi)
        
        print(f"[DEBUG] Attempting to connect to RPC: {ethereum_sepolia_rpc}")
        w3 = Web3(Web3.HTTPProvider(ethereum_sepolia_rpc))
        
        try:
            # Test connection with more detailed error info
            is_connected = w3.is_connected()
            print(f"[DEBUG] Connection status: {is_connected}")
            
            if is_connected:
                latest_block = w3.eth.block_number
                print(f"[DEBUG] Latest block number: {latest_block}")
            else:
                # Try to get more specific error info
                try:
                    w3.eth.block_number
                except Exception as conn_error:
                    print(f"[DEBUG] Connection error details: {conn_error}")
                    return {
                        "contract_address": None,
                        "transaction_hash": None,
                        "success": False,
                        "message": f"Failed to connect to Ethereum network: {str(conn_error)}"
                    }
                
                return {
                    "contract_address": None,
                    "transaction_hash": None,
                    "success": False,
                    "message": "Failed to connect to Ethereum network"
                }
        except Exception as e:
            print(f"[DEBUG] Connection exception: {e}")
            return {
                "contract_address": None,
                "transaction_hash": None,
                "success": False,
                "message": f"Network connection error: {str(e)}"
            }
        
        account = w3.eth.account.from_key(private_key).address
        nonce = w3.eth.get_transaction_count(account)

        owner_address = initial_owner
        if not owner_address:
            owner_address = account

        # Ensure address is in proper checksum format
        owner_address = w3.to_checksum_address(owner_address)

        erc20_token = w3.eth.contract(abi=abi, bytecode=bytecode)
        
        # Check if constructor requires parameters by examining ABI
        constructor_inputs = []
        for item in abi:
            if item.get('type') == 'constructor':
                constructor_inputs = item.get('inputs', [])
                break
        
        print("Constructor Inputs:", constructor_inputs)
        
        # Build constructor arguments based on actual ABI parameters
        constructor_args = []
        if constructor_inputs:
            for input_param in constructor_inputs:
                param_name = input_param['name'].lower()
                param_type = input_param['type']
                
                print(f"[DEBUG] Processing constructor param: {param_name} ({param_type})")
                
                if param_type == 'address':
                    # Address parameters (like initialOwner)
                    constructor_args.append(owner_address)
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
                        constructor_args.append("Server Token")
                    elif 'symbol' in param_name:
                        constructor_args.append("STK")
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

        print(f"[DEBUG] constructor_inputs: {constructor_inputs}")
        print(f"[DEBUG] constructor_args: {constructor_args}")
        print(f"[DEBUG] initial_owner: {owner_address}")
        
        transaction = erc20_token.constructor(*constructor_args).build_transaction({
            'from': account,
            'nonce': nonce,
            'gas': gas_limit,
            'gasPrice': w3.to_wei(gas_price_gwei, 'gwei')
        })
        
        signed = w3.eth.account.sign_transaction(transaction, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        # Verify owner was set correctly (if contract has owner function)
        deployed_contract = w3.eth.contract(address=receipt.contractAddress, abi=abi)
        actual_owner = None
        try:
            if hasattr(deployed_contract.functions, 'owner'):
                actual_owner = deployed_contract.functions.owner().call()
                print(f"[DEBUG] Deployed contract owner: {actual_owner}")
        except Exception as e:
            print(f"[DEBUG] Could not read owner: {e}")
        
        return {
            "contract_address": receipt.contractAddress,
            "transaction_hash": tx_hash.hex(),
            "success": True,
            "message": "Contract deployed successfully",
            "gas_used": receipt.gasUsed,
            "block_number": receipt.blockNumber,
            "constructor_args": constructor_args,
            "initial_owner_used": owner_address,
            "actual_owner": actual_owner
        }
        
    except Exception as e:
        return {
            "contract_address": None,
            "transaction_hash": None,
            "success": False,
            "message": f"Deployment failed: {str(e)}"
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
        
        return {
            "success": True,
            "transaction": transaction,
            "constructor_args": constructor_args,
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

if __name__ == '__main__':
    mcp.run(transport="http", host="0.0.0.0", port=8081)