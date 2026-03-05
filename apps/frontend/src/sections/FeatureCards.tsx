'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

const features = [
  {
    title: "Contract Forge",
    description: "Natural language to Solidity. Describe what you need, Vergil writes the contract.",
    status: "NETWORK ACTIVE",
    statusColor: "online" as const,
    content: (
      <div className="bg-[hsl(var(--background)/0.5)] rounded-lg p-4 space-y-3 border border-[hsl(var(--foreground)/0.04)]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-[hsl(var(--primary)/0.2)] flex items-center justify-center">
            <span className="text-[hsl(var(--primary))] text-[8px]">V</span>
          </div>
          <div className="h-2 w-32 rounded bg-[hsl(var(--foreground)/0.1)]" />
        </div>
        <div className="space-y-2 pl-8">
          <div className="h-2 w-full rounded bg-[hsl(var(--foreground)/0.06)]" />
          <div className="h-2 w-3/4 rounded bg-[hsl(var(--foreground)/0.06)]" />
          <div className="h-2 w-1/2 rounded bg-[hsl(var(--primary)/0.1)]" />
        </div>
        <div className="mt-3 p-3 rounded bg-[hsl(var(--muted)/0.5)] border border-[hsl(var(--foreground)/0.04)]">
          <div className="font-mono text-[9px] text-[hsl(var(--primary)/0.6)] mb-1">SOLIDITY · Token.sol</div>
          <div className="space-y-1">
            <div className="h-1.5 w-full rounded bg-[hsl(var(--primary)/0.1)]" />
            <div className="h-1.5 w-4/5 rounded bg-[hsl(var(--primary)/0.1)]" />
            <div className="h-1.5 w-2/3 rounded bg-[hsl(var(--secondary)/0.1)]" />
          </div>
        </div>
      </div>
    ),
  },
  {
    title: "Agent Workflow",
    description: "Watch Vergil think. Every reasoning step, tool call, and decision is visible in real time.",
    status: "REASONING",
    statusColor: "active" as const,
    content: (
      <div className="bg-[hsl(var(--background)/0.5)] rounded-lg p-4 space-y-2 border border-[hsl(var(--foreground)/0.04)]">
        {["Reasoning", "Action Planning", "Tool Execution", "Composing Output"].map((node, i) => (
          <div key={node} className="flex items-center gap-3 p-2 rounded bg-[hsl(var(--muted)/0.3)]">
            <div
              className={`w-0.5 h-6 rounded-full ${
                i === 1 ? "bg-[hsl(var(--primary))] shadow-[0_0_8px_hsl(199_90%_64%/0.5)]" : "bg-[hsl(var(--foreground)/0.1)]"
              }`}
            />
            <span className={`font-mono text-[10px] ${i === 1 ? "text-[hsl(var(--foreground))]" : "text-[hsl(var(--muted-foreground))]"}`}>
              {node}
            </span>
            {i === 1 && (
              <span className="ml-auto font-mono text-[9px] text-[hsl(var(--primary))]">00:01.2</span>
            )}
            {i === 0 && (
              <span className="ml-auto text-[hsl(var(--success))] text-[10px]">✓</span>
            )}
          </div>
        ))}
      </div>
    ),
  },
  {
    title: "Guardrail · Z3",
    description: "Triple-layer security. Logic checks, compliance rules, and symbolic verification before deployment.",
    status: "GUARDRAIL ACTIVE",
    statusColor: "warning" as const,
    content: (
      <div className="bg-[hsl(var(--background)/0.5)] rounded-lg p-4 space-y-2 border border-[hsl(var(--foreground)/0.04)]">
        {[
          { name: "CHECKER", status: "PASS", color: "text-[hsl(var(--success))]" },
          { name: "COMPLIANCE", status: "PASS", color: "text-[hsl(var(--success))]" },
          { name: "GUARDRAIL·Z3", status: "REVIEWING", color: "text-[hsl(var(--primary))]" },
        ].map((layer) => (
          <div key={layer.name} className="flex items-center justify-between p-2 rounded bg-[hsl(var(--muted)/0.3)]">
            <div className="flex items-center gap-2">
              <span className={`status-dot status-dot--${layer.status === "PASS" ? "online" : "active"}`} />
              <span className="font-mono text-[10px] text-[hsl(var(--muted-foreground))]">{layer.name}</span>
            </div>
            <span className={`font-mono text-[9px] ${layer.color}`}>{layer.status}</span>
          </div>
        ))}
        <div className="pt-2 text-center">
          <span className="font-mono text-[8px] text-[hsl(var(--muted-foreground)/0.5)] tracking-widest">
            SYMBOLIC VERIFICATION VIA Z3 SMT SOLVER
          </span>
        </div>
      </div>
    ),
  },
];

const FeatureCards = () => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <section ref={ref} className="relative py-32 overflow-hidden noise-overlay">
      <div className="container mx-auto px-8 relative z-10">
        {/* Section header */}
        <div className="mb-16 space-y-4">
          <div className="flex items-center gap-2">
            <span className="status-dot status-dot--active" />
            <span className="font-mono text-[10px] tracking-[0.15em] text-[hsl(var(--muted-foreground))] uppercase">
              System Capabilities
            </span>
          </div>
          <h2 className="font-cinzel text-4xl md:text-5xl lg:text-6xl text-[hsl(var(--foreground))] leading-tight tracking-[0.05em]">
            Contract intelligence,
            <br />
            made auditable.
          </h2>
        </div>

        {/* Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {features.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 40 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.6, delay: i * 0.15, ease: "easeOut" }}
              className={`rounded-2xl border border-[hsl(var(--foreground)/0.06)] bg-[hsl(var(--card)/0.4)] backdrop-blur-sm p-6 flex flex-col gap-5 transition-transform duration-300 ${
                i === 1 ? "md:scale-[1.03] md:-translate-y-2 border-[hsl(var(--secondary)/0.2)]" : ""
              } hover:border-[hsl(var(--secondary)/0.3)]`}
              style={i === 1 ? { boxShadow: "0 0 40px hsl(42 70% 55% / 0.06)" } : {}}
            >
              {/* Card content preview */}
              {feature.content}

              {/* Card info */}
              <div className="space-y-2 mt-auto">
                <h3 className="font-cinzel text-sm tracking-[0.1em] text-[hsl(var(--foreground))]">{feature.title}</h3>
                <p className="font-crimson italic text-sm text-[hsl(var(--muted-foreground))] leading-relaxed">
                  {feature.description}
                </p>
              </div>

              {/* Card footer status */}
              <div className="flex items-center gap-2 pt-2 border-t border-[hsl(var(--foreground)/0.04)]">
                <span className={`status-dot status-dot--${feature.statusColor}`} />
                <span className="font-mono text-[9px] tracking-[0.12em] text-[hsl(var(--muted-foreground))] uppercase">
                  {feature.status}
                </span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default FeatureCards;
