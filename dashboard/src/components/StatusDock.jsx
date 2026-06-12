const LEGEND = [
  { name: 'Yonge-University', color: 'bg-yellow-400' },
  { name: 'Bloor-Danforth', color: 'bg-green-500' },
  { name: 'Sheppard', color: 'bg-purple-500' }
];

const WarningIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
    <path d="M12 3 L22 20 H2 Z" />
    <rect x="11" y="9" width="2" height="5" fill="#0f172a" />
    <rect x="11" y="16" width="2" height="2" fill="#0f172a" />
  </svg>
);

const StatusDock = ({ trainCount, error }) => (
  <footer className="fixed inset-x-0 bottom-0 z-10 border-t border-white/10 bg-slate-900 px-6 py-3">
    <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3">
      <div className="flex flex-wrap items-center gap-6">
        <span className="flex items-center gap-2.5 font-mono text-sm font-semibold tracking-wide">
          <span className="relative flex h-2.5 w-2.5" aria-hidden="true">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
          </span>
          LIVE TRAINS: {trainCount}
        </span>

        {error && (
          <span
            role="alert"
            className="flex items-center gap-2 rounded-md bg-red-500/20 px-3 py-1.5 text-sm font-semibold text-red-400"
          >
            <WarningIcon />
            ALERT: {error}
          </span>
        )}
      </div>

      <ul className="flex flex-wrap items-center gap-6" aria-label="Line legend">
        {LEGEND.map((line) => (
          <li key={line.name} className="flex items-center gap-2 text-sm text-slate-200">
            <span className={`h-3 w-3 rounded-full ${line.color}`} aria-hidden="true" />
            {line.name}
          </li>
        ))}
      </ul>
    </div>
  </footer>
);

export default StatusDock;
