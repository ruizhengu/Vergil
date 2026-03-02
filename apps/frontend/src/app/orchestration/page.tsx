import AgentFlow from "@/components/AgentFlow";

export const metadata = {
    title: "Agent Orchestration | Vergil",
    description: "Visualizing the collaboration of multiple specialized agents in real-time.",
};

export default function OrchestrationPage() {
    return (
        <main className="w-full min-h-screen bg-slate-50">
            <AgentFlow />
        </main>
    );
}
