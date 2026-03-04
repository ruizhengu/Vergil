"use client";

import React, { useEffect, useState } from "react";
import { CheckCircle2, FileJson, Loader2 } from "lucide-react";

type NodeState = "pending" | "running" | "completed";

export default function AgentFlow() {
  const [orchestratorState, setOrchestratorState] = useState<NodeState>("pending");
  const [parserState, setParserState] = useState<NodeState>("pending");
  const [manifestState, setManifestState] = useState<NodeState>("pending");
  const [showEdges, setShowEdges] = useState(false);

  useEffect(() => {
    // Sequence of animations
    // 1. Orchestrator starts
    setOrchestratorState("running");

    // 2. Orchestrator completes after 2s, edges start drawing
    const orchestratorTimer = setTimeout(() => {
      setOrchestratorState("completed");
      setShowEdges(true);
    }, 2000);

    // 3. Parser & Manifest start running after edges draw (say 1.5s after edges start)
    const childrenStartTimer = setTimeout(() => {
      setParserState("running");
      setManifestState("running");
    }, 3500);

    // 4. Parser completes after 3s of running
    const parserCompleteTimer = setTimeout(() => {
      setParserState("completed");
    }, 6500);

    // 5. Manifest completes after 4.5s of running
    const manifestCompleteTimer = setTimeout(() => {
      setManifestState("completed");
    }, 8000);

    return () => {
      clearTimeout(orchestratorTimer);
      clearTimeout(childrenStartTimer);
      clearTimeout(parserCompleteTimer);
      clearTimeout(manifestCompleteTimer);
    };
  }, []);

  const path1 = "M 500 150 C 500 250, 250 250, 250 350";
  const path2 = "M 500 150 C 500 250, 750 250, 750 350";

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50 overflow-hidden font-sans">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-slate-800">Agent Orchestration</h1>
        <p className="text-slate-500 mt-2">Observing the collaboration of multiple specialized agents</p>
      </div>

      <div className="relative w-[1000px] h-[600px] mt-8 bg-white/50 rounded-xl shadow-sm border border-slate-100">
        <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 1000 600">
          <defs>
            <linearGradient id="edge-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#cbd5e1" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#94a3b8" stopOpacity="0.5" />
            </linearGradient>

            <marker id="dot" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6">
              <circle cx="5" cy="5" r="4" fill="#10b981" />
            </marker>
          </defs>

          {/* Lines */}
          <path
            d={path1}
            fill="none"
            stroke="url(#edge-gradient)"
            strokeWidth="2"
            className={`transition-all duration-1000 ease-in-out ${showEdges ? "opacity-100" : "opacity-0"}`}
            style={{
              strokeDasharray: "1000",
              strokeDashoffset: showEdges ? "0" : "1000",
            }}
          />
          <path
            d={path2}
            fill="none"
            stroke="url(#edge-gradient)"
            strokeWidth="2"
            className={`transition-all duration-1000 ease-in-out ${showEdges ? "opacity-100" : "opacity-0"}`}
            style={{
              strokeDasharray: "1000",
              strokeDashoffset: showEdges ? "0" : "1000",
            }}
          />

          {/* Animated dots along Path 1 */}
          {(parserState === "running" || manifestState === "running") && (
            <>
              <circle r="4" fill="#10b981">
                <animateMotion dur="2s" repeatCount="indefinite" path={path1} />
              </circle>
              {/* Delayed second dot */}
              <circle r="4" fill="#10b981">
                <animateMotion dur="2s" begin="1s" repeatCount="indefinite" path={path1} />
              </circle>

              {/* Animated dots along Path 2 */}
              <circle r="4" fill="#3b82f6">
                <animateMotion dur="2.5s" repeatCount="indefinite" path={path2} />
              </circle>
              <circle r="4" fill="#3b82f6">
                <animateMotion dur="2.5s" begin="1.25s" repeatCount="indefinite" path={path2} />
              </circle>
            </>
          )}
        </svg>

        {/* Nodes */}
        <NodeCard
          x={500}
          y={100}
          title="Opus Orchestrator"
          desc="Assigns and coordinates all sub-agents"
          state={orchestratorState}
          label="OPUS 4.6"
          align="center"
        />

        {showEdges && (
          <div
            className="absolute flex flex-col items-center opacity-0 animate-[fadeIn_0.5s_ease-in-out_1s_forwards]"
            style={{ left: '500px', top: '220px', transform: 'translate(-50%, -50%)' }}
          >
            <span className="px-3 py-1 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-full border border-emerald-100">
              PHASE 1+2
            </span>
            <span className="text-[10px] text-slate-400 mt-1 uppercase tracking-wider font-semibold">
              Parallel
            </span>
          </div>
        )}

        <NodeCard
          x={250}
          y={350}
          title="Corrections Parser"
          desc="Vision-reads corrections letter"
          state={parserState}
          result="corrections_parsed.json"
          show={showEdges}
          delay="animate-[fadeIn_0.5s_ease-in-out_0.5s_forwards]"
          align="top"
        />

        <NodeCard
          x={750}
          y={350}
          title="Manifest Agent"
          desc="Scans 15 sheets, builds spatial index"
          state={manifestState}
          result="sheet-manifest.json"
          show={showEdges}
          delay="animate-[fadeIn_0.5s_ease-in-out_0.8s_forwards]"
          align="top"
        />
      </div>

      <button
        onClick={() => window.location.reload()}
        className="mt-8 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg font-medium transition-colors shadow-sm"
      >
        Replay Simulation
      </button>

      <style dangerouslySetInnerHTML={{
        __html: `
        @keyframes fadeIn {
          from { opacity: 0; transform: translate(-50%, -40%); }
          to { opacity: 1; transform: translate(-50%, -50%); }
        }
        @keyframes popIn {
          0% { transform: scale(0.9); opacity: 0; }
          70% { transform: scale(1.05); }
          100% { transform: scale(1); opacity: 1; }
        }
      ` }} />
    </div>
  );
}

function NodeCard({
  x,
  y,
  title,
  desc,
  state,
  label,
  result,
  show = true,
  delay = "",
  align = "center",
}: {
  x: number;
  y: number;
  title: string;
  desc: string;
  state: NodeState;
  label?: string;
  result?: string;
  show?: boolean;
  delay?: string;
  align?: "center" | "top";
}) {
  if (!show) return null;

  const isCompleted = state === "completed";
  const isRunning = state === "running";

  return (
    <div
      className={`absolute w-[320px] bg-white rounded-xl shadow-lg border border-slate-200 p-5 flex flex-col items-center justify-center z-10 transition-shadow duration-300 hover:shadow-xl ${delay}`}
      style={{
        left: `${x}px`,
        top: `${y}px`,
        transform: align === "top" ? "translate(-50%, 0)" : "translate(-50%, -50%)",
        opacity: delay ? 0 : 1
      }}
    >
      {label && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-slate-50 border border-slate-200 rounded-full text-[10px] font-bold tracking-widest text-emerald-700 whitespace-nowrap">
          {label}
        </div>
      )}

      {isCompleted && (
        <div className="absolute top-3 right-3 text-emerald-500 animate-[popIn_0.3s_ease-out]">
          <CheckCircle2 size={18} />
        </div>
      )}

      <h3 className="text-xl font-bold font-serif text-slate-800">{title}</h3>
      <p className="text-sm text-slate-500 mt-1.5 text-center leading-relaxed">
        {desc}
      </p>

      {isRunning && (
        <div className="mt-4 flex items-center space-x-2 text-blue-600 text-sm font-medium animate-pulse">
          <Loader2 size={16} className="animate-spin" />
          <span>Processing...</span>
        </div>
      )}

      {isCompleted && result && (
        <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 flex items-center space-x-2 px-3 py-1.5 bg-amber-50 text-amber-700 border border-amber-200 rounded-full shadow-sm animate-[popIn_0.4s_ease-out] whitespace-nowrap">
          <FileJson size={14} />
          <span className="text-xs font-bold">{result}</span>
        </div>
      )}
    </div>
  );
}
