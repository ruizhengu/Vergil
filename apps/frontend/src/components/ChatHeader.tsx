import React, { useState, useEffect } from 'react';
import { Bot, Settings, RefreshCw, Wifi, WifiOff } from 'lucide-react';
import { WalletButton } from './WalletButton';

interface ChatHeaderProps {
  onNewChat: () => void;
  conversationId: string | null;
}

const ChatHeader: React.FC<ChatHeaderProps> = ({ onNewChat, conversationId }) => {
  const [backendStatus, setBackendStatus] = useState<'connected' | 'disconnected' | 'checking'>('checking');

  useEffect(() => {
    // Check backend connectivity on mount
    const checkBackendHealth = async () => {
      try {
        const response = await fetch('/api/health');
        const data = await response.json();
        setBackendStatus(data.success ? 'connected' : 'disconnected');
      } catch (error) {
        setBackendStatus('disconnected');
      }
    };

    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="chat-header">
      <div className="header-left">
        <div className="header-avatar">
          <Bot size={24} />
        </div>
        <div className="header-info">
          <h1>Smart Contract Assistant</h1>
          <p>
            {conversationId ? `Chat ${conversationId.slice(0, 8)}...` : 'Ready to help with smart contracts'}
          </p>
        </div>
      </div>
      
      <div className="header-actions">
        <WalletButton />
        <div className="connection-status" title={`Backend ${backendStatus}`}>
          {backendStatus === 'connected' ? (
            <Wifi size={16} style={{ color: '#10b981' }} />
          ) : backendStatus === 'disconnected' ? (
            <WifiOff size={16} style={{ color: '#ef4444' }} />
          ) : (
            <div style={{ width: 16, height: 16, background: '#6b7280', borderRadius: '50%', animation: 'pulse 2s infinite' }} />
          )}
        </div>
        <button
          onClick={onNewChat}
          className="header-button"
          title="New Chat"
        >
          <RefreshCw size={20} />
        </button>
        <button
          className="header-button"
          title="Settings"
        >
          <Settings size={20} />
        </button>
      </div>
    </div>
  );
};

export default ChatHeader;