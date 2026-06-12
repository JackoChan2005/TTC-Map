import { useState } from 'react';

const SparkIcon = () => (
  <svg viewBox="0 0 24 24" className="h-5 w-5 text-orange-400" fill="currentColor" aria-hidden="true">
    <path d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2z" />
    <circle cx="19" cy="4" r="1.6" />
    <circle cx="5" cy="19" r="1.3" />
  </svg>
);

const ACTIONS = ['Optimize Routing', 'Check Delay Context'];

const AgentWidget = () => {
  const [acknowledged, setAcknowledged] = useState(null);

  return (
    <aside
      aria-label="AI Operations Agent"
      className="absolute right-6 top-4 w-80 rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur-md"
    >
      <div className="flex items-center gap-2">
        <SparkIcon />
        <h2 className="text-sm font-semibold tracking-wide">AI Operations Agent</h2>
      </div>

      <p className="mt-3 font-mono text-xs leading-relaxed text-slate-300">
        <span className="text-orange-400">AGENT INSIGHTS:</span> Yellow Line capacity
        optimized. Green Line throughput delayed 10% near Bloor-Yonge. Auto-rerouting
        active.
      </p>

      <div className="mt-4 flex gap-2">
        {ACTIONS.map((action) => (
          <button
            key={action}
            type="button"
            onClick={() => setAcknowledged(action)}
            className="rounded-lg border border-white/20 px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:border-orange-400/60 hover:bg-white/10"
          >
            {action}
          </button>
        ))}
      </div>

      {acknowledged && (
        <p className="mt-3 font-mono text-[11px] text-emerald-400" role="status">
          ▸ {acknowledged} queued — agent responding…
        </p>
      )}
    </aside>
  );
};

export default AgentWidget;
