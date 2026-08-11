// DOM-only SVG rendering of precomputed view models. No fetch, no logic —
// everything it draws was built and validated in mapModel.js.

const SVG_NS = 'http://www.w3.org/2000/svg';

const svgEl = (tag, attrs) => {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attrs)) {
    node.setAttribute(name, value);
  }
  return node;
};

const withTitle = (node, text) => {
  const title = document.createElementNS(SVG_NS, 'title');
  title.textContent = text;
  node.appendChild(title);
  return node;
};

const STATION_RADIUS = 7;
const TERMINAL_SIZE = 10;
const INTERCHANGE_SIZE = 8;

const stationNode = (marker) => {
  if (marker.kind === 'interchange') {
    const s = INTERCHANGE_SIZE;
    return svgEl('rect', {
      x: marker.x - s,
      y: marker.y - s,
      width: s * 2,
      height: s * 2,
      rx: 3,
      class: 'station station-interchange'
    });
  }

  if (marker.kind === 'terminal') {
    const s = TERMINAL_SIZE;
    const points = `${marker.x},${marker.y - s} ${marker.x + s},${marker.y + s * 0.8} ${marker.x - s},${marker.y + s * 0.8}`;
    return svgEl('polygon', { points, class: 'station station-terminal' });
  }

  return svgEl('circle', {
    cx: marker.x,
    cy: marker.y,
    r: STATION_RADIUS,
    class: 'station'
  });
};

export const drawBase = (svg, layout, linePaths, stationMarkers) => {
  svg.setAttribute('viewBox', `0 0 ${layout.width} ${layout.height}`);
  svg.replaceChildren();

  for (const line of linePaths) {
    const points = line.points.map((p) => `${p.x},${p.y}`).join(' ');
    svg.appendChild(svgEl('polyline', {
      points,
      class: 'line-path',
      stroke: line.color
    }));
  }

  for (const marker of stationMarkers) {
    svg.appendChild(withTitle(stationNode(marker), marker.name));
  }

  const trainLayer = svgEl('g', { class: 'train-layer' });
  svg.appendChild(trainLayer);
  return trainLayer;
};

const TRAIN_W = 22;
const TRAIN_H = 12;

export const drawTrains = (trainLayer, trainMarkers) => {
  trainLayer.replaceChildren();

  for (const train of trainMarkers) {
    const capsule = svgEl('rect', {
      x: -TRAIN_W / 2,
      y: -TRAIN_H / 2,
      width: TRAIN_W,
      height: TRAIN_H,
      rx: TRAIN_H / 2,
      class: 'train',
      fill: train.color,
      transform: `translate(${train.x} ${train.y}) rotate(${train.angle})`
    });
    trainLayer.appendChild(withTitle(capsule, `Train near ${train.label}`));
  }
};

export const renderLegend = (container, linePaths) => {
  container.replaceChildren(...linePaths.map((line) => {
    const item = document.createElement('span');
    item.className = 'legend-item';

    const swatch = document.createElement('span');
    swatch.className = 'legend-swatch';
    swatch.style.background = line.color;

    item.append(swatch, document.createTextNode(line.name));
    return item;
  }));
};
