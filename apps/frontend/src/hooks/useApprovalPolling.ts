import { useState, useEffect, useCallback, useRef } from 'react';
import { apiService } from '../services/api';

interface ApprovalRequest {
  approval_id: string;
  transaction_data: {
    to?: string;
    data?: string;
    gas?: string | number;
    gasPrice?: string | number;
    chainId?: number;
    value?: string | number;
  };
  timestamp: string;
  message: string;
}

interface UseApprovalPollingResult {
  approvalRequests: ApprovalRequest[];
  hasActiveRequest: boolean;
  isPolling: boolean;
  startPolling: () => void;
  stopPolling: () => void;
  submitApproval: (approvalId: string, approved: boolean, signedTxHex?: string, rejectionReason?: string) => Promise<boolean>;
  createMockRequest: () => Promise<boolean>;
}

export const useApprovalPolling = (interval = 2000): UseApprovalPollingResult => {
  const [approvalRequests, setApprovalRequests] = useState<ApprovalRequest[]>([]);
  const [isPolling, setIsPolling] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const poll = useCallback(async () => {
    try {
      const result = await apiService.pollApprovalRequests();
      
      if (result.has_requests && result.requests.length > 0) {
        console.log(' New approval requests received:', result.requests);
        setApprovalRequests(result.requests);
      } else {
        // Clear requests if no active ones
        setApprovalRequests(prev => prev.length > 0 ? [] : prev);
      }
    } catch (error) {
      console.error('Error polling approval requests:', error);
    }
  }, []);

  const startPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    setIsPolling(true);
    console.log(' Started approval polling every', interval, 'ms');
    
    // Poll immediately, then set interval
    poll();
    intervalRef.current = setInterval(poll, interval);
  }, [poll, interval]);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsPolling(false);
    console.log(' Stopped approval polling');
  }, []);

  const submitApproval = useCallback(async (
    approvalId: string, 
    approved: boolean, 
    signedTxHex?: string, 
    rejectionReason?: string
  ): Promise<boolean> => {
    try {
      console.log(` Submitting approval response: ${approved ? 'APPROVED' : 'REJECTED'}`, {
        approvalId,
        approved,
        hasSignedTx: !!signedTxHex,
        rejectionReason
      });

      const result = await apiService.submitApprovalResponse({
        approval_id: approvalId,
        approved,
        signed_transaction_hex: signedTxHex,
        rejection_reason: rejectionReason
      });

      if (result.success) {
        console.log(' Approval response submitted successfully');
        // Remove the processed request from local state immediately
        setApprovalRequests(prev => prev.filter(req => req.approval_id !== approvalId));
        
        // Stop polling temporarily to prevent refetching the same request
        // The backend needs time to mark it as processed
        if (intervalRef.current) {
          console.log(' Temporarily pausing polling to allow backend processing');
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        
        // Resume polling after a delay to allow backend to process
        const resumePolling = () => {
          console.log(' Resuming polling after approval processing delay');
          intervalRef.current = setInterval(poll, interval);
        };
        
        setTimeout(resumePolling, 2000); // 2 second delay
        
        return true;
      } else {
        console.error(' Failed to submit approval response:', result.error);
        return false;
      }
    } catch (error) {
      console.error(' Error submitting approval response:', error);
      return false;
    }
  }, []);

  const createMockRequest = useCallback(async (): Promise<boolean> => {
    try {
      console.log(' Creating mock approval request...');
      const result = await apiService.createMockApprovalRequest();
      
      if (result.success) {
        console.log(' Mock approval request created:', result.approval_id);
        // Trigger a poll to get the new request
        setTimeout(poll, 500);
        return true;
      } else {
        console.error(' Failed to create mock request:', result.error);
        return false;
      }
    } catch (error) {
      console.error(' Error creating mock request:', error);
      return false;
    }
  }, [poll]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return {
    approvalRequests,
    hasActiveRequest: approvalRequests.length > 0,
    isPolling,
    startPolling,
    stopPolling,
    submitApproval,
    createMockRequest
  };
};