import { create } from 'zustand';

interface OnboardingState {
  isOpen: boolean;
  step: number;
  selectedNetwork: 'mainnet' | 'sepolia' | 'base';
  selectedTemplate: string | null;
  description: string;
  openOnboarding: () => void;
  closeOnboarding: () => void;
  setStep: (step: number) => void;
  setSelectedNetwork: (network: 'mainnet' | 'sepolia' | 'base') => void;
  setSelectedTemplate: (template: string | null) => void;
  setDescription: (description: string) => void;
  resetOnboarding: () => void;
}

export const useOnboardingStore = create<OnboardingState>((set) => ({
  isOpen: false,
  step: 0,
  selectedNetwork: 'sepolia',
  selectedTemplate: null,
  description: '',

  openOnboarding: () => set({ isOpen: true, step: 0 }),
  closeOnboarding: () => set({ isOpen: false }),
  setStep: (step) => set({ step }),
  setSelectedNetwork: (network) => set({ selectedNetwork: network }),
  setSelectedTemplate: (template) => set({ selectedTemplate: template }),
  setDescription: (description) => set({ description }),
  resetOnboarding: () => set({
    step: 0,
    selectedNetwork: 'sepolia',
    selectedTemplate: null,
    description: '',
  }),
}));
