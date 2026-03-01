import React, { useState, useRef, useEffect } from 'react';
import { Message, ChatState } from '../types/Chat';
import { apiService } from '../services/api';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';
import ChatHeader from './ChatHeader';
import { TransactionModal } from './TransactionModal';
import { AlertCircle } from 'lucide-react';
import { useAccount } from 'wagmi';
import { useIsClient } from '../hooks/useIsClient';
import { useApprovalPolling } from '../hooks/useApprovalPolling';
import './Chat.css';

const ChatContainer: React.FC = () => {
  const isClient = useIsClient();
  const { address, isConnected } = useAccount();
  const [chatState, setChatState] = useState<ChatState>(() => ({
    messages: [],
    isLoading: false,
    conversationId: null,
  }));  
  
  const [error, setError] = useState<string | null>(null);
  const [transactionModal, setTransactionModal] = useState<{
    isOpen: boolean;
    transactionData?: any;
    approvalRequest?: any;
    mode?: 'transaction' | 'approval';
  }>({ isOpen: false, transactionData: null, approvalRequest: null, mode: 'approval' });
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Approval polling hook
  const {
    approvalRequests,
    hasActiveRequest,
    isPolling,
    startPolling,
    stopPolling,
    submitApproval,
    createMockRequest
  } = useApprovalPolling(3000); // Poll every 3 seconds

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatState.messages]);

  // Start polling when component mounts
  useEffect(() => {
    console.log('Starting approval polling on component mount');
    startPolling();
    
    return () => {
      console.log('Stopping approval polling on component unmount');
      stopPolling();
    };
  }, [startPolling, stopPolling]);

  // Auto-register wallet when connected/disconnected
  useEffect(() => {
    const handleWalletConnection = async () => {
      if (isConnected && address) {
        console.log('Wallet connected, registering with backend:', address);
        try {
          const result = await apiService.connectWallet(address, chatState.conversationId || undefined);
          if (result.success) {
            console.log('Wallet registered successfully:', result.message);
          } else {
            console.warn('Failed to register wallet:', result.message);
          }
        } catch (error) {
          console.error('Error registering wallet:', error);
        }
      } else if (!isConnected && address) {
        console.log('Wallet disconnected, unregistering from backend');
        try {
          const result = await apiService.disconnectWallet(chatState.conversationId || undefined);
          if (result.success) {
            console.log('Wallet unregistered successfully:', result.message);
          } else {
            console.warn('Failed to unregister wallet:', result.message);
          }
        } catch (error) {
          console.error('Error unregistering wallet:', error);
        }
      }
    };

    // Only run on client side and when isClient is ready
    if (isClient) {
      handleWalletConnection();
    }
  }, [isConnected, address, isClient, chatState.conversationId]);

  // Handle approval requests when they arrive
  useEffect(() => {
    if (hasActiveRequest && approvalRequests.length > 0 && !transactionModal.isOpen) {
      const latestRequest = approvalRequests[0]; // Handle the first/latest request
      console.log('🔔 New approval request detected:', latestRequest);
      
      // Show approval modal
      setTransactionModal({
        isOpen: true,
        approvalRequest: latestRequest,
        mode: 'approval'
      });

      // Add a system message about the approval request
      const approvalMessage: Message = {
        id: generateMessageId(),
        role: 'assistant',
        content: '🔔 **Deployment Approval Required**: Please review the transaction details in the modal and approve or reject the deployment.',
        timestamp: new Date(),
      };

      setChatState(prev => ({
        ...prev,
        messages: [...prev.messages, approvalMessage],
      }));
    }
  }, [hasActiveRequest, approvalRequests, transactionModal.isOpen]);

  useEffect(() => {
    if (chatState.messages.length === 0) {
      const welcomeMessage: Message = {
        id: 'welcome',
        role: 'assistant',
        content: 'Hello! I\'m your Smart Contract Assistant. I can help you:\n\n• Generate ERC20 and ERC721 contracts\n• Compile Solidity code\n• Deploy contracts to testnets\n• Interact with deployed contracts\n\nWhat would you like to create today?',
        timestamp: new Date(),
      };
      
      setChatState(prev => ({
        ...prev,
        messages: [welcomeMessage],
      }));
    }
  }, [chatState.messages.length]);

  const generateMessageId = () => {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
  };

  // Function to detect if a message contains transaction data that needs signing
  const parseTransactionFromMessage = (content: string) => {
    try {
      console.log('Parsing message for transaction data:', content.substring(0, 200) + '...');
      
      // Look for MCP server response pattern with transaction data
      // The prepare_deployment_transaction tool returns this format:
      // {"success": true, "transaction": {...}, "estimated_gas": ..., "user_address": ...}
      
      // Method 1: Look for the transaction preparation signature first
      if (content.includes('"success":true') && content.includes('"transaction":')) {
        console.log('Found transaction signature, attempting to extract JSON...');
        
        // Find the start and end of the JSON object
        const startIndex = content.indexOf('{"success":true');
        if (startIndex !== -1) {
          // Find the matching closing brace
          let braceCount = 0;
          let endIndex = -1;
          
          for (let i = startIndex; i < content.length; i++) {
            if (content[i] === '{') braceCount++;
            else if (content[i] === '}') {
              braceCount--;
              if (braceCount === 0) {
                endIndex = i;
                break;
              }
            }
          }
          
          if (endIndex !== -1) {
            try {
              const jsonStr = content.substring(startIndex, endIndex + 1);
              console.log('Extracted JSON string:', jsonStr.substring(0, 200) + '...');
              const data = JSON.parse(jsonStr);
              
              if (data.success && data.transaction && typeof data.transaction === 'object') {
                console.log('Successfully parsed transaction data:', data);
                return {
                  mcpResponse: data,
                  transaction: {
                    ...data.transaction,
                    // Ensure required fields are present
                    gas: data.transaction.gas || data.estimated_gas || 2000000,
                    gasPrice: data.transaction.gasPrice || (data.gas_price_gwei ? Math.floor(data.gas_price_gwei * 1e9) : 10e9),
                    chainId: data.transaction.chainId || data.chain_id || 11155111
                  }
                };
              }
            } catch (e) {
              console.log('Failed to parse extracted JSON:', e);
            }
          }
        }
      }
      
      // Method 2: More flexible approach - find any valid JSON object with success and transaction
      const jsonObjectRegex = /\{(?:[^{}]|{[^{}]*})*\}/g;
      const jsonObjects = content.match(jsonObjectRegex);
      
      if (jsonObjects) {
        for (const jsonStr of jsonObjects) {
          try {
            const data = JSON.parse(jsonStr);
            if (data && typeof data === 'object' && data.success === true && data.transaction) {
              console.log('Found flexible transaction data:', data);
              return {
                mcpResponse: data,
                transaction: data.transaction
              };
            }
          } catch (e) {
            // Skip invalid JSON
            continue;
          }
        }
      }
      
      // Method 2: Look for JSON code blocks with transaction data
      const jsonBlockMatches = content.match(/```json\s*(\{[\s\S]*?\})\s*```/g);
      if (jsonBlockMatches) {
        for (const block of jsonBlockMatches) {
          try {
            const jsonContent = block.replace(/```json\s*/, '').replace(/\s*```/, '');
            const data = JSON.parse(jsonContent);
            if (data.transaction && data.success) {
              console.log('Found transaction in JSON block:', data);
              return {
                mcpResponse: data,
                transaction: data.transaction
              };
            }
          } catch (e) {
            console.log('Failed to parse JSON block:', e);
            continue;
          }
        }
      }
      
      // Method 3: Look for nested transaction objects in text
      const nestedTransactionPattern = /"transaction":\s*\{[^{}]*"from"[^{}]*"data"[^{}]*"gas"[^{}]*\}/g;
      const nestedMatches = content.match(nestedTransactionPattern);
      
      if (nestedMatches) {
        for (const match of nestedMatches) {
          try {
            const transactionJson = `{${match}}`;
            const data = JSON.parse(transactionJson);
            if (data.transaction) {
              console.log('Found nested transaction:', data.transaction);
              return {
                mcpResponse: null,
                transaction: data.transaction
              };
            }
          } catch (e) {
            console.log('Failed to parse nested transaction:', e);
            continue;
          }
        }
      }
      
      // Method 4: Look for standalone transaction objects
      const standaloneTransactionPattern = /\{[^{}]*"from"[^{}]*"data"[^{}]*"gas"[^{}]*"gasPrice"[^{}]*"chainId"[^{}]*\}/g;
      const standaloneMatches = content.match(standaloneTransactionPattern);
      
      if (standaloneMatches) {
        for (const match of standaloneMatches) {
          try {
            const transaction = JSON.parse(match);
            if (transaction.from && transaction.data && transaction.gas) {
              console.log('Found standalone transaction:', transaction);
              return {
                mcpResponse: null,
                transaction: transaction
              };
            }
          } catch (e) {
            console.log('Failed to parse standalone transaction:', e);
            continue;
          }
        }
      }
      
      console.log('No transaction data found in message');
      return null;
    } catch (error) {
      console.error('Error parsing transaction from message:', error);
      return null;
    }
  };

  const handleApprovalSubmit = async (approvalId: string, approved: boolean, signedTxHex?: string, rejectionReason?: string) => {
    console.log('🔄 Handling approval submission:', { approvalId, approved, hasSignedTx: !!signedTxHex });
    
    try {
      const success = await submitApproval(approvalId, approved, signedTxHex, rejectionReason);
      
      if (success) {
        // Create detailed success message with transaction details
        let successContent = '';
        
        if (approved) {
          // Get current approval request to access transaction data
          const currentRequest = approvalRequests.find(req => req.approval_id === approvalId);
          
          if (signedTxHex && signedTxHex.startsWith('0x') && signedTxHex.length > 20) {
            // If we have a transaction hash
            const isHash = signedTxHex.length === 66; // Standard tx hash length
            
            successContent = `✅ **Smart Contract Deployment Successful!**

🎉 **Contract Details:**
• **Transaction${isHash ? ' Hash' : ''}**: \`${signedTxHex}\`
• **Network**: ${currentRequest?.transaction_data?.chainId === 11155111 ? 'Sepolia Testnet' : `Chain ID: ${currentRequest?.transaction_data?.chainId}`}
• **Gas Used**: ${currentRequest?.transaction_data?.gas ? Number(currentRequest?.transaction_data?.gas).toLocaleString() : 'N/A'}
• **Status**: ✅ Confirmed

🔗 **View on Explorer**: 
${currentRequest?.transaction_data?.chainId === 11155111 
  ? `[Sepolia Etherscan](https://sepolia.etherscan.io/${isHash ? 'tx' : 'address'}/${signedTxHex})` 
  : 'Block explorer link not available'}

Your smart contract has been successfully deployed and is now live on the blockchain! 🚀`;
          } else {
            successContent = '✅ **Deployment Approved**: Your deployment has been approved and the transaction has been submitted to the network. Transaction details will be available shortly.';
          }
        } else {
          successContent = `❌ **Deployment Rejected**: ${rejectionReason || 'Deployment was rejected.'}`;
        }
        
        const statusMessage: Message = {
          id: generateMessageId(),
          role: 'assistant',
          content: successContent,
          timestamp: new Date(),
        };

        setChatState(prev => ({
          ...prev,
          messages: [...prev.messages, statusMessage],
        }));

        // Close modal
        setTransactionModal({ 
          isOpen: false, 
          transactionData: null, 
          approvalRequest: null, 
          mode: 'transaction' 
        });
      }
      
      return success;
    } catch (error) {
      console.error('❌ Error handling approval submission:', error);
      return false;
    }
  };

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return;

    let enhancedContent = content.trim();

    const userMessage: Message = {
      id: generateMessageId(),
      role: 'user',
      content: enhancedContent,
      timestamp: new Date(),
    };

    setChatState(prev => ({
      ...prev,
      messages: [...prev.messages, userMessage],
      isLoading: true,
    }));

    setError(null);

    try {
      const assistantMessageId = generateMessageId();
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      };

      setChatState(prev => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      try {
        const currentConversationId = chatState.conversationId;
        console.log('Current chat state:', chatState);
        console.log('Sending message with conversation ID:', currentConversationId);

        const response = await apiService.sendMessageReal({
          message: enhancedContent,
          conversationId: chatState.conversationId ?? undefined,
        });

        console.log('Full response structure:', JSON.stringify(response, null, 2));
        console.log('response.success:', response.success);
        console.log('response.data:', response.data);
        console.log('typeof response.data:', typeof response.data);
        
        if (response.success && response.data) {
          const backendConversationId = response.data.conversation_id;
          const assistantResponse = response.data.response;
          const structuredResponse = response.data.structured_response;
          const status = response.data.status;

          console.log('Backend response status:', status);
          console.log('Structured response:', structuredResponse);

          // Check if the backend indicates a transaction is ready for signing
          const isPendingSignature = status === 'pending_signature';
          let transactionData = null;

          // First check structured_response for MCP transaction data
          if (structuredResponse && structuredResponse.success && structuredResponse.transaction) {
            console.log('Found transaction in structured_response:', structuredResponse);
            transactionData = {
              mcpResponse: structuredResponse,
              transaction: structuredResponse.transaction
            };
          } else {
            // Fallback to parsing from message text
            console.log('Checking for transaction data in response text:', assistantResponse.substring(0, 300) + '...');
            const parsedData = parseTransactionFromMessage(assistantResponse);
            console.log('Parsed transaction data from text:', parsedData);
            if (parsedData) {
              transactionData = parsedData;
            }
          }
          
          console.log('Final transaction data:', transactionData);
          console.log('Is pending signature:', isPendingSignature);
          console.log('Has transaction data:', !!transactionData);
          console.log('Is connected:', isConnected);
          console.log('Has address:', !!address);
          
          if ((isPendingSignature || transactionData) && transactionData?.transaction && isConnected && address) {
            console.log('Showing transaction modal with transaction data:', transactionData);
            console.log('⚠️ Direct transaction modal triggered - this should use approval flow instead');
            // Note: This direct transaction flow is deprecated
            // All transactions should go through the approval polling system
            // Keeping this as fallback but logging for debugging
          } else if (isPendingSignature && !isConnected) {
            console.log('Transaction ready but wallet not connected');
            // Prompt user to connect wallet
            const connectWalletMessage: Message = {
              id: generateMessageId(),
              role: 'assistant',
              content: ' **Wallet Required**: Please connect your wallet to sign the prepared transaction.',
              timestamp: new Date(),
            };
            
            setChatState(prev => ({
              ...prev,
              messages: [...prev.messages, connectWalletMessage],
            }));
          } else if (isPendingSignature && !transactionData) {
            console.log('Pending signature but no transaction data - asking user to check wallet');
            // Add a message encouraging user to check their wallet
            const checkWalletMessage: Message = {
              id: generateMessageId(),
              role: 'assistant',
              content: ' **Transaction Ready**: Please check your connected wallet app (MetaMask) for a transaction notification to sign.',
              timestamp: new Date(),
            };
            
            setChatState(prev => ({
              ...prev,
              messages: [...prev.messages, checkWalletMessage],
            }));
          }

          const newConversationId = currentConversationId || backendConversationId;
          console.log('Response conversation ID:', backendConversationId);
          console.log('Current conversation ID:', currentConversationId);
          console.log('New conversation ID:', newConversationId);
          
          setChatState(prev => {
            console.log('Previous state conversation ID:', prev.conversationId);
            return {
              ...prev,
              conversationId: newConversationId,
              messages: prev.messages.map(msg => 
                msg.id === assistantMessageId 
                  ? { ...msg, content: assistantResponse, isStreaming: false }
                  : msg
              ),
            };
          });
        } else {
          throw new Error(response.error || 'Failed to get response');
        }
      } catch (apiError) {
        console.warn('API call failed, using simulation:', apiError);

        let fullResponse = '';
        for await (const chunk of apiService.simulateStreamingResponse(content)) {
          const newResponse = fullResponse + (fullResponse ? '\n\n' : '') + chunk;
          fullResponse = newResponse;
          
          setChatState(prev => ({
            ...prev,
            conversationId: prev.conversationId, 
            messages: prev.messages.map(msg => 
              msg.id === assistantMessageId 
                ? { ...msg, content: newResponse }
                : msg
            ),
          }));

        }
      }

      setChatState(prev => ({
        ...prev,
        messages: prev.messages.map(msg => 
          msg.id === assistantMessageId 
            ? { ...msg, isStreaming: false }
            : msg
        ),
        isLoading: false,
      }));

    } catch (err) {
      console.error('Error sending message:', err);
      setError('Failed to send message. Please try again.');
      
      setChatState(prev => ({
        ...prev,
        isLoading: false,
      }));
    }
  };

  const handleNewChat = () => {
    setChatState({
      messages: [],
      isLoading: false,
      conversationId: null, 
    });
    setError(null);
  };

  return (
    <div className="chat-container">
      <ChatHeader 
        onNewChat={handleNewChat}
        conversationId={chatState.conversationId}
      />

      {/* Development Helper */}
      {process.env.NODE_ENV === 'development' && (
        <div style={{ padding: '8px', backgroundColor: '#f0f0f0', borderBottom: '1px solid #ccc', fontSize: '12px' }}>
          <strong>Dev Tools:</strong>
          <button 
            onClick={createMockRequest}
            style={{ marginLeft: '8px', padding: '4px 8px', fontSize: '12px' }}
          >
            Create Mock Approval
          </button>
          <span style={{ marginLeft: '8px', color: isPolling ? 'green' : 'red' }}>
            Polling: {isPolling ? 'ON' : 'OFF'}
          </span>
          <span style={{ marginLeft: '8px' }}>
            Active Requests: {approvalRequests.length}
          </span>
        </div>
      )}
      
      {/* Error Banner */}
      {error && (
        <div className="error-banner">
          <div className="error-content">
            <div className="error-message">
              <AlertCircle size={20} style={{ marginRight: '8px' }} />
              <span>{error}</span>
            </div>
            <button
              onClick={() => setError(null)}
              className="error-close"
            >
              ×
            </button>
          </div>
        </div>
      )}
      
      {/* Messages Area */}
      <div className="messages-area">
        <div className="messages-container">
          {chatState.messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>
      
      {/* Input Area */}
      <div className="input-area">
        <div className="input-container">
          <ChatInput
            onSendMessage={handleSendMessage}
            isLoading={chatState.isLoading}
            disabled={!!error}
          />
        </div>
      </div>

      {/* Transaction Modal */}
      <TransactionModal
        isOpen={transactionModal.isOpen}
        onClose={() => setTransactionModal({ 
          isOpen: false, 
          transactionData: null, 
          approvalRequest: null, 
          mode: 'approval' 
        })}
        transactionData={transactionModal.transactionData}
        approvalRequest={transactionModal.approvalRequest}
        mode={transactionModal.mode}
        onApprovalSubmit={handleApprovalSubmit}
      />
    </div>
  );
};

export default ChatContainer;