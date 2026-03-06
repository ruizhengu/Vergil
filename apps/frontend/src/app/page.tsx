'use client';

import Navbar from '@/components/Navbar';
import HeroSection from '@/sections/Hero';
import FeatureCards from '@/sections/FeatureCards';
import BottomCTA from '@/sections/BottomCTA';
import CursorGlow from '@/components/CursorGlow';
import EdgeGlow from '@/components/EdgeGlow';
import BackgroundEffects from '@/components/BackgroundEffects';
import { OnboardingModal } from '@/components/OnboardingModal';

const Index = () => {
  return (
    <div className="min-h-screen bg-[hsl(var(--background))] corner-glow">
      <BackgroundEffects />
      <CursorGlow />
      <EdgeGlow />
      <Navbar />
      <HeroSection />
      <FeatureCards />
      <BottomCTA />
      <OnboardingModal />
    </div>
  );
};

export default Index;
