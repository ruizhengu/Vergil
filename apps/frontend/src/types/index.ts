// Wallet state
export interface WalletState {
  connected: boolean;
  address: string | null;
  network: 'mainnet' | 'sepolia' | 'base';
}

// Agent state
export type AgentStatus =
  | 'online'
  | 'reasoning'
  | 'executing'
  | 'awaiting_signature'
  | 'broadcasting'
  | 'guardrail_active'
  | 'error';

export interface AgentState {
  status: AgentStatus;
  currentNode: string | null;
  errorMessage?: string;
}

// Deployment flow state
export type DeploymentStage =
  | 'idle'
  | 'review'
  | 'preparing'
  | 'signing'
  | 'broadcasting'
  | 'success'
  | 'failed';

export interface DeploymentState {
  stage: DeploymentStage;
  contractName: string;
  contractType: 'ERC-20' | 'ERC-721' | 'ERC-1155' | 'Custom';
  estimatedGas: string;
  txHash: string | null;
  contractAddress: string | null;
  errorMessage?: string;
}

// Workflow nodes
export type NodeStatus = 'pending' | 'active' | 'done' | 'error';

export interface WorkflowNode {
  id: string;
  name: string;
  label: string;
  status: NodeStatus;
  duration?: number;
  startTime?: number;
  errorMessage?: string;
}

// Security validation layers
export type SecurityStatus = 'pass' | 'reviewing' | 'flagged' | 'blocked';

export interface SecurityLayer {
  id: string;
  name: string;
  label: string;
  status: SecurityStatus;
  description: string;
}

// Contract
export interface Contract {
  id: string;
  name: string;
  type: 'ERC-20' | 'ERC-721' | 'ERC-1155' | 'Custom';
  address: string;
  txHash: string;
  deployTime: string;
  network: string;
  status: 'deployed' | 'pending' | 'failed';
}

// Chat message
export type MessageType =
  | 'text'
  | 'code'
  | 'tool_call'
  | 'deployment_request'
  | 'error';

export interface ChatMessage {
  id: string;
  type: MessageType;
  content: string;
  code?: string;
  language?: string;
  toolName?: string;
  toolParams?: Record<string, unknown>;
  timestamp: number;
  isUser: boolean;
}

// Nav item
export interface NavItem {
  id: string;
  label: string;
  icon: string;
  badge?: number;
  href: string;
}

// Feature card
export interface FeatureCard {
  id: string;
  title: string;
  description: string;
  status: string;
  statusColor: 'blue' | 'green' | 'gold';
}

// Quick action
export interface QuickAction {
  id: string;
  label: string;
  icon: string;
  prompt: string;
}

// Trace event for agent tracing display
export interface TraceEvent {
  id: string;
  timestamp: Date;
  message: string;
  status: 'pending' | 'running' | 'completed' | 'error';
}
