'use client';

import { motion } from 'framer-motion';
import ParticleRing from '@/components/ParticleRing';
import { Button } from '@/components/ui/button';
import { useOnboardingStore } from '@/store/onboardingStore';

const HeroSection = () => {
  const openOnboarding = useOnboardingStore((state) => state.openOnboarding);

  return (
    <section id="philosophy" className="relative min-h-screen flex items-center">
      {/* System status label */}
      <div className="absolute top-28 left-8 flex items-center gap-2 z-10">
        <span className="status-dot status-dot--online" />
        <span className="font-mono text-[10px] tracking-[0.15em] text-[hsl(var(--muted-foreground))] uppercase">
          System Operational
        </span>
      </div>

      {/* Floating right labels */}
      <div className="absolute top-1/3 right-8 z-10 space-y-4 hidden lg:block">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] tracking-[0.15em] text-[hsl(var(--muted-foreground))] uppercase">
            Zero Latency
          </span>
          <span className="w-12 h-px bg-[hsl(var(--foreground)/0.2)]" />
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] tracking-[0.15em] text-[hsl(var(--muted-foreground))] uppercase">
            Audit-Native
          </span>
          <span className="w-12 h-px bg-[hsl(var(--foreground)/0.2)]" />
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-8 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center relative z-10">
        {/* Left side - Text */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="space-y-8"
        >
          <h1 className="font-cinzel text-4xl md:text-5xl lg:text-6xl leading-[1] tracking-[0.05em] font-semibold text-[hsl(var(--foreground))] hero-shimmer">
            SMARTER WITH
            <br />
            YOUR
            <br />
            CONTRACT.
          </h1>
          <p className="font-crimson italic text-base md:text-lg text-[hsl(var(--muted-foreground))] max-w-md leading-relaxed">
            From natural language to audited, on-chain contracts.
            Vergil guides you through.
          </p>
          <div className="flex items-center gap-4 pt-2">
            <Button variant="capsule-solid" size="lg" className="animate-btn-pulse" onClick={openOnboarding}>
              Connect Wallet
            </Button>
            <Button variant="capsule-outline" size="lg">
              View Architecture →
            </Button>
          </div>
        </motion.div>

        {/* Right side - Particle Ring */}
        <motion.div
          className="hidden lg:flex justify-center items-center"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1.2, ease: "easeOut", delay: 0.3 }}
        >
          <ParticleRing />
        </motion.div>
      </div>

      {/* Bottom strip */}
      <div className="absolute bottom-0 left-0 right-0 py-4 px-8 flex items-center justify-between z-10" style={{ borderTop: "1px solid", borderImage: "linear-gradient(90deg, transparent, hsl(42 70% 55% / 0.2), hsl(199 90% 64% / 0.15), transparent) 1" }}>
        <div className="flex items-center gap-8 overflow-hidden">
          {["ETHEREUM", "BASE", "ARBITRUM", "OPTIMISM", "POLYGON"].map((name) => (
            <span
              key={name}
              className="font-mono text-[10px] tracking-[0.2em] text-[hsl(var(--muted-foreground)/0.4)] whitespace-nowrap"
            >
              {name}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] tracking-[0.12em] text-[hsl(var(--muted-foreground)/0.6)]">
            [ ✓ ] TRUSTED BY BUILDERS
          </span>
        </div>
      </div>
    </section>
  );
};

export default HeroSection;
