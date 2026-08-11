// Octolinear path geometry. Pure functions, no DOM.

const EPS = 1e-6;

// Path between two points using only horizontal/vertical/45-degree segments:
// a single segment when already aligned, otherwise diagonal-then-straight.
export const octolinearPoints = (a, b) => {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const adx = Math.abs(dx);
  const ady = Math.abs(dy);

  if (adx < EPS || ady < EPS || Math.abs(adx - ady) < EPS) {
    return [a, b];
  }

  const diagonal = Math.min(adx, ady);
  const bend = {
    x: a.x + Math.sign(dx) * diagonal,
    y: a.y + Math.sign(dy) * diagonal
  };
  return [a, bend, b];
};

export const pathLength = (points) => {
  let total = 0;
  for (let i = 1; i < points.length; i += 1) {
    total += Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y);
  }
  return total;
};

// Point and heading at fraction t (clamped to [0,1]) along a polyline.
export const pointAlongPath = (points, t) => {
  if (points.length === 1) {
    return { x: points[0].x, y: points[0].y, angle: 0 };
  }

  const clamped = Math.min(Math.max(t, 0), 1);
  const target = pathLength(points) * clamped;

  let walked = 0;
  for (let i = 1; i < points.length; i += 1) {
    const a = points[i - 1];
    const b = points[i];
    const segment = Math.hypot(b.x - a.x, b.y - a.y);

    if (walked + segment >= target || i === points.length - 1) {
      const f = segment < EPS ? 0 : (target - walked) / segment;
      return {
        x: a.x + (b.x - a.x) * f,
        y: a.y + (b.y - a.y) * f,
        angle: (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI
      };
    }
    walked += segment;
  }

  const last = points[points.length - 1];
  return { x: last.x, y: last.y, angle: 0 };
};
