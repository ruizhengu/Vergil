'use client';

import { useState, useEffect, useRef } from 'react';
import { useAppStore } from '@/stores/appStore';
import { StatusBadge } from '@/components/StatusBadge';
import { WalletButton } from '@/components/WalletButton';
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
  X
} from 'lucide-react';

// Sidebar component
function Sidebar() {
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
      <div className="p-5 border-b border-white/[0.06]">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-full border border-[#4fc3f7]/30 flex items-center justify-center">
            <span className="text-[#4fc3f7] text-xs font-brand">V</span>
          </div>
          <span className="font-brand text-sm tracking-[0.15em] text-white">VERGIL</span>
        </div>
        <p className="text-[10px] text-white/40 font-body italic">
          smarter with your contract
        </p>
      </div>

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
  const { messages, addMessage, agent, openDeploymentModal } = useAppStore();
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const quickActions = [
    { id: 'erc20', label: 'Deploy an ERC-20 token', icon: Coins, prompt: 'Deploy an ERC-20 token named "MyToken" with symbol "MTK" and 1 million supply' },
    { id: 'nft', label: 'Create an NFT collection', icon: Image, prompt: 'Create an ERC-721 NFT collection named "Digital Art" with max supply of 10000' },
    { id: 'audit', label: 'Audit an existing contract', icon: Search, prompt: 'Audit this contract for security vulnerabilities' },
    { id: 'explain', label: 'Explain a contract', icon: FileText, prompt: 'Explain what this smart contract does' },
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = () => {
    if (!inputValue.trim()) return;

    addMessage({
      type: 'text',
      content: inputValue,
      isUser: true,
    });

    setInputValue('');

    // Simulate AI response
    setTimeout(() => {
      addMessage({
        type: 'code',
        content: 'I\'ll help you deploy an ERC-20 token. Here\'s the generated contract:',
        code: `// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract MyToken is ERC20, Ownable {
    constructor() ERC20("MyToken", "MTK") {
        _mint(msg.sender, 1000000 * 10 ** decimals());
    }
}`,
        language: 'solidity',
        isUser: false,
      });
    }, 1500);
  };

  const handleQuickAction = (prompt: string) => {
    addMessage({
      type: 'text',
      content: prompt,
      isUser: true,
    });

    setTimeout(() => {
      addMessage({
        type: 'deployment_request',
        content: 'Contract generated and validated. Ready to deploy?',
        isUser: false,
      });
    }, 2000);
  };

  return (
    <main className="flex-1 flex flex-col bg-[#050810] min-w-[480px]">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-6">
        {messages.length === 0 ? (
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
                    <p className="text-sm text-white/80">{msg.content}</p>
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
                      <p className="text-xs text-white/50 mb-4">{msg.content}</p>
                      <button
                        onClick={openDeploymentModal}
                        className="w-full capsule-btn-gold text-[10px] py-2"
                      >
                        Commit to Chain
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Agent thinking */}
            {agent.status === 'reasoning' && (
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
              className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-[#4fc3f7]/40 transition-colors"
            />
          </div>
          <button
            onClick={handleSend}
            className="w-10 h-10 rounded-xl bg-[#4fc3f7]/20 border border-[#4fc3f7]/30 flex items-center justify-center hover:bg-[#4fc3f7]/30 transition-colors"
          >
            <Send className="w-4 h-4 text-[#4fc3f7]" />
          </button>
        </div>
      </div>
    </main>
  );
}

// Workflow Panel component
function WorkflowPanel() {
  const { workflowNodes, agent, securityLayers } = useAppStore();
  const [activeTab, setActiveTab] = useState<'workflow' | 'security' | 'trace'>('workflow');

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
          <div className="space-y-2">
            <div className="text-[10px] text-white/30 font-mono">
              <span className="text-[#4fc3f7]">[10:32:15]</span>
              <span className="ml-2">Agent initialized</span>
            </div>
            <div className="text-[10px] text-white/30 font-mono">
              <span className="text-[#4fc3f7]">[10:32:16]</span>
              <span className="ml-2">Parsing natural language...</span>
            </div>
            <div className="text-[10px] text-white/30 font-mono">
              <span className="text-[#4fc3f7]">[10:32:18]</span>
              <span className="ml-2">Generating contract template</span>
            </div>
            <div className="text-[10px] text-white/30 font-mono">
              <span className="text-[#4fc3f7]">[10:32:21]</span>
              <span className="ml-2">Running security checks...</span>
            </div>
            <div className="text-[10px] text-white/30 font-mono">
              <span className="text-[#4caf82]">[10:32:25]</span>
              <span className="ml-2 text-[#4caf82]">All checks passed</span>
            </div>
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
