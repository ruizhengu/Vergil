'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

const BottomCTA = () => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });
  const router = useRouter();

  return (
    <section id="deploy" ref={ref} className="relative py-40 overflow-hidden">
      <div className="container mx-auto px-8 text-center relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8 }}
          className="max-w-3xl mx-auto space-y-10"
        >
          {/* Large serif paragraph */}
          <p className="font-cormorant italic text-3xl md:text-4xl lg:text-5xl leading-[1.3]">
            <span className="text-[hsl(var(--foreground))]">The contract is only as safe as</span>
            <br />
            <span style={{ color: "rgba(201,168,76,0.55)" }}>the intelligence behind it.</span>
          </p>

          {/* Section label */}
          <div className="flex items-center justify-center gap-3">
            <span className="w-12 h-px bg-gradient-to-r from-transparent via-[hsl(var(--secondary)/0.4)] to-transparent" />
            <span className="font-mono text-[10px] tracking-[0.15em] text-[hsl(var(--secondary)/0.7)] uppercase">
              Built for Onchain Builders
            </span>
            <span className="w-12 h-px bg-gradient-to-r from-transparent via-[hsl(var(--secondary)/0.4)] to-transparent" />
          </div>

          {/* CTA */}
          <Button
            variant="capsule-outline"
            size="lg"
            className="mx-auto border-[hsl(var(--secondary)/0.3)] text-[hsl(var(--secondary))] hover:border-[hsl(var(--secondary)/0.6)] hover:shadow-[0_0_30px_hsl(42_70%_55%/0.15)]"
            onClick={() => router.push('/chat')}
          >
            Begin Forging →
          </Button>
        </motion.div>
      </div>

      {/* Footer */}
      <div className="absolute bottom-0 left-0 right-0 border-t border-[hsl(var(--foreground)/0.06)] py-6 px-8 flex items-center justify-between">
        <span className="font-mono text-[10px] text-[hsl(var(--muted-foreground)/0.4)]">
          © 2026 Vergil Protocol
        </span>
        <div className="flex items-center gap-2">
          <span className="status-dot status-dot--online" />
          <span className="font-mono text-[10px] text-[hsl(var(--muted-foreground)/0.4)] tracking-wider">
            MAINNET · BLOCK #19,847,293
          </span>
        </div>
      </div>
    </section>
  );
};

export default BottomCTA;
