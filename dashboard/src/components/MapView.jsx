const LINES = [
  {
    id: 'line-1',
    name: 'Yonge-University',
    color: '#facc15',
    points: '300,70 300,310 330,340 430,340 460,310 460,70'
  },
  {
    id: 'line-2',
    name: 'Bloor-Danforth',
    color: '#22c55e',
    points: '70,250 240,250 280,210 600,210 640,250 830,250'
  },
  {
    id: 'line-4',
    name: 'Sheppard',
    color: '#a855f7',
    points: '460,120 540,120 580,160 700,160'
  }
];

const STATIONS = [
  { x: 300, y: 70 }, { x: 300, y: 130 }, { x: 300, y: 270 },
  { x: 330, y: 340 }, { x: 380, y: 340 }, { x: 430, y: 340 },
  { x: 460, y: 270 }, { x: 460, y: 180 }, { x: 460, y: 70 },
  { x: 70, y: 250 }, { x: 150, y: 250 }, { x: 240, y: 250 },
  { x: 360, y: 210 }, { x: 530, y: 210 }, { x: 600, y: 210 },
  { x: 640, y: 250 }, { x: 730, y: 250 }, { x: 830, y: 250 },
  { x: 540, y: 120 }, { x: 620, y: 160 }, { x: 700, y: 160 }
];

const INTERCHANGES = [
  { x: 300, y: 210 }, { x: 460, y: 210 }, { x: 460, y: 120 }
];

const LIVE_TRAINS = [
  { x: 300, y: 180, color: '#facc15' },
  { x: 405, y: 340, color: '#facc15' },
  { x: 200, y: 250, color: '#22c55e' },
  { x: 565, y: 210, color: '#22c55e' },
  { x: 660, y: 160, color: '#a855f7' }
];

const PulsingTrain = ({ x, y, color }) => (
  <g>
    <circle cx={x} cy={y} r="6" fill={color} opacity="0.25">
      <animate attributeName="r" values="6;14;6" dur="1.8s" repeatCount="indefinite" />
      <animate attributeName="opacity" values="0.35;0;0.35" dur="1.8s" repeatCount="indefinite" />
    </circle>
    <circle cx={x} cy={y} r="5" fill={color} stroke="#020617" strokeWidth="1.5">
      <animate attributeName="r" values="4.5;6;4.5" dur="1.8s" repeatCount="indefinite" />
    </circle>
  </g>
);

const MapView = () => (
  <section
    aria-label="Live subway network map"
    className="mx-auto h-full max-w-5xl rounded-2xl border border-white/10 bg-white/[0.02] p-4"
  >
    <p className="mb-2 font-mono text-xs uppercase tracking-widest text-slate-500">
      Network overview
    </p>

    <svg viewBox="0 0 900 420" role="img" className="h-auto w-full">
      <title>Schematic of TTC Lines 1, 2 and 4 with live trains</title>

      {LINES.map((line) => (
        <polyline
          key={line.id}
          points={line.points}
          fill="none"
          stroke={line.color}
          strokeWidth="7"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}

      {STATIONS.map((s) => (
        <circle
          key={`${s.x}-${s.y}`}
          cx={s.x}
          cy={s.y}
          r="5.5"
          fill="#ffffff"
          stroke="#0f172a"
          strokeWidth="2.5"
        />
      ))}

      {INTERCHANGES.map((s) => (
        <circle
          key={`${s.x}-${s.y}`}
          cx={s.x}
          cy={s.y}
          r="8.5"
          fill="#ffffff"
          stroke="#0f172a"
          strokeWidth="3"
        />
      ))}

      {LIVE_TRAINS.map((t) => (
        <PulsingTrain key={`${t.x}-${t.y}`} {...t} />
      ))}
    </svg>
  </section>
);

export default MapView;
