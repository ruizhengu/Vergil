'use client';

import React, { useState } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import { useAccount, useWalletClient } from 'wagmi';
import { serializeTransaction } from 'viem';

interface TransactionData {
  from?: string;
  to?: string;
  data?: string;
  gas?: string | number;
  gasPrice?: string | number;
  nonce?: number;
  chainId?: number;
  value?: string | number;
  mcpResponse?: any;
  estimated_gas?: number;
  gas_price_gwei?: number;
  user_address?: string;
}

interface ApprovalRequest {
  approval_id: string;
  transaction_data: TransactionData;
  timestamp: string;
  message: string;
}

interface TransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  transactionData?: TransactionData | null;
  approvalRequest?: ApprovalRequest | null;
  onApprovalSubmit?: (approvalId: string, approved: boolean, signedTxHex?: string, rejectionReason?: string) => Promise<boolean>;
  mode?: 'transaction' | 'approval'; // 'transaction' mode is deprecated, only 'approval' should be used
}

export const TransactionModal: React.FC<TransactionModalProps> = ({
  isOpen,
  onClose,
  transactionData,
  approvalRequest,
  onApprovalSubmit,
  mode = 'approval', // Default to approval mode since transaction mode is deprecated
}) => {
  const { address } = useAccount();
  const { data: walletClient } = useWalletClient();
  const [isConfirming, setIsConfirming] = useState(false);
  const [signStatus, setSignStatus] = useState<'idle' | 'approving' | 'signing' | 'broadcasting' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [rejectionReason] = useState<string>('');

  // Get transaction data from either direct prop or approval request
  const currentTransactionData = transactionData || approvalRequest?.transaction_data;
  
  if (!isOpen || !currentTransactionData) return null;

  const isApprovalMode = mode === 'approval' && approvalRequest;

  const handleConfirm = async () => {
    if (!walletClient || !address) {
      setErrorMessage('Wallet not connected');
      return;
    }

    setIsConfirming(true);
    setErrorMessage('');

    try {
      if (isApprovalMode && onApprovalSubmit) {
        // Approval mode: First approve, then sign and submit
        setSignStatus('approving');
        console.log('Approving deployment request:', approvalRequest?.approval_id);
        
        setSignStatus('signing');
        console.log('Transaction data received:', currentTransactionData);
        
        // Prepare transaction for sending (browser wallets use sendTransaction, not signTransaction)
        const txToSend = {
          account: address as `0x${string}`,
          to: currentTransactionData.to as `0x${string}` | undefined,
          data: currentTransactionData.data as `0x${string}`,
          gas: BigInt(currentTransactionData.gas || currentTransactionData.estimated_gas || 2000000),
          gasPrice: BigInt(currentTransactionData.gasPrice || (currentTransactionData.gas_price_gwei ? Math.floor(currentTransactionData.gas_price_gwei * 1e9) : 10e9)),
          nonce: currentTransactionData.nonce || undefined,
          value: BigInt(currentTransactionData.value || 0),
        };

        console.log('Sending transaction:', txToSend);
        setSignStatus('broadcasting');

        try {
          // Try signTransaction first (works with some wallets like MetaMask in certain cases)
          try {
            console.log('Attempting signTransaction...');
            const serializedTx = await walletClient.signTransaction(txToSend);
            console.log('Transaction signed successfully:', serializedTx);

            // Submit approval with signed transaction hex
            const approvalSuccess = await onApprovalSubmit(
              approvalRequest!.approval_id, 
              true, 
              serializedTx
            );

            if (approvalSuccess) {
              setSignStatus('success');
              console.log('Approval and signed transaction submitted successfully');
              
              // Close modal after a short delay
              setTimeout(() => {
                onClose();
                setSignStatus('idle');
              }, 2000);
            } else {
              throw new Error('Failed to submit approval response');
            }

          } catch (signError: any) {
            // If signTransaction fails, fall back to sendTransaction
            console.log('signTransaction failed, falling back to sendTransaction:', signError.message);
            
            // Check if this is the expected signTransaction error
            if (signError.message?.includes('eth_signTransaction') || 
                signError.message?.includes('not supported') ||
                signError.message?.includes('Method not supported')) {
              
              console.log('Using sendTransaction approach - transaction will be broadcast directly');
              const txHash = await walletClient.sendTransaction(txToSend);
              console.log('Transaction sent directly, hash:', txHash);

              // Submit approval with transaction hash (backend should handle this differently)
              const approvalSuccess = await onApprovalSubmit(
                approvalRequest!.approval_id, 
                true, 
                txHash // Note: This is a tx hash, not signed hex
              );

              if (approvalSuccess) {
                setSignStatus('success');
                console.log('Approval and transaction hash submitted successfully');
                
                setTimeout(() => {
                  onClose();
                  setSignStatus('idle');
                }, 2000);
              } else {
                throw new Error('Failed to submit approval response');
              }
            } else {
              throw signError;
            }
          }

        } catch (error: any) {
          console.error('Transaction failed:', error);
          throw new Error(`Transaction failed: ${error.message || 'Unknown error'}`);
        }

      } else {
        // This should never happen - all transactions should go through approval flow
        console.error('❌ Direct transaction mode triggered - this is deprecated');
        throw new Error('Invalid transaction mode. All transactions must go through approval flow.');
      }

    } catch (error: any) {
      console.error('Transaction signing/broadcasting failed:', error);
      setSignStatus('error');
      setErrorMessage(error.message || 'Transaction failed');
    } finally {
      setIsConfirming(false);
    }
  };

  const handleReject = async () => {
    // Reset confirmation state immediately to allow cancellation
    setIsConfirming(false);
    setSignStatus('idle');
    setErrorMessage('');
    
    if (isApprovalMode && onApprovalSubmit && approvalRequest) {
      setIsConfirming(true);
      setSignStatus('approving');
      
      try {
        const success = await onApprovalSubmit(
          approvalRequest.approval_id,
          false,
          undefined,
          rejectionReason || 'User rejected deployment'
        );

        if (success) {
          console.log('Deployment rejected successfully');
          onClose();
        } else {
          throw new Error('Failed to submit rejection');
        }
      } catch (error: any) {
        console.error('Error rejecting deployment:', error);
        setErrorMessage(error.message || 'Failed to reject deployment');
        setSignStatus('error');
      } finally {
        setIsConfirming(false);
      }
    } else {
      // Just close for non-approval mode
      onClose();
    }
  };

  const formatGwei = (wei: string | number | undefined) => {
    if (!wei) return 'N/A';
    try {
      return (Number(wei) / 1e9).toFixed(2) + ' Gwei';
    } catch {
      return 'N/A';
    }
  };

  const formatEther = (wei: string | number | undefined) => {
    if (!wei) return '0';
    try {
      return (Number(wei) / 1e18).toFixed(6) + ' ETH';
    } catch {
      return '0 ETH';
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content transaction-modal">
        <div className="modal-header">
          <h3>Confirm Contract Deployment</h3>
          <button onClick={() => {
            // Reset state when closing via X button
            setIsConfirming(false);
            setSignStatus('idle');
            setErrorMessage('');
            onClose();
          }} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div className="transaction-warning">
            <AlertTriangle size={20} className="warning-icon" />
            <p>
              You are about to deploy a smart contract. Please review the transaction details carefully.
            </p>
          </div>

          <div className="transaction-details">
            <div className="detail-row">
              <span className="detail-label">From:</span>
              <span className="detail-value">
                {address ? `${address.slice(0, 6)}...${address.slice(-4)}` : 'N/A'}
              </span>
            </div>

            <div className="detail-row">
              <span className="detail-label">Type:</span>
              <span className="detail-value">Contract Deployment</span>
            </div>

            <div className="detail-row">
              <span className="detail-label">Gas Limit:</span>
              <span className="detail-value">
                {currentTransactionData.gas ? Number(currentTransactionData.gas).toLocaleString() : 'N/A'}
              </span>
            </div>

            <div className="detail-row">
              <span className="detail-label">Gas Price:</span>
              <span className="detail-value">{formatGwei(currentTransactionData.gasPrice)}</span>
            </div>

            <div className="detail-row">
              <span className="detail-label">Estimated Fee:</span>
              <span className="detail-value">
                {currentTransactionData.gas && currentTransactionData.gasPrice
                  ? formatEther((BigInt(Number(currentTransactionData.gas)) * BigInt(Number(currentTransactionData.gasPrice))).toString())
                  : 'N/A'}
              </span>
            </div>

            <div className="detail-row">
              <span className="detail-label">Network:</span>
              <span className="detail-value">
                {currentTransactionData.chainId === 11155111 ? 'Sepolia Testnet' : `Chain ID: ${currentTransactionData.chainId}`}
              </span>
            </div>
          </div>

        </div>

        {/* Status Messages */}
        {signStatus !== 'idle' && (
          <div className={`status-message ${signStatus}`}>
            {signStatus === 'approving' && '🔄 Submitting approval response...'}
            {signStatus === 'signing' && '🔄 Please sign the transaction in your wallet...'}
            {signStatus === 'broadcasting' && '📡 Broadcasting transaction to network...'}
            {signStatus === 'success' && '✅ Transaction successful! Contract deployed.'}
            {signStatus === 'error' && `❌ ${errorMessage}`}
          </div>
        )}

        <div className="modal-footer">
          <button 
            onClick={handleReject} 
            className="btn-secondary" 
            disabled={signStatus === 'success'}
          >
            {signStatus === 'success' ? 'Close' : (isApprovalMode ? 'Reject' : 'Cancel')}
          </button>
          <button 
            onClick={handleConfirm} 
            className="btn-primary" 
            disabled={isConfirming || !address || signStatus === 'success'}
          >
            {isConfirming ? (
              signStatus === 'approving' ? 'Processing...' :
              signStatus === 'signing' ? 'Signing...' :
              signStatus === 'broadcasting' ? 'Broadcasting...' : 'Processing...'
            ) : (isApprovalMode ? 'Approve & Sign' : 'Sign & Deploy')}
          </button>
        </div>
      </div>
    </div>
  );
};