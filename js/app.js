/**
 * 『太平寰宇記』北宋太宗朝天下輿図 インタラクティブ歴史GISコントローラ（高速描画・遅延読込最適化版）
 */
(function () {
  'use strict';

  const RAD_TO_DEG = 180 / Math.PI;
  const DEG_TO_RAD = Math.PI / 180;

  function escHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function fmtNum(n) {
    if (n == null || isNaN(n)) return '記載なし';
    return Number(n).toLocaleString('ja-JP');
  }

  class MercatorProjector {
    constructor(width, height, bounds) {
      this.width = width;
      this.height = height;
      this.bounds = bounds;
      const spanLng = bounds.east - bounds.west;
      const spanLat = (this._latToMerc(bounds.north) - this._latToMerc(bounds.south)) * RAD_TO_DEG;
      this.scale = Math.min(width / spanLng, height / spanLat);
      this.padX = (width - spanLng * this.scale) * 0.5;
      this.padY = (height - spanLat * this.scale) * 0.5;
      this.northMerc = this._latToMerc(bounds.north);
    }

    _latToMerc(lat) {
      const clamped = Math.max(-80, Math.min(80, lat));
      return Math.log(Math.tan(Math.PI * 0.25 + clamped * DEG_TO_RAD * 0.5));
    }

    toScreen(lng, lat) {
      const x = (lng - this.bounds.west) * this.scale + this.padX;
      const y = (this.northMerc - this._latToMerc(lat)) * RAD_TO_DEG * this.scale + this.padY;
      return [x, y];
    }

    ringToSvgPath(ring) {
      if (!ring || !ring.length) return '';
      let out = '';
      for (let i = 0; i < ring.length; i++) {
        const [px, py] = this.toScreen(ring[i][0], ring[i][1]);
        out += (i === 0 ? 'M' : 'L') + px.toFixed(2) + ' ' + py.toFixed(2);
      }
      return out + 'Z';
    }

    lineToSvgPath(line) {
      if (!line || line.length < 2) return '';
      let out = '';
      for (let i = 0; i < line.length; i++) {
        const [px, py] = this.toScreen(line[i][0], line[i][1]);
        out += (i === 0 ? 'M' : 'L') + px.toFixed(2) + ' ' + py.toFixed(2);
      }
      return out;
    }
  }

  const LM_CAT_COLORS = {
    山岳: '#6e5034',
    水系: '#2b6a8c',
    故城: '#9e3d2b',
    関津: '#b5452f',
    陵墓: '#6c4b7d',
    祠廟: '#b87d1e',
    亭台: '#3d7357',
    古跡: '#5d554c',
  };

  const SIYI_DIR_CONF = {
    siyi_dongyi: { fill: '#1b7a70', stroke: '#0e4a44', label: '東夷' },
    siyi_nanman: { fill: '#c04829', stroke: '#7d1e08', label: '南蠻' },
    siyi_xirong: { fill: '#d97706', stroke: '#8c4800', label: '西戎' },
    siyi_beidi: { fill: '#4a5568', stroke: '#212732', label: '北狄' },
  };

  class TaipingAtlasApp {
    constructor() {
      this.data = window.TAIPING_ATLAS_DATA;
      this.projector = new MercatorProjector(1000, 700, {
        west: 66,
        east: 142,
        south: 14,
        north: 55,
      });

      this.camera = { x: 0, y: 0, k: 1.0 };
      this.fontScale = 1.0;
      this.activeDaoId = 'ALL';
      this.activeSiyiSub = 'ALL';
      this.selectedPref = null;
      this.selectedCounty = null;
      this.selectedLandmark = null;
      this.selectedSiyi = null;
      this.displayMode = 'polity'; // 'polity' | 'network' | 'household' | 'landmarks'
      this.activeLmCat = 'ALL';

      this.prefByName = new Map();
      this.prefById = new Map();
      this.daoById = new Map();
      this.countiesByPref = new Map();
      this.landmarksByPref = new Map();
      this.edgesBySource = new Map();

      this.textsLoaded = false;
      this._textsCallbacks = [];
      this._renderedPrefKey = null;
      this._hoveredEl = null;
      this._rafCamera = 0;
      this._detailTimer = 0;
      this._movingTimer = 0;
      this._viewportRect = null;

      this._indexData();
      this._cacheDom();
      this._initBaseMap();
      this._initDaoDock();
      this._bindEvents();
      this.renderAll();
      this.updateSidePane();
      this.updateLegend();

      // Defer loading of the 5.5MB detailed texts bundle until after initial paint
      requestAnimationFrame(() => {
        setTimeout(() => this._loadTextsAsync(), 40);
      });
    }

    _indexData() {
      for (const d of this.data.daos) {
        let pathD = '';
        for (const r of d.rings || []) pathD += this.projector.ringToSvgPath(r);
        d._pathD = pathD;
        if (d.anchor) {
          const [ax, ay] = this.projector.toScreen(d.anchor[0], d.anchor[1]);
          d._ax = ax;
          d._ay = ay;
        }
        this.daoById.set(d.id, d);
      }

      for (const p of this.data.prefectures) {
        const [sx, sy] = this.projector.toScreen(p.coord[0], p.coord[1]);
        p._sx = sx;
        p._sy = sy;
        if (p.trilaterated_coord) {
          const [tx, ty] = this.projector.toScreen(p.trilaterated_coord[0], p.trilaterated_coord[1]);
          p._tx = tx;
          p._ty = ty;
        }
        let pathD = '';
        for (const r of p.rings || []) pathD += this.projector.ringToSvgPath(r);
        p._pathD = pathD;
        if (!p.distances) p.distances = [];
        if (!p.figures) p.figures = [];
        if (!p.figures_ja) p.figures_ja = [];

        this.prefByName.set(p.name, p);
        this.prefById.set(p.id, p);
        this.countiesByPref.set(p.name, []);
        this.landmarksByPref.set(p.name, []);
        this.edgesBySource.set(p.name, []);
      }

      // Capitals alias lookup
      if (this.prefByName.has('開封府')) this.prefByName.set('東京', this.prefByName.get('開封府'));
      if (this.prefByName.has('河南府')) this.prefByName.set('西京', this.prefByName.get('河南府'));
      if (this.prefByName.has('雍州')) this.prefByName.set('長安', this.prefByName.get('雍州'));

      for (const e of this.data.edges) {
        const [x1, y1] = this.projector.toScreen(e.source_coord[0], e.source_coord[1]);
        const [x2, y2] = this.projector.toScreen(e.target_coord[0], e.target_coord[1]);
        e._x1 = x1;
        e._y1 = y1;
        e._x2 = x2;
        e._y2 = y2;
        if (this.edgesBySource.has(e.source)) {
          this.edgesBySource.get(e.source).push(e);
        }
      }

      for (const c of this.data.counties) {
        const [sx, sy] = this.projector.toScreen(c.coord[0], c.coord[1]);
        c._sx = sx;
        c._sy = sy;
        if (this.countiesByPref.has(c.prefecture)) {
          this.countiesByPref.get(c.prefecture).push(c);
        }
      }

      // Unpack compact landmarks if stored as tuples [n, c, cnty, p, d, v, dir, li, x, y]
      const rawLms = this.data.landmarks;
      for (let i = 0; i < rawLms.length; i++) {
        let lm = rawLms[i];
        if (Array.isArray(lm)) {
          lm = {
            n: lm[0],
            c: lm[1],
            cnty: lm[2],
            p: lm[3],
            d: lm[4],
            v: lm[5],
            dir: lm[6],
            li: lm[7],
            xy: [lm[8], lm[9]],
            desc: '',
            desc_ja: '',
            cit: [],
          };
          rawLms[i] = lm;
        }
        const [sx, sy] = this.projector.toScreen(lm.xy[0], lm.xy[1]);
        lm._sx = sx;
        lm._sy = sy;
        if (this.landmarksByPref.has(lm.p)) {
          this.landmarksByPref.get(lm.p).push(lm);
        }
      }

      for (const s of this.data.siyi) {
        if (s.coord) {
          const [sx, sy] = this.projector.toScreen(s.coord[0], s.coord[1]);
          s._sx = sx;
          s._sy = sy;
        }
      }

      const [chX, chY] = this.projector.toScreen(108.93, 34.27);
      this._changAnScreen = [chX, chY];
    }

    _loadTextsAsync() {
      if (this.textsLoaded) return;
      if (window.TAIPING_ATLAS_TEXTS) {
        this.hydrateTexts(window.TAIPING_ATLAS_TEXTS);
        return;
      }
      if (this._loadingTextsScript) return;
      this._loadingTextsScript = true;
      const s = document.createElement('script');
      s.src = 'js/taiping_atlas_texts.js';
      s.async = true;
      document.body.appendChild(s);
    }

    hydrateTexts(texts) {
      if (!texts || this.textsLoaded) return;
      const pMap = texts.prefectures || {};
      for (const p of this.data.prefectures) {
        const tp = pMap[p.id];
        if (tp) {
          p.history = tp.history || '';
          p.history_ja = tp.history_ja || '';
          p.customs = tp.customs || '';
          p.customs_ja = tp.customs_ja || '';
          p.surnames = tp.surnames || '';
          p.surnames_ja = tp.surnames_ja || '';
          p.figures = tp.figures || [];
          p.figures_ja = tp.figures_ja || [];
          p.distances = tp.distances || [];
        }
      }

      const cList = texts.counties || [];
      for (let i = 0; i < this.data.counties.length && i < cList.length; i++) {
        const tc = cList[i];
        if (tc) {
          this.data.counties[i].intro = tc[0] || '';
          this.data.counties[i].intro_ja = tc[1] || '';
        }
      }

      const lmList = texts.landmarks || [];
      for (let i = 0; i < this.data.landmarks.length && i < lmList.length; i++) {
        const tlm = lmList[i];
        if (tlm) {
          this.data.landmarks[i].desc = tlm[0] || '';
          this.data.landmarks[i].desc_ja = tlm[1] || tlm[0] || '';
          this.data.landmarks[i].cit = tlm[2] || [];
        }
      }

      const sList = texts.siyi || [];
      for (let i = 0; i < this.data.siyi.length && i < sList.length; i++) {
        const ts = sList[i];
        if (ts) {
          Object.assign(this.data.siyi[i], ts);
        }
      }

      this.textsLoaded = true;
      // Refresh open detail card if user clicked one before texts finished loading
      if (!this.genCard.classList.contains('is-hidden')) {
        if (this._openCardType === 'pref' && this.selectedPref) {
          this.openPrefectureDetail(this.selectedPref, false);
        } else if (this._openCardType === 'county' && this.selectedCounty) {
          this.openCountyDetail(this.selectedCounty, false);
        } else if (this._openCardType === 'lm' && this.selectedLandmark) {
          this.openLandmarkDetail(this.selectedLandmark, false);
        } else if (this._openCardType === 'siyi' && this.selectedSiyi) {
          this.openSiyiDetail(this.selectedSiyi, false);
        }
      }
    }

    _cacheDom() {
      this.viewportFrame = document.getElementById('viewport-frame');
      this.svg = document.getElementById('atlas-svg');
      this.cameraRig = document.getElementById('camera-rig');
      this.grpTerrain = document.getElementById('grp-terrain');
      this.grpProvinces = document.getElementById('grp-provinces');
      this.grpProvNames = document.getElementById('grp-prov-names');
      this.grpRivers = document.getElementById('grp-rivers');
      this.grpDaos = document.getElementById('grp-daos');
      this.grpPrefectures = document.getElementById('grp-prefectures');
      this.grpNetwork = document.getElementById('grp-network');
      this.grpTrilat = document.getElementById('grp-trilat');
      this.grpHouseholds = document.getElementById('grp-households');
      this.grpCounties = document.getElementById('grp-counties');
      this.grpLandmarks = document.getElementById('grp-landmarks');
      this.grpSiyi = document.getElementById('grp-siyi');
      this.grpSettlements = document.getElementById('grp-settlements');
      this.grpActiveRays = document.getElementById('grp-active-rays');

      this.hoverTip = document.getElementById('hover-tip');
      this.genCard = document.getElementById('genealogy-card');
      this.genKicker = document.getElementById('txt-genealogy-kicker');
      this.genHeading = document.getElementById('genealogy-heading');
      this.genSub = document.getElementById('genealogy-sub');
      this.genBody = document.getElementById('genealogy-body');

      this.chkDaos = document.getElementById('chk-daos');
      this.chkPrefectures = document.getElementById('chk-prefectures');
      this.chkSettlements = document.getElementById('chk-settlements');
      this.chkNetwork = document.getElementById('chk-network');
      this.chkCounties = document.getElementById('chk-counties');
      this.chkLandmarks = document.getElementById('chk-landmarks');
      this.chkSiyi = document.getElementById('chk-siyi');
      this.chkTrilat = document.getElementById('chk-trilat');
      this.chkTerrain = document.getElementById('chk-terrain');
      this.chkProvinces = document.getElementById('chk-provinces');
      this.chkProvNames = document.getElementById('chk-prov-names');
    }

    _initBaseMap() {
      // 1. Modern Provinces
      const provs = window.PROVINCE_OUTLINES || [];
      let provPaths = '';
      let provLabels = '';
      for (const p of provs) {
        let d = '';
        for (const r of p.rings || []) {
          d += this.projector.ringToSvgPath(r);
        }
        if (d) {
          provPaths += `<path class="province-path" d="${d}" fill="none" stroke="rgba(120,108,92,0.28)" stroke-width="0.6" stroke-dasharray="2 2" vector-effect="non-scaling-stroke"/>`;
        }
        if (p.hub) {
          const [hx, hy] = this.projector.toScreen(p.hub[0], p.hub[1]);
          provLabels += `<g transform="translate(${hx.toFixed(1)},${hy.toFixed(1)})" pointer-events="none"><g class="inv-scale"><text x="0" y="0" text-anchor="middle" font-size="9.5" fill="rgba(90,80,70,0.45)">${escHtml(p.title)}</text></g></g>`;
        }
      }
      this.grpProvinces.innerHTML = provPaths;
      this.grpProvNames.innerHTML = provLabels;

      // 2. Northern Song Period Hydrography (Year = 980 CE)
      const hydro = window.HYDRO_DATA;
      if (hydro) {
        let hHtml = '';
        const yr = 980;
        for (const l of hydro.lakes || []) {
          if ((l.appear != null && yr < l.appear) || (l.vanish != null && yr >= l.vanish)) continue;
          let d = '';
          for (const r of l.rings || []) d += this.projector.ringToSvgPath(r);
          if (d) {
            hHtml += `<path d="${d}" fill="rgba(116,162,178,0.42)" stroke="rgba(75,126,145,0.55)" stroke-width="0.5" vector-effect="non-scaling-stroke"/>`;
          }
        }
        for (const r of hydro.rivers || []) {
          if ((r.appear != null && yr < r.appear) || (r.vanish != null && yr >= r.vanish)) continue;
          let d = '';
          for (const ln of r.lines || []) d += this.projector.lineToSvgPath(ln);
          if (d) {
            const sw = r.rank === 1 ? 1.35 : 0.8;
            const op = r.rank === 1 ? 0.68 : 0.45;
            hHtml += `<path d="${d}" fill="none" stroke="rgba(68,122,148,${op})" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`;
          }
        }
        this.grpRivers.innerHTML = hHtml;
      }
    }

    _initDaoDock() {
      const dock = document.getElementById('dao-dock-list');
      let html = `<button type="button" class="dao-pill-btn is-active" data-dao="ALL"><span class="dao-dot" style="background:#b5452f"></span>天下十三道総覧</button>`;
      for (const d of this.data.daos) {
        html += `<button type="button" class="dao-pill-btn" data-dao="${escHtml(d.id)}"><span class="dao-dot" style="background:${escHtml(d.tint || '#888')}"></span>${escHtml(d.name)}</button>`;
      }
      dock.innerHTML = html;
      dock.addEventListener('click', (e) => {
        const btn = e.target.closest('.dao-pill-btn');
        if (btn) this.selectDao(btn.dataset.dao, true);
      });
    }

    _markCameraMoving() {
      this.viewportFrame.classList.add('is-camera-moving');
      this.hoverTip.classList.add('is-hidden');
      if (this._movingTimer) clearTimeout(this._movingTimer);
      this._movingTimer = setTimeout(() => {
        this.viewportFrame.classList.remove('is-camera-moving');
        this._viewportRect = null;
      }, 140);
    }

    _scheduleDynamicLayers(delayMs = 70) {
      if (this._detailTimer) clearTimeout(this._detailTimer);
      this._detailTimer = setTimeout(() => {
        this._detailTimer = 0;
        this.renderDynamicDetailLayers();
        if (this.selectedPref) this.renderActiveRays(this.selectedPref);
      }, delayMs);
    }

    _bindEvents() {
      // Pan & Zoom on SVG (rAF-throttled)
      let isDragging = false;
      let startX = 0;
      let startY = 0;
      let dragMoved = false;
      let svgRect = null;

      this.svg.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return;
        isDragging = true;
        dragMoved = false;
        startX = e.clientX;
        startY = e.clientY;
        svgRect = this.svg.getBoundingClientRect();
        this.svg.style.cursor = 'grabbing';
      });

      window.addEventListener(
        'mousemove',
        (e) => {
          if (!isDragging) return;
          const dx = e.clientX - startX;
          const dy = e.clientY - startY;
          if (!dragMoved && Math.hypot(dx, dy) > 3) {
            dragMoved = true;
            this._markCameraMoving();
          }
          startX = e.clientX;
          startY = e.clientY;
          const rect = svgRect || this.svg.getBoundingClientRect();
          const scaleX = 1000 / rect.width;
          const scaleY = 700 / rect.height;
          this.camera.x += dx * scaleX;
          this.camera.y += dy * scaleY;
          if (!this._rafCamera) {
            this._rafCamera = requestAnimationFrame(() => {
              this._rafCamera = 0;
              this._applyCamera();
            });
          }
        },
        { passive: true }
      );

      window.addEventListener('mouseup', () => {
        if (isDragging) {
          isDragging = false;
          svgRect = null;
          this.svg.style.cursor = '';
          if (dragMoved) {
            this._scheduleDynamicLayers(20);
          }
        }
      });

      this.svg.addEventListener(
        'wheel',
        (e) => {
          e.preventDefault();
          this._markCameraMoving();
          const rect = this._viewportRect || (this._viewportRect = this.svg.getBoundingClientRect());
          const mx = ((e.clientX - rect.left) / rect.width) * 1000;
          const my = ((e.clientY - rect.top) / rect.height) * 700;
          const factor = e.deltaY < 0 ? 1.24 : 1 / 1.24;
          const nextK = Math.max(0.85, Math.min(120.0, this.camera.k * factor));
          const ratio = nextK / this.camera.k;
          this.camera.x = mx - (mx - this.camera.x) * ratio;
          this.camera.y = my - (my - this.camera.y) * ratio;
          this.camera.k = nextK;
          if (!this._rafCamera) {
            this._rafCamera = requestAnimationFrame(() => {
              this._rafCamera = 0;
              this._applyCamera();
            });
          }
          this._scheduleDynamicLayers(75);
        },
        { passive: false }
      );

      // Single Delegated Click Listener on SVG
      this.svg.addEventListener('click', (e) => {
        if (dragMoved) return;
        const target = e.target.closest('[data-pref-id], [data-siyi-idx], [data-cnty-idx], [data-lm-idx]');
        if (!target) return;
        e.stopPropagation();
        if (target.dataset.prefId) {
          const p = this.prefById.get(target.dataset.prefId);
          if (p) this.openPrefectureDetail(p, false);
        } else if (target.dataset.siyiIdx != null) {
          const s = this.data.siyi[Number(target.dataset.siyiIdx)];
          if (s) this.openSiyiDetail(s, true);
        } else if (target.dataset.cntyIdx != null) {
          const c = this.data.counties[Number(target.dataset.cntyIdx)];
          if (c) this.openCountyDetail(c, true);
        } else if (target.dataset.lmIdx != null) {
          const lm = this.data.landmarks[Number(target.dataset.lmIdx)];
          if (lm) this.openLandmarkDetail(lm, true);
        }
      });

      // Single Delegated Hover Listener on SVG
      this.svg.addEventListener(
        'mousemove',
        (e) => {
          if (isDragging) return;
          const target = e.target.closest('.pref-poly, .pref-node, .siyi-marker, .cnty-node, .lm-node');
          if (!target) {
            if (this._hoveredEl) {
              this._hoveredEl = null;
              this.hoverTip.classList.add('is-hidden');
              if (!this.selectedPref) this.grpActiveRays.innerHTML = '';
            }
            return;
          }
          if (target !== this._hoveredEl) {
            this._hoveredEl = target;
            if (target.dataset.prefId) {
              const p = this.prefById.get(target.dataset.prefId);
              if (p) {
                this._showHoverTip(
                  e,
                  `<strong>${escHtml(p.name)}</strong>（${escHtml(p.dao)} · ${escHtml(p.vol)}）<br/>治所: ${escHtml(p.seat || '郭下')} · 領県: ${p.county_names.length} · 皇朝戸: ${fmtNum(p.song_total_households)}`
                );
                if (!this.selectedPref) this.renderActiveRays(p);
              }
            } else if (target.dataset.siyiIdx != null) {
              const s = this.data.siyi[Number(target.dataset.siyiIdx)];
              if (s) {
                const distStr = s.distance_chang_an_li ? ` · 長安より${fmtNum(s.distance_chang_an_li)}里` : '';
                const shortPrev = s.short_preview || (s.customs_ja || s.customs || s.history_ja || '').slice(0, 60);
                this._showHoverTip(
                  e,
                  `<strong>${escHtml(s.name)}</strong>（${escHtml(s.dao)} · ${escHtml(s.vol)}${distStr}）${shortPrev ? `<br/><span style="font-size:11px;color:#eee">${escHtml(shortPrev)}</span>` : ''}`
                );
                if (s.distance_chang_an_li && s._sx != null) {
                  this.renderSiyiRay(s);
                }
              }
            } else if (target.dataset.cntyIdx != null) {
              const c = this.data.counties[Number(target.dataset.cntyIdx)];
              if (c) {
                this._showHoverTip(
                  e,
                  `<strong>${escHtml(c.name)}</strong>（${escHtml(c.prefecture)}管轄 · ${escHtml(c.dao)}）`
                );
              }
            } else if (target.dataset.lmIdx != null) {
              const lm = this.data.landmarks[Number(target.dataset.lmIdx)];
              if (lm) {
                this._showHoverTip(
                  e,
                  `<strong>【${escHtml(lm.c)}】${escHtml(lm.n)}</strong>（${escHtml(lm.p)}${escHtml(lm.cnty)}）`
                );
              }
            }
          } else {
            this._moveHoverTip(e);
          }
        },
        { passive: true }
      );

      this.svg.addEventListener('mouseleave', () => {
        this._hoveredEl = null;
        this.hoverTip.classList.add('is-hidden');
        if (!this.selectedPref) this.grpActiveRays.innerHTML = '';
      });

      // Reset camera & Zoom buttons
      document.getElementById('act-reset-camera').addEventListener('click', () => {
        this.selectDao('ALL', true);
      });
      const btnZoomIn = document.getElementById('act-zoom-in');
      const btnZoomOut = document.getElementById('act-zoom-out');
      if (btnZoomIn) {
        btnZoomIn.addEventListener('click', () => this.zoomByFactor(1.45));
      }
      if (btnZoomOut) {
        btnZoomOut.addEventListener('click', () => this.zoomByFactor(1 / 1.45));
      }
      document.getElementById('act-home').addEventListener('click', (e) => {
        e.preventDefault();
        this.selectDao('ALL', true);
      });

      // Backbar
      document.getElementById('polity-backbar').addEventListener('click', () => {
        this.selectDao('ALL', true);
      });

      // Prev / Next Dao buttons
      const daoOrder = ['ALL', ...this.data.daos.map((d) => d.id)];
      document.getElementById('act-vol-prev').addEventListener('click', () => {
        const idx = daoOrder.indexOf(this.activeDaoId);
        const nextIdx = (idx - 1 + daoOrder.length) % daoOrder.length;
        this.selectDao(daoOrder[nextIdx], true);
      });
      document.getElementById('act-vol-next').addEventListener('click', () => {
        const idx = daoOrder.indexOf(this.activeDaoId);
        const nextIdx = (idx + 1) % daoOrder.length;
        this.selectDao(daoOrder[nextIdx], true);
      });

      // Mode switch buttons
      document.querySelectorAll('.mode-switch-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          document.querySelectorAll('.mode-switch-btn').forEach((b) => b.classList.remove('is-active'));
          btn.classList.add('is-active');
          this.displayMode = btn.dataset.mode;
          const lmBar = document.getElementById('lm-cat-bar');
          if (this.displayMode === 'landmarks') {
            lmBar.classList.remove('is-hidden');
            this.chkLandmarks.checked = true;
          } else {
            lmBar.classList.add('is-hidden');
            this.chkLandmarks.checked = false;
          }
          if (this.displayMode === 'network') {
            this.chkNetwork.checked = true;
            this.chkTrilat.checked = true;
          } else {
            this.chkNetwork.checked = false;
            this.chkTrilat.checked = false;
          }
          this.renderAll();
          this.updateLegend();
        });
      });

      // Landmark Category Filter Pills
      document.querySelectorAll('.lm-cat-pill').forEach((btn) => {
        btn.addEventListener('click', () => {
          document.querySelectorAll('.lm-cat-pill').forEach((b) => b.classList.remove('is-active'));
          btn.classList.add('is-active');
          this.activeLmCat = btn.dataset.cat;
          this.renderDynamicDetailLayers();
        });
      });

      // Layer menu toggle
      const btnLayers = document.getElementById('act-layers-menu');
      const popLayers = document.getElementById('layers-popover');
      btnLayers.addEventListener('click', (e) => {
        e.stopPropagation();
        const hidden = popLayers.classList.toggle('is-hidden');
        btnLayers.classList.toggle('is-active', !hidden);
      });
      document.addEventListener('click', (e) => {
        if (!popLayers.contains(e.target) && e.target !== btnLayers) {
          popLayers.classList.add('is-hidden');
          btnLayers.classList.remove('is-active');
        }
      });

      // Layer checkboxes
      [
        this.chkDaos,
        this.chkPrefectures,
        this.chkSettlements,
        this.chkNetwork,
        this.chkCounties,
        this.chkLandmarks,
        this.chkSiyi,
        this.chkTrilat,
        this.chkTerrain,
        this.chkProvinces,
        this.chkProvNames,
      ].forEach((chk) => {
        chk.addEventListener('change', () => {
          this.grpTerrain.classList.toggle('is-hidden', !this.chkTerrain.checked);
          this.grpRivers.classList.toggle('is-hidden', !this.chkTerrain.checked);
          this.grpProvinces.classList.toggle('is-hidden', !this.chkProvinces.checked);
          this.grpProvNames.classList.toggle('is-hidden', !this.chkProvNames.checked);
          this.renderAll();
        });
      });

      // Side pane collapse toggle
      const shell = document.getElementById('atlas-shell');
      document.getElementById('act-toggle-pane').addEventListener('click', () => {
        shell.classList.toggle('pane-collapsed');
        this._viewportRect = null;
      });

      // Detail card close & expand
      document.getElementById('act-close-genealogy').addEventListener('click', () => {
        this.genCard.classList.add('is-hidden');
        this.selectedPref = null;
        this._openCardType = null;
        this.grpActiveRays.innerHTML = '';
        this.renderPrefectures();
        this.renderDynamicDetailLayers();
      });
      document.getElementById('act-expand-genealogy').addEventListener('click', () => {
        this.genCard.classList.toggle('is-expanded');
      });

      // Modal open / close
      const modalWrap = document.getElementById('pipeline-modal-wrap');
      document.getElementById('act-data-modal').addEventListener('click', () => {
        modalWrap.classList.remove('is-hidden');
      });
      document.getElementById('act-close-modal').addEventListener('click', () => {
        modalWrap.classList.add('is-hidden');
      });
      modalWrap.addEventListener('click', (e) => {
        if (e.target === modalWrap) modalWrap.classList.add('is-hidden');
      });

      // Search input
      const inpSearch = document.getElementById('inp-map-search');
      const resList = document.getElementById('map-search-results');
      inpSearch.addEventListener('input', () => {
        const q = inpSearch.value.trim();
        if (!q) {
          resList.classList.add('is-hidden');
          return;
        }
        this._loadTextsAsync();
        this._runSearch(q, resList);
      });
      inpSearch.addEventListener('focus', () => {
        this._loadTextsAsync();
        if (inpSearch.value.trim()) this._runSearch(inpSearch.value.trim(), resList);
      });

      // Font scale slider & buttons (A- / A+ / %)
      const inpFont = document.getElementById('inp-font-scale');
      const btnFontDec = document.getElementById('act-font-dec');
      const btnFontInc = document.getElementById('act-font-inc');
      const lblFont = document.getElementById('lbl-font-scale');
      if (inpFont) {
        let initPct = 100;
        try {
          const saved = Number(localStorage.getItem('taiping_font_scale'));
          if (saved >= 50 && saved <= 180) initPct = saved;
        } catch (_) {}
        this.setFontScale(initPct, false);

        inpFont.addEventListener('input', () => {
          this.setFontScale(Number(inpFont.value), true);
        });
        if (btnFontDec) {
          btnFontDec.addEventListener('click', () => {
            this.setFontScale(Math.round(this.fontScale * 100) - 10, true);
          });
        }
        if (btnFontInc) {
          btnFontInc.addEventListener('click', () => {
            this.setFontScale(Math.round(this.fontScale * 100) + 10, true);
          });
        }
        if (lblFont) {
          lblFont.addEventListener('click', () => {
            this.setFontScale(100, true);
          });
        }
      }
    }

    setFontScale(pct, rerender = true) {
      const clamped = Math.max(50, Math.min(180, Math.round(pct / 5) * 5));
      this.fontScale = clamped / 100;
      this.svg.style.setProperty('--text-scale', this.fontScale.toFixed(3));
      document.documentElement.style.setProperty('--text-scale', this.fontScale.toFixed(3));
      const inpFont = document.getElementById('inp-font-scale');
      const lblFont = document.getElementById('lbl-font-scale');
      if (inpFont) inpFont.value = String(clamped);
      if (lblFont) lblFont.textContent = `${clamped}%`;
      try {
        localStorage.setItem('taiping_font_scale', String(clamped));
      } catch (_) {}
      if (rerender) {
        this.renderDynamicDetailLayers();
      }
    }

    _applyCamera() {
      const { x, y, k } = this.camera;
      this.cameraRig.setAttribute('transform', `translate(${x.toFixed(2)},${y.toFixed(2)}) scale(${k.toFixed(4)})`);
      const visualBoost = k > 1.0 ? Math.min(1.65, Math.pow(k, 0.24)) : 1.0;
      const invK = visualBoost / Math.max(1.0, k);
      this.svg.style.setProperty('--inv-k', invK.toFixed(5));
      const rawKm = 500 / k;
      const kmPerScreen = rawKm >= 10 ? Math.round(rawKm) : Number(rawKm.toFixed(1));
      const liPerScreen = Math.round(rawKm / 0.3721);
      const lbl = document.getElementById('scale-label-text');
      if (lbl) lbl.textContent = `${kmPerScreen} km (約${liPerScreen.toLocaleString()}宋里)`;
    }

    zoomByFactor(factor) {
      const mx = 500;
      const my = 350;
      const nextK = Math.max(0.85, Math.min(120.0, this.camera.k * factor));
      const ratio = nextK / this.camera.k;
      this.camera.x = mx - (mx - this.camera.x) * ratio;
      this.camera.y = my - (my - this.camera.y) * ratio;
      this.camera.k = nextK;
      this._applyCamera();
      this.renderDynamicDetailLayers();
      if (this.selectedPref) this.renderActiveRays(this.selectedPref);
    }

    flyToGeo(lon, lat, targetK = 3.2) {
      const [sx, sy] = this.projector.toScreen(lon, lat);
      const nextK = Math.max(1.0, Math.min(120.0, targetK));
      this.camera.k = nextK;
      this.camera.x = 500 - sx * nextK;
      this.camera.y = 350 - sy * nextK;
      this._applyCamera();
      this.renderDynamicDetailLayers();
    }

    selectDao(daoId, fly = true) {
      this.activeDaoId = daoId;
      document.querySelectorAll('.dao-pill-btn').forEach((b) => {
        b.classList.toggle('is-active', b.dataset.dao === daoId);
      });
      const backbar = document.getElementById('polity-backbar');
      const lblDao = document.getElementById('lbl-active-dao');

      if (daoId === 'ALL') {
        backbar.classList.add('is-hidden');
        lblDao.textContent = '全道総覧';
        if (fly) {
          this.camera = { x: 0, y: 0, k: 1.0 };
          this._applyCamera();
        }
      } else {
        backbar.classList.remove('is-hidden');
        const d = this.daoById.get(daoId);
        lblDao.textContent = d ? d.name : daoId;
        if (fly && d) {
          if (daoId === 'siyi') {
            this.camera = { x: 0, y: 0, k: 1.0 };
            this._applyCamera();
          } else if (d.anchor) {
            this.flyToGeo(d.anchor[0], d.anchor[1], 2.5);
          }
        }
      }
      this.renderAll();
      this.updateSidePane();
    }

    renderAll() {
      this.renderDaos();
      this.renderPrefectures();
      this.renderNetworkAndTrilat();
      this.renderHouseholdsLayer();
      this.renderSiyiLayer();
      this.renderSettlementsLayer();
      this.renderDynamicDetailLayers();
      if (this.selectedPref) {
        this.renderActiveRays(this.selectedPref);
      }
    }

    renderDaos() {
      if (!this.chkDaos.checked || this.activeDaoId === 'siyi') {
        this.grpDaos.innerHTML = '';
        return;
      }
      let html = '';
      for (const d of this.data.daos) {
        if (!d._pathD) continue;
        if (this.activeDaoId !== 'ALL' && this.activeDaoId !== d.id) continue;
        const fillOp = this.activeDaoId === d.id ? 0.25 : 0.16;
        html += `<path class="dao-poly" data-dao="${escHtml(d.id)}" d="${d._pathD}" fill="${escHtml(d.tint)}" fill-opacity="${fillOp}" stroke="${escHtml(d.tint)}"/>`;
        if (d._ax != null) {
          html += `<g transform="translate(${d._ax.toFixed(1)},${d._ay.toFixed(1)})" pointer-events="none"><g class="inv-scale"><text x="0" y="0" text-anchor="middle" font-family="var(--calligraphy-stack)" font-size="15.5" fill="${escHtml(d.tint)}" opacity="0.78">${escHtml(d.name)}</text></g></g>`;
        }
      }
      this.grpDaos.innerHTML = html;
    }

    renderPrefectures() {
      if (!this.chkPrefectures.checked || this.activeDaoId === 'siyi') {
        this.grpPrefectures.innerHTML = '';
        this._renderedPrefKey = null;
        return;
      }
      const key = `${this.activeDaoId}:${this.chkPrefectures.checked}`;
      if (this._renderedPrefKey === key) {
        // Fast O(1) selection class toggle without rebuilding 387 SVG paths
        const prevSel = this.grpPrefectures.querySelector('.pref-poly.is-selected');
        if (prevSel) prevSel.classList.remove('is-selected');
        if (this.selectedPref) {
          const nextSel = this.grpPrefectures.querySelector(`.pref-poly[data-pref-id="${this.selectedPref.id}"]`);
          if (nextSel) nextSel.classList.add('is-selected');
        }
        return;
      }
      this._renderedPrefKey = key;

      let html = '';
      for (const p of this.data.prefectures) {
        if (this.activeDaoId !== 'ALL' && p.dao_id !== this.activeDaoId) continue;
        if (!p._pathD) continue;
        const dMeta = this.daoById.get(p.dao_id);
        const tint = dMeta ? dMeta.tint : '#8f4b32';
        const isSel = this.selectedPref && this.selectedPref.id === p.id;
        html += `<path class="pref-poly${isSel ? ' is-selected' : ''}" data-pref-id="${escHtml(p.id)}" d="${p._pathD}" fill="${escHtml(tint)}"/>`;
      }
      this.grpPrefectures.innerHTML = html;
    }

    renderNetworkAndTrilat() {
      if (this.activeDaoId === 'siyi') {
        this.grpNetwork.innerHTML = '';
        this.grpTrilat.innerHTML = '';
        return;
      }
      // 1. 四至八到 Network
      if (!this.chkNetwork.checked && this.displayMode !== 'network') {
        this.grpNetwork.innerHTML = '';
      } else {
        let netHtml = '';
        const isNetMode = this.displayMode === 'network';
        for (const e of this.data.edges) {
          if (this.activeDaoId !== 'ALL') {
            const sp = this.prefByName.get(e.source);
            if (!sp || sp.dao_id !== this.activeDaoId) continue;
          }
          if (e.geodesic_km > 900 && !isNetMode) continue;
          let color = 'rgba(143, 75, 50, 0.25)';
          let sw = '0.85';
          if (isNetMode) {
            if (e.tortuosity >= 0.7 && e.tortuosity <= 1.35) {
              color = 'rgba(46, 115, 87, 0.52)';
            } else if (e.tortuosity < 0.7) {
              color = 'rgba(46, 95, 133, 0.52)';
            } else {
              color = 'rgba(181, 69, 47, 0.55)';
            }
            sw = '1.2';
          }
          netHtml += `<line x1="${e._x1.toFixed(1)}" y1="${e._y1.toFixed(1)}" x2="${e._x2.toFixed(1)}" y2="${e._y2.toFixed(1)}" stroke="${color}" stroke-width="${sw}" vector-effect="non-scaling-stroke" pointer-events="none"/>`;
        }
        this.grpNetwork.innerHTML = netHtml;
      }

      // 2. Trilateration Vectors
      if (!this.chkTrilat.checked) {
        this.grpTrilat.innerHTML = '';
      } else {
        let triHtml = '';
        for (const p of this.data.prefectures) {
          if (this.activeDaoId !== 'ALL' && p.dao_id !== this.activeDaoId) continue;
          if (p._tx == null || p.trilateration_error_km < 5) continue;
          triHtml += `<line class="trilat-line" x1="${p._sx.toFixed(1)}" y1="${p._sy.toFixed(1)}" x2="${p._tx.toFixed(1)}" y2="${p._ty.toFixed(1)}"/>`;
          triHtml += `<circle cx="${p._tx.toFixed(1)}" cy="${p._ty.toFixed(1)}" r="2.2" fill="#2e5f85" opacity="0.8" pointer-events="none"/>`;
        }
        this.grpTrilat.innerHTML = triHtml;
      }
    }

    renderHouseholdsLayer() {
      if (this.displayMode !== 'household' || this.activeDaoId === 'siyi') {
        this.grpHouseholds.innerHTML = '';
        return;
      }
      let html = '';
      for (const p of this.data.prefectures) {
        if (this.activeDaoId !== 'ALL' && p.dao_id !== this.activeDaoId) continue;
        const total = p.song_total_households || p.tang_households || 0;
        if (!total) continue;
        const r = Math.max(3.5, Math.min(20, Math.sqrt(total / 1800)));
        const zhuRatio = p.song_total_households ? (p.song_zhu_households || 0) / p.song_total_households : 0.6;
        html += `<g class="hh-bubble" data-pref-id="${escHtml(p.id)}" style="cursor:pointer">
          <circle cx="${p._sx.toFixed(1)}" cy="${p._sy.toFixed(1)}" r="${r.toFixed(1)}" fill="rgba(217,138,60,0.55)" stroke="#b5452f" stroke-width="1" vector-effect="non-scaling-stroke"/>
          <circle cx="${p._sx.toFixed(1)}" cy="${p._sy.toFixed(1)}" r="${(r * Math.sqrt(zhuRatio)).toFixed(1)}" fill="rgba(181,69,47,0.72)" pointer-events="none"/>
        </g>`;
      }
      this.grpHouseholds.innerHTML = html;
    }

    renderSiyiLayer() {
      if (!this.chkSiyi.checked && this.activeDaoId !== 'siyi') {
        this.grpSiyi.innerHTML = '';
        return;
      }
      let html = '';
      const filterSub = this.activeSiyiSub || 'ALL';
      const isSiyiActive = this.activeDaoId === 'siyi';
      const rSize = isSiyiActive ? 3.4 : 2.5;
      const fSize = isSiyiActive ? 9.6 : 8.8;

      for (let i = 0; i < this.data.siyi.length; i++) {
        const s = this.data.siyi[i];
        if (s._sx == null) continue;
        if (filterSub !== 'ALL' && s.dao_id !== filterSub) continue;
        const conf = SIYI_DIR_CONF[s.dao_id] || { fill: '#6e655c', stroke: '#3a322b', label: '四夷' };
        html += `<g class="siyi-marker" data-siyi-idx="${i}" transform="translate(${s._sx.toFixed(1)},${s._sy.toFixed(1)})" style="cursor:pointer">
          <g class="inv-scale">
            <rect x="${(-rSize).toFixed(1)}" y="${(-rSize).toFixed(1)}" width="${(rSize * 2).toFixed(1)}" height="${(rSize * 2).toFixed(1)}" transform="rotate(45)" fill="${conf.fill}" stroke="#ffffff" stroke-width="0.8"/>
            <circle cx="0" cy="0" r="1.1" fill="#ffffff"/>
            <text x="0" y="${(-rSize - 3.2).toFixed(1)}" text-anchor="middle" font-family="var(--serif-stack)" font-size="${fSize}" font-weight="600" fill="${conf.stroke}">${escHtml(s.name)}</text>
          </g>
        </g>`;
      }
      this.grpSiyi.innerHTML = html;
    }

    renderSiyiRay(s) {
      if (s._sx == null) return;
      const [x1, y1] = this._changAnScreen;
      const x2 = s._sx;
      const y2 = s._sy;
      const mx = (x1 + x2) * 0.5;
      const my = (y1 + y2) * 0.5;
      let html = `<line class="net-edge-active" x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="#c04829" stroke-dasharray="4,3" stroke-width="1.3" marker-end="url(#arrow-vermilion)"/>`;
      html += `<g transform="translate(${mx.toFixed(1)},${my.toFixed(1)})" pointer-events="none"><g class="inv-scale"><text x="0" y="-3.5" text-anchor="middle" font-size="9.0" font-weight="600" fill="#c04829">長安より ${fmtNum(s.distance_chang_an_li)}里</text></g></g>`;
      this.grpActiveRays.innerHTML = html;
    }

    renderSettlementsLayer() {
      if (!this.chkSettlements.checked) {
        this.grpSettlements.innerHTML = '';
        return;
      }
      let html = '';
      const isSiyi = this.activeDaoId === 'siyi';
      for (const p of this.data.prefectures) {
        const isCap = p.name === '開封府' || p.name === '河南府' || p.name === '雍州';
        if (isSiyi) {
          if (!isCap) continue;
        } else if (this.activeDaoId !== 'ALL' && p.dao_id !== this.activeDaoId) {
          continue;
        }
        const isFu = p.name.endsWith('府');
        const r = isCap ? 4.0 : isFu ? 3.0 : 2.3;
        const fill = isCap ? '#b5452f' : isFu ? '#8f3524' : '#3a322b';
        const fSize = isCap ? 11.0 : isFu ? 9.6 : 8.5;
        const opacity = isSiyi ? '0.75' : '1.0';
        const capLabel = isSiyi && p.name === '雍州' ? '長安（雍州）' : p.name;
        html += `<g class="pref-node" data-pref-id="${escHtml(p.id)}" transform="translate(${p._sx.toFixed(3)},${p._sy.toFixed(3)})" style="cursor:pointer" opacity="${opacity}">
          <g class="inv-scale">
            <circle cx="0" cy="0" r="${r}" fill="${fill}" stroke="#fbf8f1" stroke-width="0.8"/>
            <text x="0" y="${(-r - 2.6).toFixed(1)}" text-anchor="middle" font-family="var(--serif-stack)" font-size="${fSize}" font-weight="${isCap || isFu ? '700' : '500'}" fill="${isCap ? '#9c2c18' : '#2b2622'}">${escHtml(capLabel)}</text>
          </g>
        </g>`;
      }
      this.grpSettlements.innerHTML = html;
    }

    _getViewportBox(marginPx = 50) {
      const k = this.camera.k;
      const m = marginPx / k;
      return {
        minX: -this.camera.x / k - m,
        maxX: (1000 - this.camera.x) / k + m,
        minY: -this.camera.y / k - m,
        maxY: (700 - this.camera.y) / k + m,
      };
    }

    renderDynamicDetailLayers() {
      if (this.activeDaoId === 'siyi') {
        this.grpCounties.innerHTML = '';
        this.grpLandmarks.innerHTML = '';
        return;
      }
      const k = this.camera.k;
      const showCounties = this.chkCounties.checked || k >= 2.3 || this.selectedPref != null;
      const showLandmarks =
        this.chkLandmarks.checked || this.displayMode === 'landmarks' || k >= 3.2 || this.selectedPref != null;

      if (!showCounties && !showLandmarks) {
        this.grpCounties.innerHTML = '';
        this.grpLandmarks.innerHTML = '';
        return;
      }

      const vp = this._getViewportBox(60);
      const selPrefName = this.selectedPref ? this.selectedPref.name : null;
      const visualBoost = (k > 1.0 ? Math.min(1.65, Math.pow(k, 0.24)) : 1.0) * (this.fontScale || 1.0);

      // Unified Screen-Space Label Bounding-Box Collision Detector
      // Prevents any County or Landmark label from overlapping Prefecture labels or each other
      const placedBoxes = [];
      const canPlaceBox = (cx, cy, halfW, halfH) => {
        const x1 = cx - halfW;
        const x2 = cx + halfW;
        const y1 = cy - halfH;
        const y2 = cy + halfH;
        for (let j = 0; j < placedBoxes.length; j++) {
          const b = placedBoxes[j];
          if (x1 < b.x2 && x2 > b.x1 && y1 < b.y2 && y2 > b.y1) return false;
        }
        placedBoxes.push({ x1, x2, y1, y2 });
        return true;
      };

      // Reserve bounding boxes for visible Prefecture labels first
      if (this.chkSettlements.checked) {
        for (let i = 0; i < this.data.prefectures.length; i++) {
          const p = this.data.prefectures[i];
          if (p._sx < vp.minX || p._sx > vp.maxX || p._sy < vp.minY || p._sy > vp.maxY) continue;
          if (this.activeDaoId !== 'ALL' && p.dao_id !== this.activeDaoId) continue;
          const scrX = p._sx * k + this.camera.x;
          const scrY = p._sy * k + this.camera.y;
          const halfW = (p.name.length * 5.2 + 4) * visualBoost;
          const halfH = 6.8 * visualBoost;
          placedBoxes.push({
            x1: scrX - halfW,
            x2: scrX + halfW,
            y1: scrY - halfH * 2.1,
            y2: scrY + halfH * 0.5,
          });
        }
      }

      // 1. Counties (1,150) with Viewport Culling + Exact Bounding-Box Label Decluttering
      if (!showCounties) {
        this.grpCounties.innerHTML = '';
      } else {
        let cHtml = '';
        const showCntyLabels = k >= 2.2 || selPrefName != null;

        for (let i = 0; i < this.data.counties.length; i++) {
          const c = this.data.counties[i];
          if (c._sx < vp.minX || c._sx > vp.maxX || c._sy < vp.minY || c._sy > vp.maxY) continue;
          const isSelPref = selPrefName && c.prefecture === selPrefName;
          if (selPrefName && !isSelPref && !this.chkCounties.checked && k < 2.8) {
            continue;
          }
          if (this.activeDaoId !== 'ALL' && c.dao_id !== this.activeDaoId) {
            continue;
          }
          const scrX = c._sx * k + this.camera.x;
          const scrY = c._sy * k + this.camera.y;

          let drawLabel = false;
          if (showCntyLabels && (isSelPref || k >= 2.2)) {
            const halfW = (c.name.length * 4.3 + 2.5) * visualBoost;
            const halfH = 5.4 * visualBoost;
            drawLabel = canPlaceBox(scrX, scrY - 5.5 * visualBoost, halfW, halfH);
          }
          cHtml += `<g class="cnty-node" data-cnty-idx="${i}" transform="translate(${c._sx.toFixed(3)},${c._sy.toFixed(3)})" style="cursor:pointer">
            <g class="inv-scale">
              <circle cx="0" cy="0" r="2.1" fill="#2e5f85" stroke="#fff" stroke-width="0.6"/>
              ${drawLabel ? `<text x="0" y="-3.8" text-anchor="middle" font-size="8.4" font-weight="600" fill="#1f496b">${escHtml(c.name)}</text>` : ''}
            </g>
          </g>`;
        }
        this.grpCounties.innerHTML = cHtml;
      }

      // 2. Landmarks (6,934) with Viewport Culling + Exact Bounding-Box Label Decluttering
      if (!showLandmarks) {
        this.grpLandmarks.innerHTML = '';
      } else {
        let lmHtml = '';
        const dotGrid = new Set();
        const useDotCulling = k < 6.0 && !selPrefName;
        const dotCellPx = k < 1.8 ? 11 : k < 2.8 ? 8 : 5;
        const showLmLabels = k >= 3.2 || selPrefName != null;

        for (let i = 0; i < this.data.landmarks.length; i++) {
          const lm = this.data.landmarks[i];
          if (lm._sx < vp.minX || lm._sx > vp.maxX || lm._sy < vp.minY || lm._sy > vp.maxY) continue;
          if (this.activeLmCat !== 'ALL' && lm.c !== this.activeLmCat) continue;
          const isSelPref = selPrefName && lm.p === selPrefName;
          if (selPrefName && !isSelPref && this.displayMode !== 'landmarks' && !this.chkLandmarks.checked && k < 3.5) {
            continue;
          }
          if (this.activeDaoId !== 'ALL') {
            const p = this.prefByName.get(lm.p);
            if (!p || p.dao_id !== this.activeDaoId) continue;
          }

          const scrX = lm._sx * k + this.camera.x;
          const scrY = lm._sy * k + this.camera.y;

          if (useDotCulling && !isSelPref) {
            const dKey = Math.floor(scrX / dotCellPx) * 10000 + Math.floor(scrY / dotCellPx);
            if (dotGrid.has(dKey)) continue;
            dotGrid.add(dKey);
          }

          let drawLabel = false;
          if (showLmLabels && (isSelPref || k >= 3.2)) {
            const halfW = (lm.n.length * 4.0 + 2.0) * visualBoost;
            const halfH = 5.0 * visualBoost;
            drawLabel = canPlaceBox(scrX, scrY - 5.0 * visualBoost, halfW, halfH);
          }

          const col = LM_CAT_COLORS[lm.c] || '#5d554c';
          lmHtml += `<g class="lm-node" data-lm-idx="${i}" transform="translate(${lm._sx.toFixed(3)},${lm._sy.toFixed(3)})" style="cursor:pointer">
            <g class="inv-scale">
              <circle cx="0" cy="0" r="1.8" fill="${col}" stroke="rgba(255,255,255,0.65)" stroke-width="0.4" opacity="0.9"/>
              ${drawLabel ? `<text x="0" y="-3.4" text-anchor="middle" font-size="8.0" fill="${col}">${escHtml(lm.n)}</text>` : ''}
            </g>
          </g>`;
        }
        this.grpLandmarks.innerHTML = lmHtml;
      }
    }

    renderActiveRays(pref) {
      if (!pref) {
        this.grpActiveRays.innerHTML = '';
        return;
      }
      const x1 = pref._sx;
      const y1 = pref._sy;
      const k = this.camera.k;
      let html = `<g transform="translate(${x1.toFixed(3)},${y1.toFixed(3)})" pointer-events="none"><g class="inv-scale"><circle cx="0" cy="0" r="6.5" fill="none" stroke="#b5452f" stroke-width="1.8"/></g></g>`;

      // When zoomed in very deeply (> 18x) to inspect individual counties/landmarks, hide the long-distance inter-prefecture ray labels so they don't clutter the local map
      const showRayText = k < 18.0;
      const rayOpacity = k >= 12.0 ? '0.35' : '0.88';

      const outgoing = this.edgesBySource.get(pref.name) || [];
      for (const e of outgoing) {
        const x2 = e._x2;
        const y2 = e._y2;
        // Place label at 62% along the ray so it stays outside the dense county/landmark cluster around the source prefecture
        const t = k >= 5.0 ? 0.68 : 0.52;
        const mx = x1 + (x2 - x1) * t;
        const my = y1 + (y2 - y1) * t;
        html += `<line class="net-edge-active" x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}" opacity="${rayOpacity}" marker-end="url(#arrow-vermilion)"/>`;
        if (showRayText) {
          html += `<g transform="translate(${mx.toFixed(2)},${my.toFixed(2)})" pointer-events="none"><g class="inv-scale"><text x="0" y="-2.5" text-anchor="middle" font-size="8.6" font-weight="600" fill="#b5452f">${escHtml(e.direction)}：${escHtml(e.target)}へ ${e.distance_li}里</text></g></g>`;
        }
      }
      this.grpActiveRays.innerHTML = html;
    }

    updateSidePane() {
      const titleEl = document.getElementById('dynasty-title');
      const spanEl = document.getElementById('dynasty-span');
      const seatEl = document.getElementById('dynasty-seat');
      const descEl = document.getElementById('dynasty-summary');
      const statsEl = document.getElementById('dao-stats-container');
      const listEl = document.getElementById('prefecture-list-container');

      const isAll = this.activeDaoId === 'ALL';
      const isSiyi = this.activeDaoId === 'siyi';
      const daoObj = isAll ? null : this.daoById.get(this.activeDaoId);

      if (isAll) {
        titleEl.textContent = '天下十三道・四夷総覧';
        spanEl.textContent = '全二百巻（北宋・太平興国年間）';
        seatEl.textContent = '東京開封府 · 西京河南府 · 十三道387州府軍監';
        descEl.textContent =
          '『太平寰宇記』は北宋太宗の太平興国年間（976〜983）に楽史が撰進した全200巻の全国地理総志。唐の十道志・元和郡県図志を継承しつつ、五代十国の分裂を経て再統一された北宋初期の州・府・軍・監、管轄県、四至八到（里程）、唐開元戸と宋皇朝戸（主戸・客戸）、風俗・姓氏・人物・土産・山川古跡を網羅する。';
      } else if (daoObj) {
        titleEl.textContent = daoObj.name;
        spanEl.textContent = daoObj.vols;
        seatEl.textContent = daoObj.capital;
        descEl.textContent = daoObj.desc;
      }

      if (isSiyi) {
        const subCounts = {
          ALL: this.data.siyi.length,
          siyi_dongyi: this.data.siyi.filter((s) => s.dao_id === 'siyi_dongyi').length,
          siyi_nanman: this.data.siyi.filter((s) => s.dao_id === 'siyi_nanman').length,
          siyi_xirong: this.data.siyi.filter((s) => s.dao_id === 'siyi_xirong').length,
          siyi_beidi: this.data.siyi.filter((s) => s.dao_id === 'siyi_beidi').length,
        };
        const currentSub = this.activeSiyiSub || 'ALL';
        statsEl.innerHTML = `<div class="stat-grid-box">
          <div class="stat-card"><div class="stat-lbl">収録諸国・部族</div><div class="stat-val">${this.data.siyi.length} 国</div><div class="stat-sub">東夷・南蠻・西戎・北狄</div></div>
          <div class="stat-card"><div class="stat-lbl">収録巻数</div><div class="stat-val">卷172上〜200</div><div class="stat-sub">計29巻</div></div>
        </div>
        <div class="siyi-filter-bar" style="display:flex;gap:4px;margin-top:10px;flex-wrap:wrap;">
          <button class="siyi-sub-btn ${currentSub === 'ALL' ? 'is-active' : ''}" data-siyi-sub="ALL">全四夷 (${subCounts.ALL})</button>
          <button class="siyi-sub-btn ${currentSub === 'siyi_dongyi' ? 'is-active' : ''}" data-siyi-sub="siyi_dongyi" style="--tint:#1b7a70">東夷 (${subCounts.siyi_dongyi})</button>
          <button class="siyi-sub-btn ${currentSub === 'siyi_nanman' ? 'is-active' : ''}" data-siyi-sub="siyi_nanman" style="--tint:#c04829">南蠻 (${subCounts.siyi_nanman})</button>
          <button class="siyi-sub-btn ${currentSub === 'siyi_xirong' ? 'is-active' : ''}" data-siyi-sub="siyi_xirong" style="--tint:#d97706">西戎 (${subCounts.siyi_xirong})</button>
          <button class="siyi-sub-btn ${currentSub === 'siyi_beidi' ? 'is-active' : ''}" data-siyi-sub="siyi_beidi" style="--tint:#4a5568">北狄 (${subCounts.siyi_beidi})</button>
        </div>`;

        statsEl.querySelectorAll('.siyi-filter-bar button').forEach((btn) => {
          btn.addEventListener('click', () => {
            this.activeSiyiSub = btn.dataset.siyiSub;
            this.renderSiyiLayer();
            this.updateSidePane();
          });
        });

        const filteredSiyi = this.data.siyi
          .map((s, idx) => ({ ...s, originalIdx: idx }))
          .filter((s) => currentSub === 'ALL' || s.dao_id === currentSub);

        let sHtml = '';
        filteredSiyi.forEach((s) => {
          const conf = SIYI_DIR_CONF[s.dao_id] || { fill: '#6e655c', stroke: '#3a322b', label: '四夷' };
          sHtml += `<div class="pref-list-item" data-siyi-idx="${s.originalIdx}">
            <div>
              <span style="display:inline-block;width:7px;height:7px;background:${conf.fill};transform:rotate(45deg);margin-right:5px;vertical-align:middle;"></span>
              <strong>${escHtml(s.name)}</strong>
              <span style="font-size:11px;color:var(--text-muted)">(${escHtml(s.dao)} · ${escHtml(s.vol)})</span>
            </div>
            <div style="font-size:11px;color:var(--vermilion)">${s.distance_chang_an_li ? `長安より${fmtNum(s.distance_chang_an_li)}里` : '詳伝'}</div>
          </div>`;
        });
        listEl.innerHTML = sHtml;
        listEl.onclick = (e) => {
          const item = e.target.closest('.pref-list-item[data-siyi-idx]');
          if (item) {
            const s = this.data.siyi[Number(item.dataset.siyiIdx)];
            if (s) this.openSiyiDetail(s, true);
          }
        };
        return;
      }

      const prefs = isAll
        ? this.data.prefectures
        : this.data.prefectures.filter((p) => p.dao_id === this.activeDaoId);
      const songHH = prefs.reduce((s, p) => s + (p.song_total_households || 0), 0);
      const songZhu = prefs.reduce((s, p) => s + (p.song_zhu_households || 0), 0);
      const songKe = prefs.reduce((s, p) => s + (p.song_ke_households || 0), 0);
      const cntyCount = prefs.reduce((s, p) => s + p.county_names.length, 0);
      const lmCount = prefs.reduce((s, p) => s + (this.landmarksByPref.get(p.name) || []).length, 0);

      statsEl.innerHTML = `<div class="stat-grid-box">
        <div class="stat-card">
          <div class="stat-lbl">管轄州府軍監 / 所属県</div>
          <div class="stat-val">${prefs.length} 州府 / ${cntyCount} 県</div>
          <div class="stat-sub">NER山川古跡: ${fmtNum(lmCount)} 箇所</div>
        </div>
        <div class="stat-card">
          <div class="stat-lbl">皇朝（北宋）総戸数</div>
          <div class="stat-val">${fmtNum(songHH)} 戸</div>
          <div class="stat-sub">主戸 ${fmtNum(songZhu)} / 客戸 ${fmtNum(songKe)}</div>
        </div>
      </div>`;

      let pHtml = '';
      for (const p of prefs) {
        const isSel = this.selectedPref && this.selectedPref.id === p.id;
        const distCount = p.distance_count != null ? p.distance_count : (p.distances ? p.distances.length : 0);
        pHtml += `<div class="pref-list-item${isSel ? ' is-selected' : ''}" data-pref-id="${escHtml(p.id)}">
          <div>
            <strong>${escHtml(p.name)}</strong>
            <span style="font-size:11px;color:var(--text-muted)">${p.jun_name ? `(${escHtml(p.jun_name)})` : ''} · ${escHtml(p.vol)}</span>
          </div>
          <div style="font-size:11px;color:var(--text-secondary)">
            ${p.county_names.length}県 · 四至${distCount}
          </div>
        </div>`;
      }
      listEl.innerHTML = pHtml;
      listEl.onclick = (e) => {
        const item = e.target.closest('.pref-list-item[data-pref-id]');
        if (item) {
          const p = this.prefById.get(item.dataset.prefId);
          if (p) this.openPrefectureDetail(p, true);
        }
      };
    }

    openPrefectureDetail(pref, fly = true) {
      this._loadTextsAsync();
      this.selectedPref = pref;
      this._openCardType = 'pref';
      this.genCard.classList.remove('is-hidden');
      this.genKicker.textContent = `${pref.dao} · ${pref.vol} · 州府軍監考証`;
      this.genHeading.textContent = `${pref.name}${pref.jun_name ? `（${pref.jun_name}）` : ''}`;
      this.genSub.textContent = `治所: ${pref.seat || '郭下'}県 ｜ 州境: 東西${pref.east_west_li || '—'}里・南北${pref.north_south_li || '—'}里 ｜ 基準座標: [${pref.coord[0]}, ${pref.coord[1]}] (${pref.coord_source})`;

      if (fly) {
        this.flyToGeo(pref.coord[0], pref.coord[1], Math.max(this.camera.k, 5.5));
      } else {
        this.renderDynamicDetailLayers();
      }
      this.renderPrefectures();
      this.renderActiveRays(pref);

      const counties = this.countiesByPref.get(pref.name) || [];
      const lms = this.landmarksByPref.get(pref.name) || [];

      const zhu = pref.song_zhu_households || 0;
      const ke = pref.song_ke_households || 0;
      const tot = pref.song_total_households || zhu + ke;
      const zhuPct = tot > 0 ? Math.round((zhu / tot) * 100) : 50;
      const kePct = 100 - zhuPct;

      let html = '';

      // 1. Households bar
      html += `<div class="hh-bar-wrap">
        <div style="display:flex;justify-content:space-between;font-size:11.5px;">
          <span><strong>唐・開元戸数:</strong> ${fmtNum(pref.tang_households)} 戸</span>
          <span><strong>北宋・皇朝戸数:</strong> ${fmtNum(tot)} 戸</span>
        </div>
        ${
          tot > 0
            ? `<div class="hh-bar-track">
                <div class="hh-bar-zhu" style="width:${zhuPct}%" title="主戸 ${fmtNum(zhu)}"></div>
                <div class="hh-bar-ke" style="width:${kePct}%" title="客戸 ${fmtNum(ke)}"></div>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:10.5px;color:var(--text-secondary);">
                <span style="color:#b5452f">■ 主戸: ${fmtNum(zhu)} (${zhuPct}%)</span>
                <span style="color:#b86b1e">■ 客戸: ${fmtNum(ke)} (${kePct}%)</span>
              </div>`
            : ''
        }
      </div>`;

      // 2. Trilateration verification
      html += `<div style="font-size:11.5px;background:rgba(46,95,133,0.08);border:1px solid rgba(46,95,133,0.22);border-radius:7px;padding:6px 9px;margin:6px 0;">
        <strong>NetworkX 四至八到・三辺測量検証:</strong>
        推計座標 [${pref.trilaterated_coord[0]}, ${pref.trilaterated_coord[1]}]
        （CHGIS基準点との偏差: <strong>${pref.trilateration_error_km} km</strong>）
      </div>`;

      // 3. History Japanese translation
      const histJa = pref.history_ja || pref.history || (this.textsLoaded ? '' : '解説データを読み込み中…');
      html += `<div class="section-subhead"><span>『太平寰宇記』建置沿革（現代語和訳）</span></div>
      <div style="font-size:12.5px;line-height:1.7;background:rgba(255,255,255,0.68);padding:9px 11px;border-radius:7px;border-left:3px solid var(--vermilion);">
        ${escHtml(histJa)}
        ${
          pref.history
            ? `<details style="margin-top:6px;font-size:11.5px;color:var(--text-muted);">
                <summary style="cursor:pointer;user-select:none;">漢文原文（四庫全書本）を表示</summary>
                <p style="font-family:var(--serif-stack);margin:5px 0 0;line-height:1.6;color:var(--text-secondary);">${escHtml(pref.history)}</p>
              </details>`
            : ''
        }
      </div>`;

      // 4. Counties
      html += `<div class="section-subhead"><span>管轄県（旧領 ${pref.orig_counties_count ?? '—'} → 現領 ${pref.county_names.length} 県）</span></div>`;
      html += `<div class="tag-cloud">`;
      for (const cname of pref.county_names) {
        html += `<span class="info-tag county-tag" data-cname="${escHtml(cname)}">${escHtml(cname)}</span>`;
      }
      html += `</div>`;

      // 5. 四至八到
      if (pref.distances && pref.distances.length) {
        html += `<div class="section-subhead"><span>四至八到（里程ネットワーク: ${pref.distances.length} 路線）</span></div>`;
        html += `<div style="max-height:130px;overflow-y:auto;border:1px solid rgba(43,38,34,0.1);border-radius:7px;padding:4px;background:rgba(255,255,255,0.5);">`;
        for (const d of pref.distances) {
          const geoKm = d.geodesic_km ? `（直線 ${d.geodesic_km} km）` : '';
          html += `<div class="sizhi-row" data-target="${escHtml(d.target)}">
            <span><strong>${escHtml(d.direction)}</strong>：<strong>${escHtml(d.target_detail)}</strong>に至る</span>
            <span style="color:var(--vermilion);font-weight:600;">${fmtNum(d.distance_li)} 里 <span style="font-size:10.5px;color:var(--text-muted);font-weight:400;">${geoKm}</span></span>
          </div>`;
        }
        html += `</div>`;
      }

      // 6. Products (土産) & Customs (風俗) & Surnames (姓氏) & Figures (人物)
      if (pref.products && pref.products.length) {
        html += `<div class="section-subhead"><span>土産（特産品・貢物）</span></div><div class="tag-cloud">`;
        for (const prod of pref.products) {
          html += `<span class="info-tag prod-tag" data-query="${escHtml(prod)}">${escHtml(prod)}</span>`;
        }
        html += `</div>`;
      }
      const custJa = pref.customs_ja || pref.customs || '';
      const surnJa = pref.surnames_ja || pref.surnames || '';
      if (custJa || surnJa) {
        html += `<div class="section-subhead"><span>風俗・姓氏（和訳）</span></div>
        <p style="font-size:12px;line-height:1.65;margin:4px 0;background:rgba(255,255,255,0.5);padding:6px 8px;border-radius:6px;">
          ${escHtml(custJa)}${surnJa ? `<br/><strong>【著姓】</strong>${escHtml(surnJa)}` : ''}
        </p>`;
      }
      const figsList = pref.figures_ja && pref.figures_ja.length ? pref.figures_ja : pref.figures || [];
      if (figsList.length) {
        html += `<div class="section-subhead"><span>人物（${figsList.length} 名）</span></div>
        <div style="font-size:11.5px;line-height:1.6;max-height:95px;overflow-y:auto;background:rgba(255,255,255,0.45);padding:5px 8px;border-radius:6px;">${figsList.map(escHtml).join(' ／ ')}</div>`;
      }

      // 7. Landmarks in this Prefecture
      if (lms.length) {
        html += `<div class="section-subhead"><span>山川・古跡・故城・陵墓（和訳解説: ${lms.length} 箇所）</span></div>`;
        html += `<div style="max-height:175px;overflow-y:auto;border:1px solid rgba(43,38,34,0.1);border-radius:7px;padding:5px;background:rgba(255,255,255,0.55);">`;
        for (const lm of lms.slice(0, 60)) {
          const citBadges = (lm.cit || []).map((c) => `<span class="info-tag cit-tag">『${escHtml(c)}』</span>`).join('');
          const lmDescJa = lm.desc_ja || lm.desc || '';
          html += `<div style="font-size:11.5px;padding:4px 3px;border-bottom:1px dashed rgba(43,38,34,0.1);">
            <div><strong>【${escHtml(lm.c)}】${escHtml(lm.n)}</strong> <span style="color:var(--text-muted)">(${escHtml(lm.cnty)}${lm.dir ? ` · ${escHtml(lm.dir)}${lm.li}里` : ''})</span> ${citBadges}</div>
            ${lmDescJa ? `<div style="color:var(--text-secondary);font-size:11.5px;margin-top:2px;line-height:1.55;">${escHtml(lmDescJa)}</div>` : ''}
          </div>`;
        }
        html += `</div>`;
      }

      this.genBody.innerHTML = html;

      // Bind interactive jumps inside card
      this.genBody.querySelectorAll('.sizhi-row').forEach((row) => {
        row.addEventListener('click', () => {
          const t = this.prefByName.get(row.dataset.target);
          if (t) this.openPrefectureDetail(t, true);
        });
      });
      this.genBody.querySelectorAll('.county-tag').forEach((tag) => {
        tag.addEventListener('click', () => {
          const cname = tag.dataset.cname;
          const cObj = counties.find(
            (c) => c.name === cname || c.name === cname + '縣' || c.name.replace('縣', '') === cname
          );
          if (cObj) this.openCountyDetail(cObj, true);
        });
      });
      this.genBody.querySelectorAll('.prod-tag').forEach((tag) => {
        tag.addEventListener('click', () => {
          const inp = document.getElementById('inp-map-search');
          inp.value = tag.dataset.query;
          inp.dispatchEvent(new Event('input'));
          inp.focus();
        });
      });
    }

    openCountyDetail(county, fly = true) {
      this._loadTextsAsync();
      this.selectedCounty = county;
      this._openCardType = 'county';
      this.genCard.classList.remove('is-hidden');
      this.genKicker.textContent = `${county.dao} · ${county.prefecture} · 所属県考証`;
      this.genHeading.textContent = `${county.name}（${county.prefecture}管轄）`;
      this.genSub.textContent = `方位里程: ${county.direction ? `州の${county.direction}${county.distance_li}里` : '州郭下/域内'} ｜ 郷数: 旧${county.old_xiang ?? '—'}郷 → 現${county.curr_xiang ?? '—'}郷 ｜ 座標: [${county.coord[0]}, ${county.coord[1]}]`;
      if (fly) {
        this.flyToGeo(county.coord[0], county.coord[1], Math.max(this.camera.k, 14.0));
      }

      const lms = (this.landmarksByPref.get(county.prefecture) || []).filter((l) => l.cnty === county.name);
      const introJa = county.intro_ja || county.intro || (this.textsLoaded ? '' : '解説データを読み込み中…');
      let html = `<div class="section-subhead"><span>県建置沿革（現代語和訳）</span></div>`;
      html += `<div style="font-size:12.5px;line-height:1.7;background:rgba(255,255,255,0.68);padding:9px 11px;border-radius:7px;border-left:3px solid var(--cobalt);">
        ${escHtml(introJa)}
        ${
          county.intro
            ? `<details style="margin-top:6px;font-size:11.5px;color:var(--text-muted);">
                <summary style="cursor:pointer;user-select:none;">漢文原文を表示</summary>
                <p style="font-family:var(--serif-stack);margin:5px 0 0;line-height:1.6;color:var(--text-secondary);">${escHtml(county.intro)}</p>
              </details>`
            : ''
        }
      </div>`;
      html += `<div class="section-subhead"><span>${escHtml(county.name)}内の山川・古跡・陵墓（${lms.length} 箇所）</span></div>`;
      for (const lm of lms) {
        const citBadges = (lm.cit || []).map((c) => `<span class="info-tag cit-tag">『${escHtml(c)}』</span>`).join('');
        const lmDescJa = lm.desc_ja || lm.desc || '';
        html += `<div style="font-size:11.5px;padding:5px 3px;border-bottom:1px dashed rgba(43,38,34,0.12);">
          <div><strong>【${escHtml(lm.c)}】${escHtml(lm.n)}</strong> <span style="color:var(--vermilion)">${lm.dir ? `県の${escHtml(lm.dir)}${lm.li}里` : ''}</span> ${citBadges}</div>
          ${lmDescJa ? `<div style="color:var(--text-secondary);margin-top:2px;line-height:1.55;">${escHtml(lmDescJa)}</div>` : ''}
        </div>`;
      }
      const parentPref = this.prefByName.get(county.prefecture);
      if (parentPref) {
        html += `<button type="button" class="action-btn subtle" id="btn-back-pref" style="margin-top:10px;width:100%;">← ${escHtml(parentPref.name)}の州府詳細へ戻る</button>`;
      }
      this.genBody.innerHTML = html;
      const btnBack = document.getElementById('btn-back-pref');
      if (btnBack && parentPref) {
        btnBack.addEventListener('click', () => this.openPrefectureDetail(parentPref, false));
      }
    }

    openLandmarkDetail(lm, fly = true) {
      this._loadTextsAsync();
      this.selectedLandmark = lm;
      this._openCardType = 'lm';
      this.genCard.classList.remove('is-hidden');
      this.genKicker.textContent = `${lm.d} · ${lm.p}${lm.cnty} · 【${lm.c}】考証`;
      this.genHeading.textContent = lm.n;
      this.genSub.textContent = `所属: ${lm.p} ${lm.cnty}（${lm.v}） ｜ 位置: ${lm.dir ? `県の${lm.dir}${lm.li}里` : '県域内'} ｜ 推計座標: [${lm.xy[0]}, ${lm.xy[1]}]`;
      if (fly) {
        this.flyToGeo(lm.xy[0], lm.xy[1], Math.max(this.camera.k, 24.0));
      }

      const citBadges = (lm.cit || []).map((c) => `<span class="info-tag cit-tag">『${escHtml(c)}』引用</span>`).join(' ');
      const descJa = lm.desc_ja || lm.desc || (this.textsLoaded ? '' : '解説データを読み込み中…');
      let html = `<div style="margin:6px 0;">${citBadges || '<span class="info-tag cit-tag">『太平寰宇記』本文</span>'}</div>`;
      html += `<div style="font-size:13px;line-height:1.72;background:rgba(255,255,255,0.68);padding:10px 12px;border-radius:8px;border-left:3px solid var(--vermilion);">
        ${escHtml(descJa)}
        ${
          lm.desc
            ? `<details style="margin-top:6px;font-size:11.5px;color:var(--text-muted);">
                <summary style="cursor:pointer;user-select:none;">漢文原文を表示</summary>
                <p style="font-family:var(--serif-stack);margin:5px 0 0;line-height:1.6;color:var(--text-secondary);">${escHtml(lm.desc)}</p>
              </details>`
            : ''
        }
      </div>`;
      const parentPref = this.prefByName.get(lm.p);
      if (parentPref) {
        html += `<button type="button" class="action-btn subtle" id="btn-lm-to-pref" style="margin-top:8px;width:100%;">← ${escHtml(parentPref.name)}（${escHtml(lm.cnty)}）の詳細を開く</button>`;
      }
      this.genBody.innerHTML = html;
      const btn = document.getElementById('btn-lm-to-pref');
      if (btn && parentPref) {
        btn.addEventListener('click', () => this.openPrefectureDetail(parentPref, false));
      }
    }

    openSiyiDetail(s, fly = true) {
      this._loadTextsAsync();
      this.selectedSiyi = s;
      this._openCardType = 'siyi';
      this.genCard.classList.remove('is-hidden');
      this.genKicker.textContent = `${s.dao} · ${s.vol} · 四夷諸国伝`;
      this.genHeading.textContent = s.name;
      this.genSub.textContent = `${s.distance_chang_an_li ? `長安より: ${fmtNum(s.distance_chang_an_li)} 里 ｜ ` : ''}基準座標: [${s.coord[0]}, ${s.coord[1]}]`;
      if (fly) {
        this.flyToGeo(s.coord[0], s.coord[1], 2.8);
      }

      let html = '';
      const sizhiJa = s.sizhi_ja || s.sizhi;
      const custJa = s.customs_ja || s.customs;
      const histJa = s.history_ja || s.history || (this.textsLoaded ? '' : '解説データを読み込み中…');

      if (sizhiJa) {
        html += `<div class="section-subhead"><span>四至・道里（和訳）</span></div><p style="font-size:12px;line-height:1.65;background:rgba(255,255,255,0.55);padding:7px 9px;border-radius:6px;">${escHtml(sizhiJa)}</p>`;
      }
      if (custJa) {
        html += `<div class="section-subhead"><span>土俗・物産（和訳）</span></div><p style="font-size:12px;line-height:1.65;background:rgba(255,255,255,0.55);padding:7px 9px;border-radius:6px;">${escHtml(custJa)}</p>`;
      }
      if (histJa) {
        html += `<div class="section-subhead"><span>『太平寰宇記』沿革・本伝（和訳）</span></div>
        <div style="font-size:12.5px;line-height:1.7;background:rgba(255,255,255,0.65);padding:9px 11px;border-radius:7px;border-left:3px solid var(--vermilion);">
          ${escHtml(histJa)}
          ${
            s.history
              ? `<details style="margin-top:6px;font-size:11.5px;color:var(--text-muted);">
                  <summary style="cursor:pointer;user-select:none;">漢文原文を表示</summary>
                  <p style="font-family:var(--serif-stack);margin:5px 0 0;line-height:1.6;color:var(--text-secondary);">${escHtml(s.history.slice(0, 800))}</p>
                </details>`
              : ''
          }
        </div>`;
      }
      this.genBody.innerHTML = html;
    }

    _runSearch(q, resList) {
      const hits = [];
      // 1. Prefectures & Products & Figures
      for (const p of this.data.prefectures) {
        if (p.name.includes(q) || (p.jun_name && p.jun_name.includes(q)) || (p.seat && p.seat.includes(q))) {
          hits.push({
            label: `【州府】${p.name}（${p.dao} · ${p.vol}）`,
            sub: `治所: ${p.seat} · 皇朝戸: ${fmtNum(p.song_total_households)}`,
            act: () => this.openPrefectureDetail(p, true),
          });
        } else if (p.products && p.products.some((pr) => pr.includes(q))) {
          hits.push({
            label: `【土産: ${q}】${p.name}（${p.dao}）`,
            sub: `土産: ${p.products.join('・')}`,
            act: () => this.openPrefectureDetail(p, true),
          });
        } else if (p.figures && p.figures.some((fg) => fg.includes(q))) {
          const figsJa = p.figures_ja && p.figures_ja.length ? p.figures_ja : p.figures;
          const mFig = figsJa.find((fg) => fg.includes(q)) || p.figures.find((fg) => fg.includes(q));
          hits.push({
            label: `【人物】${p.name}（${p.dao}）`,
            sub: mFig,
            act: () => this.openPrefectureDetail(p, true),
          });
        }
        if (hits.length >= 25) break;
      }

      // 2. Counties
      if (hits.length < 25) {
        for (const c of this.data.counties) {
          if (c.name.includes(q)) {
            hits.push({
              label: `【県】${c.name}（${c.prefecture} · ${c.dao}）`,
              sub: (c.intro_ja || c.intro || '').slice(0, 50),
              act: () => this.openCountyDetail(c, true),
            });
            if (hits.length >= 25) break;
          }
        }
      }

      // 3. Landmarks
      if (hits.length < 25) {
        for (const lm of this.data.landmarks) {
          if (lm.n.includes(q)) {
            hits.push({
              label: `【${lm.c}】${lm.n}（${lm.p}${lm.cnty}）`,
              sub: (lm.desc_ja || lm.desc || '').slice(0, 55),
              act: () => this.openLandmarkDetail(lm, true),
            });
            if (hits.length >= 25) break;
          }
        }
      }

      // 4. Si-Yi
      if (hits.length < 25) {
        for (const s of this.data.siyi) {
          if (s.name.includes(q)) {
            hits.push({
              label: `【四夷】${s.name}（${s.dao} · ${s.vol}）`,
              sub: (s.history_ja || s.history || s.short_preview || '').slice(0, 50),
              act: () => this.openSiyiDetail(s, true),
            });
            if (hits.length >= 25) break;
          }
        }
      }

      if (!hits.length) {
        resList.innerHTML = `<li style="padding:8px 12px;font-size:12px;color:var(--text-muted);">「${escHtml(q)}」に一致する項目はありません</li>`;
      } else {
        resList.innerHTML = hits
          .map(
            (h, i) => `<li class="search-res-item" data-idx="${i}" style="padding:7px 12px;cursor:pointer;border-bottom:1px solid rgba(43,38,34,0.07);">
            <div style="font-size:12.5px;font-weight:600;color:var(--text-main);">${escHtml(h.label)}</div>
            <div style="font-size:11px;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(h.sub)}</div>
          </li>`
          )
          .join('');
        resList.querySelectorAll('.search-res-item').forEach((li) => {
          li.addEventListener('click', () => {
            const h = hits[Number(li.dataset.idx)];
            resList.classList.add('is-hidden');
            if (h) h.act();
          });
        });
      }
      resList.classList.remove('is-hidden');
    }

    updateLegend() {
      const box = document.getElementById('map-key');
      if (this.displayMode === 'network') {
        box.innerHTML = `<div style="font-size:11.5px;padding:6px 10px;background:rgba(251,248,241,0.92);border-radius:8px;border:1px solid rgba(43,38,34,0.15);">
          <strong>四至八到・里程ネットワーク凡例 (1宋里≈0.372km)</strong><br/>
          <span style="color:#2e7357">━</span> 記載里数と実測距離が一致 (迂回比 0.7〜1.35)<br/>
          <span style="color:#2e5f85">━</span> 山岳・河川による長距離迂回路 (迂回比 &lt; 0.7)<br/>
          <span style="color:#b5452f">━</span> 伝写異同または直線短縮 (迂回比 &gt; 1.35)
        </div>`;
      } else if (this.displayMode === 'household') {
        box.innerHTML = `<div style="font-size:11.5px;padding:6px 10px;background:rgba(251,248,241,0.92);border-radius:8px;border:1px solid rgba(43,38,34,0.15);">
          <strong>北宋太宗朝・皇朝戸口バブル凡例</strong><br/>
          <span style="color:#b5452f">●</span> 内円: 主戸（土着課税戸） ／ <span style="color:#d98a3c">●</span> 外円: 客戸（移住・小作戸）
        </div>`;
      } else if (this.displayMode === 'landmarks') {
        box.innerHTML = `<div style="font-size:11.5px;padding:6px 10px;background:rgba(251,248,241,0.92);border-radius:8px;border:1px solid rgba(43,38,34,0.15);">
          <strong>山川・古跡NER分布 (6,934箇所)</strong>:
          <span style="color:#6e5034">●山岳</span>
          <span style="color:#2b6a8c">●水系</span>
          <span style="color:#9e3d2b">●故城</span>
          <span style="color:#6c4b7d">●陵墓</span>
          <span style="color:#b87d1e">●祠廟</span>
        </div>`;
      } else {
        box.innerHTML = `<div style="font-size:11.5px;padding:6px 10px;background:rgba(251,248,241,0.92);border-radius:8px;border:1px solid rgba(43,38,34,0.15);">
          <span style="color:#b5452f">●</span> 三京（東京・西京・長安）
          <span style="color:#3a322b;margin-left:6px;">●</span> 州府軍監 (387)
          <span style="color:#2e5f85;margin-left:6px;">●</span> 所属県 (1,150)
          <span style="color:#6e655c;margin-left:6px;">◆</span> 四夷 (${this.data.siyi.length})
        </div>`;
      }
    }

    _showHoverTip(e, html) {
      this.hoverTip.innerHTML = html;
      this.hoverTip.classList.remove('is-hidden');
      this._moveHoverTip(e);
    }

    _moveHoverTip(e) {
      const rect = this._viewportRect || (this._viewportRect = this.viewportFrame.getBoundingClientRect());
      const x = Math.min(rect.width - 240, e.clientX - rect.left + 14);
      const y = Math.max(10, e.clientY - rect.top - 28);
      this.hoverTip.style.left = `${x}px`;
      this.hoverTip.style.top = `${y}px`;
    }
  }

  window.addEventListener('DOMContentLoaded', () => {
    window.taipingApp = new TaipingAtlasApp();
  });
})();
