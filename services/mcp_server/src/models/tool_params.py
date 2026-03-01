from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional


class ERC20ContractParams(BaseModel):
    """Parameters for generating ERC20 token contracts."""
    
    contract_name: str = Field(
        description="Name of the contract class (e.g., 'MyToken')",
        min_length=1,
        max_length=50
    )
    token_name: str = Field(
        description="Display name of the token (e.g., 'My Token')",
        min_length=1,
        max_length=100
    )
    token_symbol: str = Field(
        description="Token symbol (3-10 characters, uppercase recommended)",
        min_length=1,
        max_length=10
    )
    initial_supply: int = Field(
        default=0,
        ge=0,
        description="Initial token supply (0 for no initial mint)"
    )
    decimals: int = Field(
        default=18,
        ge=0,
        le=77,
        description="Number of decimal places (typically 18)"
    )
    mintable: bool = Field(
        default=False,
        description="Enable minting capability (requires ownable)"
    )
    burnable: bool = Field(
        default=False,
        description="Enable burning capability"
    )
    pausable: bool = Field(
        default=False,
        description="Enable pause functionality (requires ownable)"
    )
    permit: bool = Field(
        default=False,
        description="Enable EIP-2612 permit functionality"
    )
    ownable: bool = Field(
        default=False,
        description="Enable ownership controls (auto-enabled for mintable/pausable)"
    )
    capped: bool = Field(
        default=False,
        description="Enable supply cap (requires ownable)"
    )
    max_supply: int = Field(
        default=0,
        ge=0,
        description="Maximum token supply for capped tokens (0 = unlimited)"
    )


class ERC721ContractParams(BaseModel):
    """Parameters for generating ERC721 NFT contracts."""
    
    contract_name: str = Field(
        description="Name of the contract class (e.g., 'MyNFT')",
        min_length=1,
        max_length=50
    )
    token_name: str = Field(
        description="Name of the NFT collection (e.g., 'My NFT Collection')",
        min_length=1,
        max_length=100
    )
    token_symbol: str = Field(
        description="NFT collection symbol (e.g., 'MNFT')",
        min_length=1,
        max_length=10
    )
    base_uri: str = Field(
        default="",
        description="Base URI for token metadata (e.g., 'https://api.mynfts.com/metadata/')"
    )
    mintable: bool = Field(
        default=True,
        description="Enable minting capability"
    )
    burnable: bool = Field(
        default=False,
        description="Enable burning capability"
    )
    enumerable: bool = Field(
        default=False,
        description="Enable token enumeration (increases gas costs)"
    )
    uri_storage: bool = Field(
        default=False,
        description="Enable per-token URI storage"
    )
    ownable: bool = Field(
        default=True,
        description="Enable ownership controls"
    )
    royalty: bool = Field(
        default=False,
        description="Enable EIP-2981 royalty support"
    )
    royalty_percentage: int = Field(
        default=250,
        ge=0,
        le=10000,
        description="Royalty percentage in basis points (250 = 2.5%, max 100%)"
    )
    max_supply: int = Field(
        default=0,
        ge=0,
        description="Maximum NFT supply (0 = unlimited)"
    )


class CompileContractParams(BaseModel):
    """Parameters for compiling Solidity contracts."""
    
    solidity_code: str = Field(
        description="Solidity source code to compile",
        min_length=1
    )


class DeployContractParams(BaseModel):
    """Parameters for deploying contracts to blockchain."""
    
    compilation_id: str = Field(
        description="Compilation ID from compile_contract tool"
    )
    initial_owner: str = Field(
        description="Initial owner wallet address (must be valid Ethereum address)"
    )
    gas_limit: int = Field(
        default=2000000,
        ge=21000,
        le=10000000,
        description="Gas limit for deployment transaction"
    )
    gas_price_gwei: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Gas price in Gwei"
    )
    
    @field_validator('initial_owner')
    def validate_ethereum_address(cls, v):
        """Validate Ethereum address format."""
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError('Invalid Ethereum address format')
        try:
            # Basic hex validation
            int(v[2:], 16)
        except ValueError:
            raise ValueError('Invalid Ethereum address format')
        return v


class PrepareDeploymentParams(BaseModel):
    """Parameters for preparing deployment transactions for user signing."""
    
    compilation_id: str = Field(
        description="Compilation ID from compile_contract tool"
    )
    user_wallet_address: str = Field(
        description="User's wallet address that will sign the transaction"
    )
    gas_limit: int = Field(
        default=2000000,
        ge=21000,
        le=10000000,
        description="Gas limit for deployment transaction"
    )
    gas_price_gwei: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Gas price in Gwei"
    )
    
    @field_validator('user_wallet_address')
    def validate_ethereum_address(cls, v):
        """Validate Ethereum address format."""
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError('Invalid Ethereum address format')
        try:
            int(v[2:], 16)
        except ValueError:
            raise ValueError('Invalid Ethereum address format')
        return v


class BroadcastTransactionParams(BaseModel):
    """Parameters for broadcasting signed transactions."""
    
    signed_transaction_hex: str = Field(
        description="Hex-encoded signed transaction data",
        min_length=1
    )
    
    @field_validator('signed_transaction_hex')
    def validate_hex_format(cls, v):
        """Validate hex transaction format."""
        # Remove 0x prefix if present
        hex_data = v[2:] if v.startswith('0x') else v
        
        try:
            # Validate it's valid hex
            bytes.fromhex(hex_data)
        except ValueError:
            raise ValueError('Invalid hex format for signed transaction')
        
        return v


class GetAbiParams(BaseModel):
    """Parameters for retrieving contract ABI."""
    
    compilation_id: str = Field(
        description="Compilation ID from compile_contract tool"
    )


class GetBytecodeParams(BaseModel):
    """Parameters for retrieving contract bytecode."""
    
    compilation_id: str = Field(
        description="Compilation ID from compile_contract tool"
    )


# Legacy support for backward compatibility
class LegacyGenerateContractParams(BaseModel):
    """Legacy parameters for generate_contract tool (backward compatibility)."""
    
    contract_name: str = Field(
        default="MyToken",
        description="Name of the contract class"
    )
    token_name: str = Field(
        default="MyToken", 
        description="Display name of the token"
    )
    token_symbol: str = Field(
        default="MTK",
        description="Token symbol"
    )
    mintable: bool = Field(
        default=False,
        description="Enable minting capability"
    )
    ownable: bool = Field(
        default=False,
        description="Enable ownership controls"
    )