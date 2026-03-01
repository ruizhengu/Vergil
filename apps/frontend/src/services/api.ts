import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ChatRequest {
  message: string;
  conversationId?: string;
}

export interface ChatResponse {
  success: boolean;
  data?: {
    response: string;
    message_id: string;
    structured_response?: any;
    status?: string;
    conversation_id: string;
    timestamp: string;
    backend_mode: string;
  };
  error?: string;
}

export interface WalletConnectRequest {
  wallet_address: string;
  conversation_id?: string;
}

export interface WalletDisconnectRequest {
  conversation_id?: string;
}

export interface WalletResponse {
  success: boolean;
  message: string;
  wallet_address?: string;
}

class ApiService {
  private axiosInstance;

  constructor() {
    this.axiosInstance = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  private async _sendMessage(request: ChatRequest): Promise<ChatResponse> {
    try {
      const backendRequest = {
        message: request.message,
        conversation_id: request.conversationId
      };

      const response = await this.axiosInstance.post('/api/chat/', backendRequest);
      console.log("response.data from assistant:", response.data)

      return response.data as ChatResponse;

    } catch (error: any) {
      console.error('Backend API Error:', error);
      
      if (error.response) {
        const errorMessage = error.response.data?.error || error.message || 'Backend server error';
        console.error('Backend responded with error:', error.response.status, errorMessage);
        return {
          success: false,
          error: `Backend Error: ${errorMessage}`
        };
      }
      
      if (error.request) {
        console.error('Cannot reach backend server at:', API_BASE_URL);
        return {
          success: false,
          error: 'Cannot connect to backend server. Please ensure the backend is running on port 8000.'
        };
      }
      
      return {
        success: false,
        error: 'An unexpected error occurred while connecting to the backend'
      };
    }
  }

  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    return this._sendMessage(request);
  }

  async sendMessageReal(request: ChatRequest): Promise<ChatResponse> {
    return this._sendMessage(request);
  }

  async startNewConversation(): Promise<{ conversationId: string }> {
    try {
      const response = await this.axiosInstance.post('/api/chat/new');
      return response.data as { conversationId: string };
    } catch (error) {
      console.error('Error starting new conversation:', error);
      throw error;
    }
  }

  // Legacy broadcastSignedTransaction removed - now handled through approval flow

  async *simulateStreamingResponse(message: string): AsyncGenerator<string, void, unknown> {
    yield "THOUGHT: Backend connection failed, running in frontend fallback mode...";
    
    if (message.toLowerCase().includes('contract') || message.toLowerCase().includes('erc20') || message.toLowerCase().includes('erc721')) {
      yield "ACTION_NEEDED: simulate_contract_generation";
      yield `FINAL_ANSWER: ⚠️ **Backend Disconnected - Frontend Fallback Mode**

I'm running in simulation mode because the backend server isn't available.

🏗️ **Expected Architecture**: 
Frontend → Backend API (port 8000) → ReAct Agent → MCP Server (port 8081)

📍 **Current Status**: Frontend Only (simulation mode)

Here's what I would help you with when the backend is connected:
• **Full ReAct reasoning** with THOUGHT → ACTION → ANSWER flow
• **Real ERC20/ERC721 generation** via MCP tools  
• **Smart contract compilation** and deployment
• **Blockchain interactions** and testing

Please ensure the backend server is running on port 8000 to access the full Smart Contract Assistant capabilities!`;
    } else {
      yield `FINAL_ANSWER: Hello! I'm your Smart Contract Assistant (frontend fallback mode).

⚠️ **Backend Connection Issue**: Cannot reach backend server
🔧 **Expected Backend**: http://localhost:8000
🏗️ **Full Architecture**: Frontend + Backend API + ReAct Agent + MCP Server

When properly connected, I can help you with:
• **ERC20 & ERC721** contract generation with full reasoning
• **Smart contract** compilation and deployment  
• **Blockchain** interactions and testing
• **Multi-step workflows** with conversation memory

Please start the backend server to access the complete functionality!`;
    }
  }

  // Approval workflow methods
  async pollApprovalRequests(): Promise<{ has_requests: boolean; requests: any[] }> {
    try {
      const response = await this.axiosInstance.get('/api/approval/poll');
      return response.data;
    } catch (error: any) {
      console.error('Error polling approval requests:', error);
      return { has_requests: false, requests: [] };
    }
  }

  async submitApprovalResponse(approvalData: {
    approval_id: string;
    approved: boolean;
    signed_transaction_hex?: string;
    rejection_reason?: string;
  }): Promise<{ success: boolean; message: string; error?: string }> {
    try {
      console.log('🚀 Sending approval response to backend:', {
        approval_id: approvalData.approval_id,
        approved: approvalData.approved,
        has_signed_tx: !!approvalData.signed_transaction_hex,
        signed_tx_length: approvalData.signed_transaction_hex?.length,
        rejection_reason: approvalData.rejection_reason
      });
      
      const response = await this.axiosInstance.post('/api/approval/respond', approvalData);
      
      console.log('🎯 Backend response:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('❌ Error submitting approval response:', error);
      
      if (error.response) {
        return {
          success: false,
          message: 'Failed to submit approval response',
          error: error.response.data?.error || error.message
        };
      }
      
      return {
        success: false,
        message: 'Failed to connect to approval service',
        error: 'Network error'
      };
    }
  }

  async createMockApprovalRequest(): Promise<{ success: boolean; approval_id?: string; error?: string }> {
    try {
      const response = await this.axiosInstance.post('/api/approval/mock-request');
      return response.data;
    } catch (error: any) {
      console.error('Error creating mock approval request:', error);
      return {
        success: false,
        error: error.message || 'Failed to create mock request'
      };
    }
  }

  // Wallet management methods
  async connectWallet(walletAddress: string, conversationId?: string): Promise<WalletResponse> {
    try {
      const request: WalletConnectRequest = {
        wallet_address: walletAddress,
        conversation_id: conversationId
      };
      
      const response = await this.axiosInstance.post('/api/wallet/connect', request);
      console.log('Wallet connected:', response.data);
      return response.data as WalletResponse;
    } catch (error: any) {
      console.error('Error connecting wallet:', error);
      
      if (error.response) {
        return {
          success: false,
          message: error.response.data?.detail || error.response.data?.message || 'Failed to connect wallet'
        };
      }
      
      return {
        success: false,
        message: 'Network error while connecting wallet'
      };
    }
  }

  async disconnectWallet(conversationId?: string): Promise<WalletResponse> {
    try {
      const request: WalletDisconnectRequest = {
        conversation_id: conversationId
      };
      
      const response = await this.axiosInstance.post('/api/wallet/disconnect', request);
      console.log('Wallet disconnected:', response.data);
      return response.data as WalletResponse;
    } catch (error: any) {
      console.error('Error disconnecting wallet:', error);
      
      if (error.response) {
        return {
          success: false,
          message: error.response.data?.detail || error.response.data?.message || 'Failed to disconnect wallet'
        };
      }
      
      return {
        success: false,
        message: 'Network error while disconnecting wallet'
      };
    }
  }

  async getWalletStatus(conversationId?: string): Promise<WalletResponse> {
    try {
      const params = conversationId ? { conversation_id: conversationId } : {};
      const response = await this.axiosInstance.get('/api/wallet/status', { params });
      return response.data as WalletResponse;
    } catch (error: any) {
      console.error('Error getting wallet status:', error);
      
      if (error.response) {
        return {
          success: false,
          message: error.response.data?.detail || error.response.data?.message || 'Failed to get wallet status'
        };
      }
      
      return {
        success: false,
        message: 'Network error while getting wallet status'
      };
    }
  }

}

export const apiService = new ApiService();