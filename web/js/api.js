// All transit requests belong here. No static transit fallback or invented feed.
export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export async function request(path, params = {}) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null));
  const response = await fetch(`/api/v1/${path}${query.size ? `?${query}` : ''}`, {
    signal: AbortSignal.timeout(15000), cache: 'no-store'
  });
  let result;
  try { result = await response.json(); } catch { throw new ApiError('The server returned an unreadable response.', response.status); }
  if (!response.ok) throw new ApiError(result?.message || 'Transit data is unavailable.', response.status);
  return result;
}

export const api = {
  state: () => request('map-state'),
  health: () => request('health'),
  departures: (route, at) => request('departures', { route, at }),
  // Station coordinates and schematic now come from the same atomic response.
  config: () => request('map-config')
};
