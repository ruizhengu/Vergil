import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useOnboardingStore } from '@/store/onboardingStore';
import { X, ChevronRight, Check, Globe, FileCode, MessageSquare } from 'lucide-react';
import VergilSigil from '@/components/VergilSigil';

export function OnboardingModal() {
  const {
    isOpen,
    closeOnboarding,
    step,
    setStep,
    selectedNetwork,
    setSelectedNetwork,
    selectedTemplate,
    setSelectedTemplate,
    description,
    setDescription,
  } = useOnboardingStore();

  const router = useRouter();
  const [localNetwork, setLocalNetwork] = useState(selectedNetwork);

  if (!isOpen) return null;

  const networks = [
    { id: 'mainnet', label: 'Ethereum Mainnet', icon: Globe, color: '#4caf82' },
    { id: 'sepolia', label: 'Sepolia Testnet', icon: Globe, color: '#c9a84c' },
    { id: 'base', label: 'Base', icon: Globe, color: '#4fc3f7' },
  ];

  const templates = [
    { id: 'erc20', label: 'ERC-20 Token', icon: FileCode, description: 'Standard fungible token' },
    { id: 'erc721', label: 'ERC-721 NFT', icon: FileCode, description: 'Non-fungible token collection' },
    { id: 'custom', label: 'Custom Contract', icon: MessageSquare, description: 'Describe your own contract' },
  ];

  const handleNext = () => {
    if (step === 0) {
      setSelectedNetwork(localNetwork);
    }
    if (step < 2) {
      setStep(step + 1);
    } else {
      closeOnboarding();
      router.push('/chat');
    }
  };

  const handleSkip = () => {
    closeOnboarding();
  };

  const steps = [
    {
      title: 'Select your network',
      description: 'Choose the blockchain network for your contracts',
      content: (
        <div className="space-y-3">
          {networks.map((network) => (
            <button
              key={network.id}
              onClick={() => setLocalNetwork(network.id as 'mainnet' | 'sepolia' | 'base')}
              className={`w-full flex items-center gap-4 p-4 rounded-xl border transition-all ${
                localNetwork === network.id
                  ? 'bg-[#4fc3f7]/5 border-[#4fc3f7]/40'
                  : 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.12]'
              }`}
            >
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center"
                style={{ background: `${network.color}20` }}
              >
                <network.icon className="w-5 h-5" style={{ color: network.color }} />
              </div>
              <div className="text-left">
                <p className="text-sm text-white">{network.label}</p>
              </div>
              {localNetwork === network.id && (
                <Check className="w-4 h-4 text-[#4fc3f7] ml-auto" />
              )}
            </button>
          ))}
        </div>
      ),
    },
    {
      title: 'Choose a starting template',
      description: 'Select a template to get started quickly',
      content: (
        <div className="space-y-3">
          {templates.map((template) => (
            <button
              key={template.id}
              onClick={() => setSelectedTemplate(template.id)}
              className={`w-full flex items-center gap-4 p-4 rounded-xl border transition-all ${
                selectedTemplate === template.id
                  ? 'bg-[#4fc3f7]/5 border-[#4fc3f7]/40'
                  : 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.12]'
              }`}
            >
              <div className="w-10 h-10 rounded-lg bg-[#4fc3f7]/10 flex items-center justify-center">
                <template.icon className="w-5 h-5 text-[#4fc3f7]" />
              </div>
              <div className="text-left">
                <p className="text-sm text-white">{template.label}</p>
                <p className="text-xs text-white/40">{template.description}</p>
              </div>
              {selectedTemplate === template.id && (
                <Check className="w-4 h-4 text-[#4fc3f7] ml-auto" />
              )}
            </button>
          ))}
        </div>
      ),
    },
    {
      title: 'Describe your contract',
      description: 'Tell Vergil what you want to build',
      content: (
        <div className="space-y-4">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g., Create an ERC-20 token named 'MyToken' with symbol 'MTK' and a total supply of 1 million tokens..."
            className="w-full h-32 bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-[#4fc3f7]/40 resize-none"
          />
          <div className="flex flex-wrap gap-2">
            {[
              'ERC-20 with minting',
              'NFT with royalties',
              'Staking contract',
              'DAO governance',
            ].map((prompt) => (
              <button
                key={prompt}
                onClick={() => setDescription(`Create a ${prompt} contract`)}
                className="px-3 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.08] text-xs text-white/50 hover:text-white hover:border-white/20 transition-colors"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      ),
    },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(4, 5, 8, 0.92)', backdropFilter: 'blur(8px)' }}
    >
      <div className="w-full max-w-md mx-4 vergil-card overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <VergilSigil size={32} />
            <span className="font-cinzel text-xs tracking-[0.15em] text-[hsl(var(--foreground))]">VERGIL</span>
          </div>
          <button
            onClick={handleSkip}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-white/40 hover:text-white hover:bg-white/5 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Progress */}
        <div className="px-5 pt-5">
          <div className="flex items-center gap-2 mb-2">
            {steps.map((_, i) => (
              <div
                key={i}
                className={`h-1 flex-1 rounded-full transition-colors ${
                  i <= step ? 'bg-[#4fc3f7]' : 'bg-white/10'
                }`}
              />
            ))}
          </div>
          <p className="text-[10px] text-white/40 text-right">
            Step {step + 1} of {steps.length}
          </p>
        </div>

        {/* Content */}
        <div className="p-5">
          <h2 className="font-cinzel text-lg text-white mb-2">{steps[step].title}</h2>
          <p className="text-sm text-white/50 mb-6">{steps[step].description}</p>

          {steps[step].content}
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-white/[0.06] flex items-center justify-between">
          <button
            onClick={handleSkip}
            className="text-xs text-white/40 hover:text-white/60 transition-colors"
          >
            Skip, I&apos;ll forge my own path →
          </button>

          <button
            onClick={handleNext}
            className="capsule-btn-primary flex items-center gap-2 px-4 py-2"
          >
            <span>{step === steps.length - 1 ? 'Start Forging' : 'Continue'}</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
