import Header from './components/Header.jsx';
import MapView from './components/MapView.jsx';
import AgentWidget from './components/AgentWidget.jsx';
import StatusDock from './components/StatusDock.jsx';
import { useMapState } from './hooks/useMapState.js';

const App = () => {
  const { trainCount, error } = useMapState();

  return (
    <div className="dot-grid min-h-screen bg-slate-950 text-white flex flex-col">
      <Header />

      <main className="relative flex-1 px-6 pb-24">
        <MapView />
        <AgentWidget />
      </main>

      <StatusDock trainCount={trainCount} error={error} />
    </div>
  );
};

export default App;
