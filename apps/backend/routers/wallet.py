from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

# In-memory storage for wallet addresses (consider using Redis in production)
wallet_sessions: Dict[str, str] = {}

class WalletConnectRequest(BaseModel):
    wallet_address: str
    conversation_id: Optional[str] = None

class WalletDisconnectRequest(BaseModel):
    conversation_id: Optional[str] = None

class WalletResponse(BaseModel):
    success: bool
    message: str
    wallet_address: Optional[str] = None

@router.post("/connect", response_model=WalletResponse)
async def connect_wallet(request: WalletConnectRequest):
    try:
        wallet_address = request.wallet_address.lower() 
        conversation_id = request.conversation_id or "default"

        if not wallet_address.startswith('0x') or len(wallet_address) != 42:
            raise HTTPException(status_code=400, detail="Invalid Ethereum wallet address format")

        wallet_sessions[conversation_id] = wallet_address
        
        logger.info(f"Wallet connected: {wallet_address[:8]}...{wallet_address[-6:]} for conversation {conversation_id[:8]}...")
        
        return WalletResponse(
            success=True,
            message="Wallet connected successfully",
            wallet_address=wallet_address
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting wallet: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect wallet: {str(e)}")

@router.post("/disconnect", response_model=WalletResponse)
async def disconnect_wallet(request: WalletDisconnectRequest):
    try:
        conversation_id = request.conversation_id or "default"
        
        # Remove wallet from session if it exists
        removed_wallet = wallet_sessions.pop(conversation_id, None)
        
        if removed_wallet:
            logger.info(f"Wallet disconnected: {removed_wallet[:8]}...{removed_wallet[-6:]} for conversation {conversation_id[:8]}...")
            message = "Wallet disconnected successfully"
        else:
            message = "No wallet was connected for this session"
        
        return WalletResponse(
            success=True,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error disconnecting wallet: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disconnect wallet: {str(e)}")

@router.get("/status", response_model=WalletResponse)
async def get_wallet_status(conversation_id: Optional[str] = None):
    try:
        session_id = conversation_id or "default"
        wallet_address = wallet_sessions.get(session_id)
        
        if wallet_address:
            return WalletResponse(
                success=True,
                message="Wallet is connected",
                wallet_address=wallet_address
            )
        else:
            return WalletResponse(
                success=True,
                message="No wallet connected"
            )
            
    except Exception as e:
        logger.error(f"Error getting wallet status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get wallet status: {str(e)}")

def get_wallet_for_conversation(conversation_id: str) -> Optional[str]:
    return wallet_sessions.get(conversation_id)