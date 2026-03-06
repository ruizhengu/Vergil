import { create } from 'zustand';
import type {
  WalletState,
  AgentState,
  DeploymentState,
  WorkflowNode,
  SecurityLayer,
  Contract,
  ChatMessage,
  AgentStatus,
  DeploymentStage,
  NodeStatus,
  TraceEvent,
} from '@/types';

interface AppState {
  // Wallet state
  wallet: WalletState;
  setWallet: (wallet: Partial<WalletState>) => void;
  connectWallet: (address: string) => void;
  disconnectWallet: () => void;

  // Agent state
  agent: AgentState;
  setAgentStatus: (status: AgentStatus, currentNode?: string) => void;
  setAgentError: (errorMessage: string) => void;

  // Deployment flow
  deployment: DeploymentState;
  setDeploymentStage: (stage: DeploymentStage) => void;
  setDeploymentData: (data: Partial<DeploymentState>) => void;
  resetDeployment: () => void;

  // Workflow nodes
  workflowNodes: WorkflowNode[];
  setNodeStatus: (nodeId: string, status: NodeStatus) => void;
  activateNode: (nodeId: string) => void;
  completeNode: (nodeId: string) => void;
  resetWorkflow: () => void;

  // Security validation layers
  securityLayers: SecurityLayer[];
  setSecurityStatus: (layerId: string, status: SecurityLayer['status']) => void;

  // Contract list
  contracts: Contract[];
  addContract: (contract: Contract) => void;
  updateContractStatus: (id: string, status: Contract['status']) => void;

  // Chat messages
  messages: ChatMessage[];
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  clearMessages: () => void;

  // UI state
  ui: {
    sidebarOpen: boolean;
    workflowPanelOpen: boolean;
    deploymentModalOpen: boolean;
    onboardingOpen: boolean;
    onboardingStep: number;
    currentView: 'landing' | 'dashboard' | 'contracts';
  };
  toggleSidebar: () => void;
  toggleWorkflowPanel: () => void;
  openDeploymentModal: () => void;
  closeDeploymentModal: () => void;
  openOnboarding: () => void;
  closeOnboarding: () => void;
  setOnboardingStep: (step: number) => void;
  setCurrentView: (view: AppState['ui']['currentView']) => void;

  // Trace events for Trace tab
  traceEvents: TraceEvent[];
  addTraceEvent: (message: string, status: TraceEvent['status']) => void;
  clearTraceEvents: () => void;
  setTraceComplete: () => void;
}

const initialWorkflowNodes: WorkflowNode[] = [
  { id: 'reasoning', name: 'reasoning_node', label: 'Reasoning', status: 'pending' },
  { id: 'action', name: 'action_node', label: 'Action Planning', status: 'pending' },
  { id: 'tool', name: 'tool_execution_node', label: 'Tool Execution', status: 'pending' },
  { id: 'output', name: 'output_node', label: 'Composing Output', status: 'pending' },
];

const initialSecurityLayers: SecurityLayer[] = [
  { id: 'checker', name: 'CHECKER', label: 'Layer 1', status: 'reviewing', description: 'Soft validation, logic vulnerabilities' },
  { id: 'compliance', name: 'COMPLIANCE', label: 'Layer 2', status: 'reviewing', description: 'Hard-coded compliance red lines' },
  { id: 'guardrail', name: 'GUARDRAIL · Z3', label: 'Layer 3', status: 'reviewing', description: 'Symbolic verification via Z3 SMT Solver' },
];

const initialContracts: Contract[] = [
  {
    id: '1',
    name: 'MyToken',
    type: 'ERC-20',
    address: '0x4Fc3123456789012345678901234567890F7A2',
    txHash: '0xabc123...',
    deployTime: '2024-03-04T10:30:00Z',
    network: 'Sepolia',
    status: 'deployed',
  },
  {
    id: '2',
    name: 'NFTCollection',
    type: 'ERC-721',
    address: '0x7Ab8234567890123456789012345678901B3C4',
    txHash: '0xdef456...',
    deployTime: '2024-03-03T15:45:00Z',
    network: 'Base',
    status: 'deployed',
  },
];

export const useAppStore = create<AppState>((set) => ({
  // Wallet initial state
  wallet: {
    connected: false,
    address: null,
    network: 'sepolia',
  },
  setWallet: (wallet) => set((state) => ({ wallet: { ...state.wallet, ...wallet } })),
  connectWallet: (address) => set((state) => ({
    wallet: { ...state.wallet, connected: true, address },
    ui: { ...state.ui, onboardingOpen: true }
  })),
  disconnectWallet: () => set({ wallet: { connected: false, address: null, network: 'sepolia' } }),

  // Agent initial state
  agent: {
    status: 'online',
    currentNode: null,
  },
  setAgentStatus: (status, currentNode) => set({ agent: { status, currentNode: currentNode || null } }),
  setAgentError: (errorMessage) => set({ agent: { status: 'error', currentNode: null, errorMessage } }),

  // Deployment initial state
  deployment: {
    stage: 'idle',
    contractName: '',
    contractType: 'ERC-20',
    estimatedGas: '0.0025 ETH',
    txHash: null,
    contractAddress: null,
  },
  setDeploymentStage: (stage) => set((state) => ({ deployment: { ...state.deployment, stage } })),
  setDeploymentData: (data) => set((state) => ({ deployment: { ...state.deployment, ...data } })),
  resetDeployment: () => set({
    deployment: {
      stage: 'idle',
      contractName: '',
      contractType: 'ERC-20',
      estimatedGas: '0.0025 ETH',
      txHash: null,
      contractAddress: null,
    }
  }),

  // Workflow nodes
  workflowNodes: initialWorkflowNodes,
  setNodeStatus: (nodeId, status) => set((state) => ({
    workflowNodes: state.workflowNodes.map((node) =>
      node.id === nodeId ? { ...node, status } : node
    ),
  })),
  activateNode: (nodeId) => set((state) => ({
    workflowNodes: state.workflowNodes.map((node) =>
      node.id === nodeId
        ? { ...node, status: 'active', startTime: Date.now() }
        : node
    ),
  })),
  completeNode: (nodeId) => set((state) => ({
    workflowNodes: state.workflowNodes.map((node) =>
      node.id === nodeId && node.startTime
        ? {
            ...node,
            status: 'done',
            duration: Date.now() - node.startTime
          }
        : node
    ),
  })),
  resetWorkflow: () => set({ workflowNodes: initialWorkflowNodes }),

  // Security validation layers
  securityLayers: initialSecurityLayers,
  setSecurityStatus: (layerId, status) => set((state) => ({
    securityLayers: state.securityLayers.map((layer) =>
      layer.id === layerId ? { ...layer, status } : layer
    ),
  })),

  // Contract list
  contracts: initialContracts,
  addContract: (contract) => set((state) => ({ contracts: [contract, ...state.contracts] })),
  updateContractStatus: (id, status) => set((state) => ({
    contracts: state.contracts.map((c) => (c.id === id ? { ...c, status } : c)),
  })),

  // Chat messages
  messages: [],
  addMessage: (message) => set((state) => ({
    messages: [
      ...state.messages,
      {
        ...message,
        id: Math.random().toString(36).substr(2, 9),
        timestamp: Date.now(),
      },
    ],
  })),
  clearMessages: () => set({ messages: [] }),

  // UI state
  ui: {
    sidebarOpen: true,
    workflowPanelOpen: true,
    deploymentModalOpen: false,
    onboardingOpen: false,
    onboardingStep: 0,
    currentView: 'landing',
  },
  toggleSidebar: () => set((state) => ({ ui: { ...state.ui, sidebarOpen: !state.ui.sidebarOpen } })),
  toggleWorkflowPanel: () => set((state) => ({ ui: { ...state.ui, workflowPanelOpen: !state.ui.workflowPanelOpen } })),
  openDeploymentModal: () => set((state) => ({ ui: { ...state.ui, deploymentModalOpen: true } })),
  closeDeploymentModal: () => set((state) => ({ ui: { ...state.ui, deploymentModalOpen: false } })),
  openOnboarding: () => set((state) => ({ ui: { ...state.ui, onboardingOpen: true, onboardingStep: 0 } })),
  closeOnboarding: () => set((state) => ({ ui: { ...state.ui, onboardingOpen: false } })),
  setOnboardingStep: (step) => set((state) => ({ ui: { ...state.ui, onboardingStep: step } })),
  setCurrentView: (view) => set((state) => ({ ui: { ...state.ui, currentView: view } })),

  // Trace events
  traceEvents: [],
  addTraceEvent: (message, status) => set((state) => ({
    traceEvents: [
      ...state.traceEvents,
      {
        id: Date.now().toString(),
        timestamp: new Date(),
        message,
        status,
      },
    ],
  })),
  clearTraceEvents: () => set({ traceEvents: [] }),
  setTraceComplete: () => set((state) => ({
    traceEvents: state.traceEvents.map((event) =>
      event.status === 'running' ? { ...event, status: 'completed' as const } : event
    ),
  })),
}));

// Helper to get store state directly (for use outside React components)
export const getStoreState = useAppStore.getState;
