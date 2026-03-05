'use client';

import { motion } from 'framer-motion';
import { useMemo } from 'react';

const ParticleRing = () => {
  const particles = useMemo(() => {
    const count = 100;
    return Array.from({ length: count }).map((_, i) => {
      const angle = (i / count) * Math.PI * 2;
      const rx = 220;
      const ry = 175;
      const x = 250 + rx * Math.cos(angle);
      const y = 210 + ry * Math.sin(angle);
      const opacity = 0.5 + Math.random() * 0.3;
      const r = 1.5 + Math.random() * 1.5;
      const delay = (i / count) * 3;
      return { x, y, opacity, r, delay };
    });
  }, []);

  const innerParticles = useMemo(() => {
    const count = 30;
    return Array.from({ length: count }).map((_, i) => {
      const angle = (i / count) * Math.PI * 2;
      const x = 250 + 140 * Math.cos(angle);
      const y = 210 + 110 * Math.sin(angle);
      return { x, y, opacity: 0.2 + Math.random() * 0.4 };
    });
  }, []);

  return (
    <div className="relative w-[500px] h-[420px] flex items-center justify-center">
      {/* Deep outer glow */}
      <div
        className="absolute animate-breathe"
        style={{
          width: 540,
          height: 430,
          left: -20,
          top: -5,
          borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(79,195,247,0.15) 0%, transparent 70%)',
          filter: 'blur(60px)',
        }}
      />

      {/* Main rotating ring */}
      <motion.div
        className="absolute w-full h-full"
        animate={{ rotate: 360 }}
        transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
        style={{ willChange: 'transform' }}
      >
        <svg viewBox="0 0 500 420" className="w-full h-full" style={{ overflow: 'visible' }}>
          <defs>
            <filter id="particleGlow">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Main ellipse stroke */}
          <ellipse
            cx="250"
            cy="210"
            rx="220"
            ry="175"
            fill="none"
            stroke="rgba(79,195,247,0.25)"
            strokeWidth="1.5"
          />

          {/* Particle dots */}
          {particles.map((p, i) => (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r={p.r}
              fill="#4fc3f7"
              opacity={p.opacity}
              filter="url(#particleGlow)"
              className="animate-particle-pulse"
              style={{ animationDelay: `${p.delay}s` }}
            />
          ))}

          {/* Copper gold arc — 30% of ellipse */}
          <ellipse
            cx="250"
            cy="210"
            rx="220"
            ry="175"
            fill="none"
            stroke="rgba(201,168,76,0.45)"
            strokeWidth="3"
            strokeDasharray="415 970"
            strokeLinecap="round"
          />
          {/* Second gold arc — opposite side */}
          <ellipse
            cx="250"
            cy="210"
            rx="220"
            ry="175"
            fill="none"
            stroke="rgba(180,140,50,0.25)"
            strokeWidth="2"
            strokeDasharray="200 1185"
            strokeDashoffset="700"
            strokeLinecap="round"
          />
        </svg>
      </motion.div>

      {/* Inner counter-rotating ring */}
      <motion.div
        className="absolute w-[300px] h-[240px]"
        animate={{ rotate: -360 }}
        transition={{ duration: 30, repeat: Infinity, ease: 'linear' }}
        style={{ willChange: 'transform' }}
      >
        <svg viewBox="0 0 500 420" className="w-full h-full" style={{ overflow: 'visible' }}>
          <ellipse
            cx="250"
            cy="210"
            rx="140"
            ry="110"
            fill="none"
            stroke="rgba(79,195,247,0.15)"
            strokeWidth="0.8"
          />
          {innerParticles.map((p, i) => (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r={1.5}
              fill="#4fc3f7"
              opacity={p.opacity}
            />
          ))}
        </svg>
      </motion.div>

      {/* Core glow */}
      <div className="absolute w-4 h-4 rounded-full bg-[hsl(199_90%_64%/0.5)] blur-md animate-breathe" />
      <div className="absolute w-2 h-2 rounded-full bg-[hsl(199_90%_64%)] " />
    </div>
  );
};

export default ParticleRing;
