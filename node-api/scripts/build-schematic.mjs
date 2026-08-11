// Regenerates shared/layouts/schematic.json from the canonical topology.
// Run after build_network.py: node scripts/build-schematic.mjs

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildSchematicLayout } from './lib/schematic.mjs';

const sharedDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'shared');

const network = JSON.parse(fs.readFileSync(path.join(sharedDir, 'network.json'), 'utf8'));
const geographic = JSON.parse(fs.readFileSync(path.join(sharedDir, 'layouts', 'geographic.json'), 'utf8'));

const layout = buildSchematicLayout(network, geographic);
const outPath = path.join(sharedDir, 'layouts', 'schematic.json');
fs.writeFileSync(outPath, JSON.stringify(layout, null, 2));

console.log(`Wrote ${outPath} (${Object.keys(layout.stations).length} stations, ${layout.width}x${layout.height})`);
