'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const MAP_DIR = 'e:/マイドライブ/史書/map/js';
const OUT_FILE = 'e:/マイドライブ/史書/太平寰宇記/data/reference_geo.json';

const ctx = { window: {} };
vm.createContext(ctx);
for (const f of ['map_data.js', 'china_geo_data.js', 'atlas_snapshots.js', 'lore_data.js', 'zh_hant.js']) {
  vm.runInContext(fs.readFileSync(path.join(MAP_DIR, f), 'utf8'), ctx, { filename: f });
}

const W = ctx.window;

// Collect prefecture anchors & polygons prioritizing Northern Song (s_beisong_b0, s_beisong_a5, s_beisong_b), then Tang/Wudai/all
const snapOrder = [
  's_beisong_b0', 's_beisong_a5', 's_beisong_b', 's_beisong_b1', 's_beisong_a',
  's_wudai_e', 's_wudai_a', 's_tang_b', 's_tang_a', 's_nansong_a', 's_sui'
];
const allSnapKeys = [...new Set([...snapOrder, ...Object.keys(W.ATLAS_SNAPSHOTS)])];

const prefCoords = {};
const prefPolys = {};

for (const k of allSnapKeys) {
  const snap = W.ATLAS_SNAPSHOTS[k];
  if (!snap) continue;
  if (snap.prefectures) {
    for (const p of snap.prefectures) {
      if (p.title && p.anchor && !prefCoords[p.title]) {
        prefCoords[p.title] = p.anchor;
      }
      if (p.title && p.shape && !prefPolys[p.title] && k.startsWith('s_beisong')) {
        prefPolys[p.title] = {
          type: p.shape.type,
          coordinates: p.shape.coordinates
        };
      }
    }
  }
}

// Also collect settlements from DYNASTY_DATA and PLACE_GAZETTEER
const settlementCoords = {};
for (const d of W.DYNASTY_DATA || []) {
  for (const s of d.settlements || []) {
    if (s.name && s.coord && !settlementCoords[s.name]) {
      settlementCoords[s.name] = s.coord;
    }
  }
}
if (W.ATLAS_LORE_DATA && W.ATLAS_LORE_DATA.PLACE_GAZETTEER) {
  for (const [name, obj] of Object.entries(W.ATLAS_LORE_DATA.PLACE_GAZETTEER)) {
    if (obj.coord && !settlementCoords[name]) {
      settlementCoords[name] = obj.coord;
    }
  }
}

// Also Tang 15 Dao regions from s_tang_b and Beisong regions from s_beisong_b0
const tangRegions = (W.ATLAS_SNAPSHOTS.s_tang_b && W.ATLAS_SNAPSHOTS.s_tang_b.regions || []).map(r => ({
  title: r.title,
  anchor: r.anchor,
  shape: r.shape ? { type: r.shape.type, coordinates: r.shape.coordinates } : null
}));

const beisongPolities = (W.ATLAS_SNAPSHOTS.s_beisong_b0 && W.ATLAS_SNAPSHOTS.s_beisong_b0.polities || []).map(p => ({
  title: p.title,
  anchor: p.anchor,
  tint: p.tint,
  isPrimary: p.isPrimary,
  shape: p.shape ? { type: p.shape.type, coordinates: p.shape.coordinates } : null
}));

fs.writeFileSync(OUT_FILE, JSON.stringify({
  prefCoords,
  prefPolys,
  settlementCoords,
  tangRegions,
  beisongPolities,
  charT2S: (W.ZH_HANT_CONV && W.ZH_HANT_CONV.CHAR_T2S) || {}
}, null, 2), 'utf8');

console.log('Exported prefCoords:', Object.keys(prefCoords).length, 'prefPolys:', Object.keys(prefPolys).length, 'settlementCoords:', Object.keys(settlementCoords).length);
