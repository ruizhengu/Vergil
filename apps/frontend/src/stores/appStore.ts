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

// Default state for SSR
const defaultState: AppState = {
  wallet: { connected: false, address: null, network: 'sepolia' },
  setWallet: () => {},
  connectWallet: () => {},
  disconnectWallet: () => {},
  agent: { status: 'online', currentNode: null },
  setAgentStatus: () => {},
  setAgentError: () => {},
  deployment: { stage: 'idle', contractName: '', contractType: 'ERC-20', estimatedGas: '0.0025 ETH', txHash: null, contractAddress: null },
  setDeploymentStage: () => {},
  setDeploymentData: () => {},
  resetDeployment: () => {},
  workflowNodes: [],
  setNodeStatus: () => {},
  activateNode: () => {},
  completeNode: () => {},
  resetWorkflow: () => {},
  securityLayers: [],
  setSecurityStatus: () => {},
  contracts: [],
  addContract: () => {},
  updateContractStatus: () => {},
  messages: [],
  addMessage: () => {},
  clearMessages: () => {},
  ui: { sidebarOpen: true, workflowPanelOpen: true, deploymentModalOpen: false, onboardingOpen: false, onboardingStep: 0, currentView: 'landing' },
  toggleSidebar: () => {},
  toggleWorkflowPanel: () => {},
  openDeploymentModal: () => {},
  closeDeploymentModal: () => {},
  openOnboarding: () => {},
  closeOnboarding: () => {},
  setOnboardingStep: () => {},
  setCurrentView: () => {},
};

// Store instance
let store: AppState | null = null;

function createAppStore(): AppState {
  if (!store) {
    store = {
      // Wallet initial state
      wallet: {
        connected: false,
        address: null,
        network: 'sepolia',
      },
      setWallet: (wallet) => {
        const currentStore = store as AppState;
        currentStore.wallet = { ...currentStore.wallet, ...wallet };
      },
      connectWallet: (address) => {
        const currentStore = store as AppState;
        currentStore.wallet = { connected: true, address, network: 'sepolia' };
        currentStore.ui.onboardingOpen = true;
      },
      disconnectWallet: () => {
        const currentStore = store as AppState;
        currentStore.wallet = { connected: false, address: null, network: 'sepolia' };
      },

      // Agent initial state
      agent: {
        status: 'online',
        currentNode: null,
      },
      setAgentStatus: (status, currentNode) => {
        const currentStore = store as AppState;
        currentStore.agent = { status, currentNode: currentNode || null };
      },
      setAgentError: (errorMessage) => {
        const currentStore = store as AppState;
        currentStore.agent = { status: 'error', currentNode: null, errorMessage };
      },

      // Deployment initial state
      deployment: {
        stage: 'idle',
        contractName: '',
        contractType: 'ERC-20',
        estimatedGas: '0.0025 ETH',
        txHash: null,
        contractAddress: null,
      },
      setDeploymentStage: (stage) => {
        const currentStore = store as AppState;
        currentStore.deployment.stage = stage;
      },
      setDeploymentData: (data) => {
        const currentStore = store as AppState;
        currentStore.deployment = { ...currentStore.deployment, ...data };
      },
      resetDeployment: () => {
        const currentStore = store as AppState;
        currentStore.deployment = {
          stage: 'idle',
          contractName: '',
          contractType: 'ERC-20',
          estimatedGas: '0.0025 ETH',
          txHash: null,
          contractAddress: null,
        };
      },

      // Workflow nodes
      workflowNodes: initialWorkflowNodes,
      setNodeStatus: (nodeId, status) => {
        const currentStore = store as AppState;
        currentStore.workflowNodes = currentStore.workflowNodes.map((node) =>
          node.id === nodeId ? { ...node, status } : node
        );
      },
      activateNode: (nodeId) => {
        const currentStore = store as AppState;
        currentStore.workflowNodes = currentStore.workflowNodes.map((node) =>
          node.id === nodeId
            ? { ...node, status: 'active', startTime: Date.now() }
            : node
        );
      },
      completeNode: (nodeId) => {
        const currentStore = store as AppState;
        currentStore.workflowNodes = currentStore.workflowNodes.map((node) =>
          node.id === nodeId && node.startTime
            ? {
                ...node,
                status: 'done',
                duration: Date.now() - node.startTime
              }
            : node
        );
      },
      resetWorkflow: () => {
        const currentStore = store as AppState;
        currentStore.workflowNodes = initialWorkflowNodes;
      },

      // Security validation layers
      securityLayers: initialSecurityLayers,
      setSecurityStatus: (layerId, status) => {
        const currentStore = store as AppState;
        currentStore.securityLayers = currentStore.securityLayers.map((layer) =>
          layer.id === layerId ? { ...layer, status } : layer
        );
      },

      // Contract list
      contracts: initialContracts,
      addContract: (contract) => {
        const currentStore = store as AppState;
        currentStore.contracts = [contract, ...currentStore.contracts];
      },
      updateContractStatus: (id, status) => {
        const currentStore = store as AppState;
        currentStore.contracts = currentStore.contracts.map((c) => (c.id === id ? { ...c, status } : c));
      },

      // Chat messages
      messages: [],
      addMessage: (message) => {
        const currentStore = store as AppState;
        currentStore.messages = [
          ...currentStore.messages,
          {
            ...message,
            id: Math.random().toString(36).substr(2, 9),
            timestamp: Date.now(),
          },
        ];
      },
      clearMessages: () => {
        const currentStore = store as AppState;
        currentStore.messages = [];
      },

      // UI state
      ui: {
        sidebarOpen: true,
        workflowPanelOpen: true,
        deploymentModalOpen: false,
        onboardingOpen: false,
        onboardingStep: 0,
        currentView: 'landing',
      },
      toggleSidebar: () => {
        const currentStore = store as AppState;
        currentStore.ui.sidebarOpen = !currentStore.ui.sidebarOpen;
      },
      toggleWorkflowPanel: () => {
        const currentStore = store as AppState;
        currentStore.ui.workflowPanelOpen = !currentStore.ui.workflowPanelOpen;
      },
      openDeploymentModal: () => {
        const currentStore = store as AppState;
        currentStore.ui.deploymentModalOpen = true;
      },
      closeDeploymentModal: () => {
        const currentStore = store as AppState;
        currentStore.ui.deploymentModalOpen = false;
      },
      openOnboarding: () => {
        const currentStore = store as AppState;
        currentStore.ui.onboardingOpen = true;
        currentStore.ui.onboardingStep = 0;
      },
      closeOnboarding: () => {
        const currentStore = store as AppState;
        currentStore.ui.onboardingOpen = false;
      },
      setOnboardingStep: (step) => {
        const currentStore = store as AppState;
        currentStore.ui.onboardingStep = step;
      },
      setCurrentView: (view) => {
        const currentStore = store as AppState;
        currentStore.ui.currentView = view;
      },
    };
  }
  return store;
}

// React hook for the store
export const useAppStore = (): AppState => {
  if (typeof window === 'undefined') {
    return defaultState;
  }
  return createAppStore();
};
