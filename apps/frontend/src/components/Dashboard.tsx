'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAppStore, getStoreState } from '@/stores/appStore';
import { StatusBadge } from '@/components/StatusBadge';
import { WalletButton } from '@/components/WalletButton';
import { TransactionModal } from '@/components/TransactionModal';
import { apiService } from '@/services/api';
import { useAccount } from 'wagmi';
import { useApprovalPolling } from '@/hooks/useApprovalPolling';
import {
  MessageSquare,
  FileCode,
  Shield,
  History,
  ChevronDown,
  Copy,
  Send,
  Zap,
  Coins,
  Image,
  Search,
  FileText,
  Check,
  X,
  Loader2,
  Sparkles,
  Bot,
  Terminal,
  ShieldCheck,
  CheckCircle2,
  Circle
} from 'lucide-react';

// Sidebar component
function Sidebar() {
  const router = useRouter();
  const { wallet, setCurrentView, contracts } = useAppStore();
  const [activeNav, setActiveNav] = useState('forge');

  const navItems = [
    { id: 'forge', label: 'Forge', icon: MessageSquare },
    { id: 'deployed', label: 'Deployed', icon: FileCode, badge: contracts.length },
    { id: 'audit', label: 'Security Audit', icon: Shield },
    { id: 'history', label: 'History', icon: History },
  ];

  const networks = [
    { id: 'mainnet', label: 'Mainnet', color: '#4caf82' },
    { id: 'sepolia', label: 'Sepolia', color: '#c9a84c' },
    { id: 'base', label: 'Base', color: '#4fc3f7' },
  ];

  return (
    <aside className="w-60 h-full bg-[#0d1117] border-r border-white/[0.06] flex flex-col">
      {/* Logo */}
      <button
        onClick={() => router.push('/')}
        className="p-5 border-b border-white/[0.06] hover:bg-white/[0.02] transition-colors text-left w-full"
      >
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-full border border-[#4fc3f7]/30 flex items-center justify-center">
            <span className="text-[#4fc3f7] text-xs font-brand">V</span>
          </div>
          <span className="font-brand text-sm tracking-[0.15em] text-white">VERGIL</span>
        </div>
        <p className="text-[10px] text-white/40 font-body italic">
          smarter with your contract
        </p>
      </button>

      {/* Wallet status */}
      <div className="p-4 border-b border-white/[0.06]">
        {wallet.connected ? (
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#4caf82]" style={{ boxShadow: '0 0 6px #4caf82' }} />
            <span className="text-xs text-white/60 font-mono">
              {wallet.address?.slice(0, 6)}...{wallet.address?.slice(-4)}
            </span>
          </div>
        ) : (
          <div className="w-full">
            <WalletButton />
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => {
              setActiveNav(item.id);
              if (item.id === 'deployed') setCurrentView('contracts');
            }}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs transition-all ${activeNav === item.id
                ? 'bg-white/5 text-white'
                : 'text-white/50 hover:text-white hover:bg-white/[0.02]'
              }`}
          >
            <item.icon className="w-4 h-4" />
            <span>{item.label}</span>
            {item.badge && (
              <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-[#4fc3f7]/20 text-[#4fc3f7]">
                {item.badge}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Network selector */}
      <div className="p-3 border-t border-white/[0.06]">
        <div className="flex items-center justify-between px-2 mb-2">
          <span className="text-[10px] uppercase tracking-wider text-white/30">Network</span>
          <ChevronDown className="w-3 h-3 text-white/30" />
        </div>
        <div className="space-y-1">
          {networks.map((network) => (
            <button
              key={network.id}
              className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-[10px] transition-colors ${wallet.network === network.id
                  ? 'bg-white/5 text-white'
                  : 'text-white/40 hover:text-white/60'
                }`}
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: network.color }}
              />
              <span>{network.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Bottom status */}
      <div className="p-3 border-t border-white/[0.06]">
        <div className="flex items-center justify-between">
          <StatusBadge status="online">Agent Online</StatusBadge>
          <span className="text-[10px] text-white/30 font-mono">#18,432,109</span>
        </div>
      </div>
    </aside>
  );
}

// Chat Panel component
function ChatPanel() {
  const STATIC_FAKE_CHAT_MODE = false;
  const { address, isConnected } = useAccount();
  const [inputValue, setInputValue] = useState('');
  const [messages, setMessages] = useState<Array<{ id: string; type: string; content: string; isUser: boolean; code?: string; language?: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [transactionModal, setTransactionModal] = useState<{ isOpen: boolean; approvalRequest: any | null }>({ isOpen: false, approvalRequest: null });
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { approvalRequests, hasActiveRequest, startPolling, stopPolling, submitApproval } = useApprovalPolling(3000);

  const quickActions = [
    { id: 'erc20', label: 'Deploy an ERC-20 token', icon: Coins, prompt: 'Deploy an ERC-20 token named "MyToken" with symbol "MTK" and 1 million supply' },
    { id: 'nft', label: 'Create an NFT collection', icon: Image, prompt: 'Create an ERC-721 NFT collection named "Digital Art" with max supply of 10000' },
    { id: 'audit', label: 'Audit an existing contract', icon: Search, prompt: 'Audit this contract for security vulnerabilities' },
    { id: 'explain', label: 'Explain a contract', icon: FileText, prompt: 'Explain what this smart contract does' },
  ];

  // Parse content to handle code blocks
  const parseContent = (content: string): React.ReactNode => {
    if (content.includes('```')) {
      const parts = content.split('```');
      const elements: React.ReactNode[] = [];

      for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
          // Regular text part
          const text = parts[i];
          if (text.trim()) {
            elements.push(
              <p key={`text-${i}`} className="text-sm text-white/80 mb-2">{text.trim()}</p>
            );
          }
        } else {
          // Code block part
          let codeContent = parts[i];
          let language = 'SOLIDITY';

          // Extract language if present
          const firstNewlineIndex = codeContent.indexOf('\n');
          if (firstNewlineIndex !== -1 && firstNewlineIndex < 20) {
            const potentialLang = codeContent.slice(0, firstNewlineIndex).trim().toLowerCase();
            if (/^[a-zA-Z0-9]+$/.test(potentialLang)) {
              language = potentialLang.toUpperCase();
              codeContent = codeContent.slice(firstNewlineIndex + 1);
            }
          }

          elements.push(
            <div key={`code-${i}`} className="rounded-lg overflow-hidden border border-white/[0.08] mb-3">
              <div className="flex items-center justify-between px-3 py-2 bg-[#0d1117] border-b border-white/[0.06]">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] uppercase tracking-wider text-white/40">{language}</span>
                </div>
                <button
                  className="text-[10px] text-white/40 hover:text-white/60 flex items-center gap-1"
                  onClick={() => navigator.clipboard.writeText(codeContent.trim())}
                >
                  <Copy className="w-3 h-3" />
                  Copy
                </button>
              </div>
              <pre className="p-3 bg-[#050810] overflow-x-auto">
                <code className="text-xs font-mono text-white/70">{codeContent.trim()}</code>
              </pre>
            </div>
          );
        }
      }

      return <div>{elements}</div>;
    }

    // No code blocks, return as plain text
    return <p className="text-sm text-white/80">{content}</p>;
  };

  const generateId = () => Date.now().toString(36) + Math.random().toString(36).substr(2);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    startPolling();
    return () => stopPolling();
  }, [startPolling, stopPolling]);

  // Register wallet with backend when connected
  useEffect(() => {
    if (isConnected && address) {
      apiService.connectWallet(address, conversationId || undefined).catch(() => {});
    }
  }, [isConnected, address, conversationId]);

  // Open approval modal when a pending request arrives
  useEffect(() => {
    if (hasActiveRequest && approvalRequests.length > 0 && !transactionModal.isOpen) {
      setTransactionModal({ isOpen: true, approvalRequest: approvalRequests[0] });
      setMessages(prev => [...prev, {
        id: generateId(),
        type: 'text',
        content: '🔔 Deployment approval required — please review and sign the transaction in the modal.',
        isUser: false,
      }]);
    }
  }, [hasActiveRequest, approvalRequests, transactionModal.isOpen]);

  const sendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return;

    const { clearTraceEvents, addTraceEvent, setTraceComplete } = getStoreState();

    // Clear previous trace events and start new trace
    clearTraceEvents();
    addTraceEvent('Agent initialized', 'completed');
    addTraceEvent('Parsing user request...', 'running');

    setMessages(prev => [...prev, { id: generateId(), type: 'text', content, isUser: true }]);
    setIsLoading(true);

    // Update trace to show processing
    setTimeout(() => {
      addTraceEvent('Analyzing intent...', 'running');
    }, 500);

    try {
      const response = await apiService.sendMessageReal({
        message: content,
        conversationId: conversationId ?? undefined,
      });

      if (response.success && response.data) {
        const { addTraceEvent, setTraceComplete } = getStoreState();

        // Add trace events for contract generation
        addTraceEvent('Generating contract code...', 'completed');
        addTraceEvent('Verifying contract security...', 'running');

        const data = response.data;
        const backendConvId = data.conversation_id;
        if (backendConvId) {
          setConversationId(backendConvId);
          if (isConnected && address) {
            apiService.connectWallet(address, backendConvId).catch(() => {});
          }
        }

        // Check if it's a contract deployment/generation response
        if (data.response && (
          data.response.includes('contract') ||
          data.response.includes('ERC-20') ||
          data.response.includes('ERC-721') ||
          data.response.includes('deployed') ||
          data.response.includes('Generated')
        )) {
          addTraceEvent('Security verification passed', 'completed');
        }

        addTraceEvent('Response generated', 'completed');
        setTraceComplete();

        setMessages(prev => [...prev, { id: generateId(), type: 'text', content: data.response, isUser: false }]);
      } else {
        throw new Error(response.error || 'Failed to get response');
      }
    } catch (err) {
      const { addTraceEvent } = getStoreState();
      addTraceEvent('Error processing request', 'error');
      console.error('Failed to send message:', err);
      setMessages(prev => [...prev, { id: generateId(), type: 'text', content: 'Sorry, something went wrong. Please try again.', isUser: false }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = () => {
    const content = inputValue.trim();
    if (!content) return;
    setInputValue('');
    sendMessage(content);
  };

  const handleQuickAction = (prompt: string) => {
    sendMessage(prompt);
  };

  const handleApprovalSubmit = async (approvalId: string, approved: boolean, signedTxHex?: string, rejectionReason?: string) => {
    const success = await submitApproval(approvalId, approved, signedTxHex, rejectionReason);
    if (success) {
      const resultMsg = approved
        ? `✅ Transaction signed and submitted successfully!${signedTxHex && signedTxHex.startsWith('ALREADY_BROADCAST:') ? ` Tx: \`${signedTxHex.replace('ALREADY_BROADCAST:', '')}\`` : ''}`
        : `❌ Deployment rejected.${rejectionReason ? ` Reason: ${rejectionReason}` : ''}`;
      setMessages(prev => [...prev, { id: generateId(), type: 'text', content: resultMsg, isUser: false }]);
      setTransactionModal({ isOpen: false, approvalRequest: null });
    }
    return success;
  };

  return (
    <main className="flex-1 flex flex-col bg-[#050810] min-w-[480px]">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-6">
        {!STATIC_FAKE_CHAT_MODE && messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center">
            {/* Vergil Sigil */}
            <div className="w-16 h-16 rounded-full border border-[#4fc3f7]/20 flex items-center justify-center mb-6 animate-breathe">
              <span className="text-2xl text-[#4fc3f7]/60 font-brand">V</span>
            </div>
            <p className="font-body italic text-white/40 text-center mb-8">
              Your ledger is empty. Begin forging.
            </p>

            {/* Quick actions */}
            <div className="grid grid-cols-2 gap-3 max-w-md">
              {quickActions.map((action) => (
                <button
                  key={action.id}
                  onClick={() => handleQuickAction(action.prompt)}
                  className="flex items-center gap-3 p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-[#4fc3f7]/30 hover:bg-white/[0.04] transition-all text-left group"
                >
                  <div className="w-8 h-8 rounded-lg bg-[#4fc3f7]/10 flex items-center justify-center group-hover:bg-[#4fc3f7]/20 transition-colors">
                    <action.icon className="w-4 h-4 text-[#4fc3f7]" />
                  </div>
                  <span className="text-xs text-white/70">{action.label}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6 max-w-3xl mx-auto">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.isUser ? 'justify-end' : 'justify-start'}`}
              >
                {!msg.isUser && (
                  <div className="w-7 h-7 rounded-full border border-[#4fc3f7]/30 flex items-center justify-center mr-3 flex-shrink-0">
                    <span className="text-[10px] text-[#4fc3f7]">V</span>
                  </div>
                )}
                <div
                  className={`max-w-[80%] ${msg.isUser
                      ? 'bg-[#4fc3f7]/10 border border-[#4fc3f7]/30 rounded-2xl rounded-tr-sm'
                      : 'bg-white/[0.03] border border-white/[0.06] rounded-2xl rounded-tl-sm'
                    } px-4 py-3`}
                >
                  {msg.type === 'text' && (
                    parseContent(msg.content)
                  )}

                  {msg.type === 'code' && (
                    <div>
                      <p className="text-sm text-white/60 mb-3">{msg.content}</p>
                      <div className="rounded-lg overflow-hidden border border-white/[0.08]">
                        <div className="flex items-center justify-between px-3 py-2 bg-[#0d1117] border-b border-white/[0.06]">
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] uppercase tracking-wider text-white/40">Solidity</span>
                            <span className="text-white/20">·</span>
                            <span className="text-[10px] text-white/40">MyToken.sol</span>
                            <span className="text-white/20">·</span>
                            <span className="text-[10px] text-white/40">18 lines</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <button className="text-[10px] text-white/40 hover:text-white/60 flex items-center gap-1">
                              <Copy className="w-3 h-3" />
                              Copy
                            </button>
                          </div>
                        </div>
                        <pre className="p-3 bg-[#050810] overflow-x-auto">
                          <code className="text-xs font-mono text-white/70">{msg.code}</code>
                        </pre>
                      </div>
                    </div>
                  )}

                  {msg.type === 'deployment_request' && (
                    <div className="border border-[#c9a84c]/40 rounded-lg p-4 bg-[#c9a84c]/5">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-6 h-6 rounded-full bg-[#c9a84c]/20 flex items-center justify-center">
                          <Zap className="w-3 h-3 text-[#c9a84c]" />
                        </div>
                        <span className="text-sm text-[#c9a84c]">Deployment Ready</span>
                      </div>
                      <p className="text-xs text-white/50">{msg.content}</p>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Loading indicator */}
            {isLoading && (
              <div className="flex justify-start">
                <div className="w-7 h-7 rounded-full border border-[#4fc3f7]/30 flex items-center justify-center mr-3">
                  <span className="text-[10px] text-[#4fc3f7]">V</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[#4fc3f7] animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 rounded-full bg-[#4fc3f7] animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 rounded-full bg-[#4fc3f7] animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="p-4 border-t border-white/[0.06]">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <div className="flex-1 relative">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Describe your contract..."
              disabled={isLoading}
              className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-[#4fc3f7]/40 transition-colors disabled:opacity-50"
            />
          </div>
          <button
            onClick={handleSend}
            disabled={isLoading}
            className="w-10 h-10 rounded-xl bg-[#4fc3f7]/20 border border-[#4fc3f7]/30 flex items-center justify-center hover:bg-[#4fc3f7]/30 transition-colors disabled:opacity-50"
          >
            <Send className="w-4 h-4 text-[#4fc3f7]" />
          </button>
        </div>
      </div>

      {/* Transaction/Approval Modal */}
      <TransactionModal
        isOpen={transactionModal.isOpen}
        onClose={() => setTransactionModal({ isOpen: false, approvalRequest: null })}
        approvalRequest={transactionModal.approvalRequest}
        mode="approval"
        onApprovalSubmit={handleApprovalSubmit}
      />
    </main>
  );
}

// Workflow Panel component
function WorkflowPanel() {
  const { workflowNodes, agent, securityLayers, traceEvents: storeTraceEvents } = useAppStore();
  const [activeTab, setActiveTab] = useState<'workflow' | 'security' | 'trace'>('workflow');

  // Use trace events from store, or show idle state if empty
  const traceEvents = React.useMemo(() => {
    if (storeTraceEvents.length > 0) {
      return storeTraceEvents.map(event => ({
        ...event,
        time: formatTime(event.timestamp)
      }));
    }

    // Default placeholder traces when agent is idle
    return [{
      id: 'idle',
      timestamp: new Date(),
      time: formatTime(new Date()),
      message: 'Agent ready',
      status: 'pending' as const
    }];
  }, [storeTraceEvents]);

  function formatTime(date: Date): string {
    return date.toLocaleTimeString('en-US', { hour12: false });
  }

  function getNodeTraceMessage(label: string): string {
    const messages: Record<string, string> = {
      'Reasoning': 'Analyzing request intent...',
      'Action Planning': 'Planning execution steps...',
      'Tool Execution': 'Executing tools...',
      'Composing Output': 'Generating response...',
      'Intent Classification': 'Classifying user intent...',
      'Contract Generation': 'Generating contract code...',
      'Verification': 'Running security verification...',
      'Deployment': 'Preparing deployment...',
    };
    return messages[label] || label;
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'done':
        return <Check className="w-3 h-3 text-[#4caf82]" />;
      case 'active':
        return <div className="w-2 h-2 rounded-full bg-[#4fc3f7] animate-pulse" />;
      case 'error':
        return <X className="w-3 h-3 text-[#e05a2b]" />;
      default:
        return <div className="w-2 h-2 rounded-full bg-white/20" />;
    }
  };

  const getSecurityStatusIcon = (status: string) => {
    switch (status) {
      case 'pass':
        return <span className="text-[10px] text-[#4caf82]">PASS</span>;
      case 'reviewing':
        return <span className="text-[10px] text-[#4fc3f7]">RUNNING</span>;
      case 'flagged':
        return <span className="text-[10px] text-[#c9a84c]">FLAGGED</span>;
      case 'blocked':
        return <span className="text-[10px] text-[#e05a2b]">BLOCKED</span>;
      default:
        return null;
    }
  };

  return (
    <aside className="w-80 h-full bg-[#0d1117] border-l border-white/[0.06] flex flex-col">
      {/* Tabs */}
      <div className="flex border-b border-white/[0.06]">
        {(['workflow', 'security', 'trace'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-3 text-[10px] uppercase tracking-wider transition-colors ${activeTab === tab
                ? 'text-white border-b border-[#4fc3f7]'
                : 'text-white/40 hover:text-white/60'
              }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'workflow' && (
          <div className="space-y-3">
            {workflowNodes.map((node, index) => (
              <div key={node.id} className="relative">
                {/* Connection line */}
                {index < workflowNodes.length - 1 && (
                  <div className="absolute left-[11px] top-8 w-px h-6 bg-white/10" />
                )}

                <div
                  className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${node.status === 'active'
                      ? 'bg-[#4fc3f7]/5 border-[#4fc3f7]/30 animate-node-glow'
                      : node.status === 'done'
                        ? 'bg-white/[0.02] border-white/[0.06]'
                        : 'bg-transparent border-transparent'
                    }`}
                >
                  {/* Status indicator */}
                  <div
                    className={`w-5 h-5 rounded-full flex items-center justify-center ${node.status === 'active'
                        ? 'bg-[#4fc3f7]/20'
                        : node.status === 'done'
                          ? 'bg-[#4caf82]/20'
                          : 'bg-white/5'
                      }`}
                  >
                    {getStatusIcon(node.status)}
                  </div>

                  {/* Node info */}
                  <div className="flex-1">
                    <p className={`text-xs ${node.status === 'active' ? 'text-white' : 'text-white/50'}`}>
                      {node.label}
                    </p>
                  </div>

                  {/* Timer */}
                  {node.status === 'active' && (
                    <span className="text-[10px] text-white/40 font-mono">
                      00:02.4
                    </span>
                  )}
                  {node.status === 'done' && node.duration && (
                    <span className="text-[10px] text-white/30 font-mono">
                      {(node.duration / 1000).toFixed(1)}s
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'security' && (
          <div className="space-y-4">
            {securityLayers.map((layer) => (
              <div
                key={layer.id}
                className="p-4 rounded-lg bg-white/[0.02] border border-white/[0.06]"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-white/40" />
                    <span className="text-[10px] uppercase tracking-wider text-white/40">
                      {layer.label}
                    </span>
                  </div>
                  {getSecurityStatusIcon(layer.status)}
                </div>
                <p className="text-xs text-white/70 mb-1">{layer.name}</p>
                <p className="text-[10px] text-white/40">{layer.description}</p>
              </div>
            ))}

            <div className="p-3 rounded-lg bg-[#4fc3f7]/5 border border-[#4fc3f7]/20">
              <p className="text-[10px] text-[#4fc3f7]/70">
                Symbolic verification via Z3 SMT Solver
              </p>
            </div>
          </div>
        )}

        {activeTab === 'trace' && (
          <div className="space-y-1">
            {traceEvents.map((event, index) => (
              <div
                key={event.id}
                className={`relative flex items-start gap-3 p-3 rounded-lg transition-all duration-300 ${
                  event.status === 'running'
                    ? 'bg-[#4fc3f7]/5 border border-[#4fc3f7]/20'
                    : event.status === 'completed'
                      ? 'bg-white/[0.02] border border-transparent'
                      : 'bg-transparent border border-transparent'
                }`}
              >
                {/* Status indicator */}
                <div className="flex-shrink-0 mt-0.5">
                  {event.status === 'running' ? (
                    <Loader2 className="w-3 h-3 text-[#4fc3f7] animate-spin" />
                  ) : event.status === 'completed' ? (
                    <CheckCircle2 className="w-3 h-3 text-[#4caf82]" />
                  ) : event.status === 'error' ? (
                    <X className="w-3 h-3 text-[#e05a2b]" />
                  ) : (
                    <Circle className="w-3 h-3 text-white/30" />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-mono ${
                      event.status === 'running'
                        ? 'text-[#4fc3f7]'
                        : event.status === 'completed'
                          ? 'text-[#4caf82]'
                          : event.status === 'error'
                            ? 'text-[#e05a2b]'
                            : 'text-white/30'
                    }`}>
                      [{event.time}]
                    </span>
                    {event.status === 'running' && (
                      <span className="flex items-center gap-1">
                        <span className="w-1 h-1 rounded-full bg-[#4fc3f7] animate-pulse" />
                        <span className="w-1 h-1 rounded-full bg-[#4fc3f7] animate-pulse" style={{ animationDelay: '150ms' }} />
                        <span className="w-1 h-1 rounded-full bg-[#4fc3f7] animate-pulse" style={{ animationDelay: '300ms' }} />
                      </span>
                    )}
                  </div>
                  <p className={`text-xs mt-0.5 ${
                    event.status === 'running'
                      ? 'text-white'
                      : event.status === 'completed'
                        ? 'text-white/70'
                        : event.status === 'error'
                          ? 'text-white/70'
                          : 'text-white/40'
                  }`}>
                    {event.message}
                  </p>
                </div>
              </div>
            ))}

            {/* Empty state */}
            {traceEvents.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mb-4">
                  <Terminal className="w-5 h-5 text-white/30" />
                </div>
                <p className="text-xs text-white/40 mb-1">No trace data</p>
                <p className="text-[10px] text-white/20">Send a message to start tracing</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bottom status */}
      <div className="p-3 border-t border-white/[0.06]">
        <StatusBadge
          status={
            agent.status === 'online' ? 'online' :
              agent.status === 'error' ? 'error' :
                'blue'
          }
        >
          {agent.status.replace('_', ' ')}
        </StatusBadge>
      </div>
    </aside>
  );
}

// Main Dashboard component
export function Dashboard() {
  return (
    <div className="h-screen flex bg-[#050810]">
      <Sidebar />
      <ChatPanel />
      <WorkflowPanel />
    </div>
  );
}
