'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import VergilSigil from '@/components/VergilSigil';
import { useAppStore } from '@/stores/appStore';
import { useOnboardingStore } from '@/store/onboardingStore';

const Navbar = () => {
  const [activeSection, setActiveSection] = useState('philosophy');
  const { setCurrentView } = useAppStore();
  const openOnboarding = useOnboardingStore((state) => state.openOnboarding);

  const handleNavClick = (item: string) => {
    const sectionId = item.toLowerCase();
    setActiveSection(sectionId);

    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const navItems = ['Philosophy', 'Architecture', 'Deploy'];

  return (
    <nav className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
      <div className="relative rounded-full">
        {/* Gradient border overlay */}
        <div
          className="absolute -inset-px rounded-full pointer-events-none"
          style={{
            background: 'linear-gradient(90deg, transparent, rgba(79,195,247,0.3), rgba(201,168,76,0.2), transparent)',
            maskImage: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
            WebkitMaskImage: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
            maskComposite: 'exclude',
            WebkitMaskComposite: 'xor',
            padding: 1,
          }}
        />
        <div
          className="flex items-center gap-1 pl-2 pr-3 py-2.5 rounded-full"
          style={{
            background: 'rgba(5,8,16,0.7)',
            backdropFilter: 'blur(12px) saturate(180%)',
            WebkitBackdropFilter: 'blur(12px) saturate(180%)',
            boxShadow: '0 1px 40px rgba(79,195,247,0.08)',
          }}
        >
          {/* Brand */}
          <div className="flex items-center gap-2 px-4">
            <VergilSigil size={24} />
            <span className="font-cinzel text-xs tracking-[0.15em] text-[hsl(var(--foreground))]">VERGIL</span>
          </div>

          {/* Separator */}
          <div className="w-px h-5 bg-[hsl(var(--foreground)/0.1)]" />

          {/* Nav links */}
          <div className="flex items-center gap-1 px-2">
            {navItems.map((item) => (
              <button
                key={item}
                onClick={() => handleNavClick(item)}
                className={`px-4 py-1.5 rounded-full text-xs font-mono tracking-wider transition-all duration-300 ${activeSection === item.toLowerCase()
                    ? 'bg-[hsl(var(--foreground)/0.1)] text-[hsl(var(--foreground))]'
                    : 'text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]'
                  }`}
              >
                {item}
              </button>
            ))}
          </div>

          {/* Separator */}
          <div className="w-px h-5 bg-[hsl(var(--foreground)/0.1)]" />

          {/* CTA */}
          <Button variant="capsule-solid" size="sm" className="ml-1 text-xs tracking-wider animate-btn-pulse" onClick={openOnboarding}>
            Connect Wallet ▶
          </Button>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
