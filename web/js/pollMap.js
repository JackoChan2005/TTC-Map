// Serialize refreshes and pair state with its exact map generation.
export const createMapPoller = ({ fetchConfig, fetchState, onConfig, onState }) => {
  let generation = null;
  let busy = false;
  const load = async () => {
    const config = await fetchConfig();
    if (!config.generation) throw new Error('Missing map generation');
    onConfig(config);
    generation = config.generation;
  };
  return async () => {
    if (busy) return;
    busy = true;
    try {
      if (generation === null) await load();
      const state = await fetchState();
      if (state.generation !== generation) await load();
      if (state.generation !== generation) throw new Error('Map changed; waiting for a matching update');
      onState(state);
    } finally {
      busy = false;
    }
  };
};
