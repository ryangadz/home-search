/* Big garages, walkable streets — map + filters.
   Data comes from data/*.js (built by scripts/03_build.py) as window.HS_* globals. */
(function () {
  'use strict';

  var H = window.HS_HOMES, META = window.HS_META, GRID = window.HS_GRID, PLACES = window.HS_PLACES || [];
  if (!H || !META || !GRID) {
    document.getElementById('count-t').textContent =
      'Data files are missing. Run scripts/03_build.py, then reload this page.';
    return;
  }
  var N = H.lat.length;
  var LIST_MAX = 250;
  var HOUSE = '#eb6834', INK = '#1b2430';
  var WALK_COLORS = [[205, 226, 251], [134, 182, 239], [57, 135, 229], [24, 79, 149]]; // 30, 50, 70, 90+
  var DEFAULTS = { space: 900, walk: 70, liv: 0, val: 5050, lot: 0, shop: false, sort: 'walk' };

  // ---------------------------------------------------------------- helpers
  var $ = function (id) { return document.getElementById(id); };
  var fmt = function (n) { return Math.round(n).toLocaleString('en-US'); };
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  var KEEP_UPPER = { N: 1, S: 1, E: 1, W: 1, NE: 1, NW: 1, SE: 1, SW: 1 };
  function titleCase(s) {
    return String(s || '').toLowerCase().split(' ').map(function (w) {
      var up = w.toUpperCase();
      if (KEEP_UPPER[up]) return up;
      if (/^\d/.test(w)) return w;                      // 70th, 12311
      return w.charAt(0).toUpperCase() + w.slice(1);
    }).join(' ');
  }
  function walkWords(w) {
    if (w >= 90) return 'everything on foot';
    if (w >= 70) return 'most errands on foot';
    if (w >= 50) return 'some errands on foot';
    if (w >= 30) return 'mostly by car';
    return 'car needed';
  }
  function carsWords(sqft) {
    return sqft > 1600 ? 'workshop scale' : 'about ' + Math.max(2, Math.round(sqft / 230)) + ' cars';
  }
  function money(k) {
    if (!k) return 'not listed';
    return k >= 1000 ? '$' + (k / 1000).toFixed(2).replace(/0$/, '') + 'M' : '$' + fmt(k) + 'k';
  }
  function cityOf(i) { return META.cities[H.city[i]] || ''; }
  function spaceOf(i) { return H.g[i] + (state.shop ? H.sh[i] : 0); }

  // Web-Mercator position of every house, 0..1
  var MX = new Float64Array(N), MY = new Float64Array(N);
  function mercX(lon) { return (lon + 180) / 360; }
  function mercY(lat) { var s = Math.sin(lat * Math.PI / 180); return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI); }
  for (var i = 0; i < N; i++) { MX[i] = mercX(H.lon[i]); MY[i] = mercY(H.lat[i]); }

  // ---------------------------------------------------------------- state
  var state = Object.assign({}, DEFAULTS);
  try {
    var saved = JSON.parse(localStorage.getItem('hs-filters') || 'null');
    if (saved) Object.keys(DEFAULTS).forEach(function (k) { if (typeof saved[k] === typeof DEFAULTS[k]) state[k] = saved[k]; });
  } catch (e) { /* storage unavailable: start from defaults */ }
  function persist() { try { localStorage.setItem('hs-filters', JSON.stringify(state)); } catch (e) { /* ignore */ } }

  var match = new Int32Array(0);     // indices of houses passing the filters, in list order
  var selected = -1, hovered = -1;

  // ---------------------------------------------------------------- map
  var map = L.map('map', { zoomControl: false, preferCanvas: true, minZoom: 9, maxZoom: 19 })
    .setView([47.62, -122.22], 11);
  L.control.zoom({ position: 'bottomleft' }).addTo(map);
  // Street maps: Esri's public tile services (no key needed, and they load from a local file)
  var ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/';
  var ATTR = 'Street map &copy; Esri and its data providers · Places &copy; OpenStreetMap contributors · Houses: King County Assessor';
  map.createPane('labels').style.zIndex = 420;
  map.getPane('labels').style.pointerEvents = 'none';
  function esri(service, maxNative, pane) {
    return L.tileLayer(ESRI + service + '/MapServer/tile/{z}/{y}/{x}',
      { maxNativeZoom: maxNative, maxZoom: 20, attribution: ATTR, pane: pane || 'tilePane' });
  }
  var BASES = {
    light: L.layerGroup([esri('Canvas/World_Light_Gray_Base', 16), esri('Canvas/World_Light_Gray_Reference', 16, 'labels')]),
    streets: esri('World_Street_Map', 19),
    aerial: esri('World_Imagery', 19)
  };
  var baseName = 'light';
  try { var b = localStorage.getItem('hs-base'); if (b && BASES[b]) baseName = b; } catch (e) { /* ignore */ }
  function setBase(name) {
    map.removeLayer(BASES[baseName]);
    baseName = name; BASES[name].addTo(map);
    try { localStorage.setItem('hs-base', name); } catch (e) { /* ignore */ }
  }
  BASES[baseName].addTo(map);

  // Walkability shading, painted from the score grid
  var gridBytes = (function () {
    var bin = atob(GRID.data), out = new Uint8Array(bin.length);
    for (var k = 0; k < bin.length; k++) out[k] = bin.charCodeAt(k);
    return out;
  })();
  var walkLayer = (function () {
    var c = document.createElement('canvas'); c.width = GRID.w; c.height = GRID.h;
    var ctx = c.getContext('2d'), img = ctx.createImageData(GRID.w, GRID.h), d = img.data;
    for (var k = 0; k < gridBytes.length; k++) {
      var v = gridBytes[k];
      if (v === 255 || v < 30) continue;
      var col = WALK_COLORS[v >= 90 ? 3 : v >= 70 ? 2 : v >= 50 ? 1 : 0];
      d[k * 4] = col[0]; d[k * 4 + 1] = col[1]; d[k * 4 + 2] = col[2]; d[k * 4 + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    return L.imageOverlay(c.toDataURL('image/png'), [[GRID.south, GRID.west], [GRID.north, GRID.east]],
      { opacity: 0.62, interactive: false });
  })();
  var gx0 = mercX(GRID.west), gx1 = mercX(GRID.east), gy0 = mercY(GRID.north), gy1 = mercY(GRID.south);
  function walkAt(latlng) {
    var cx = Math.floor((mercX(latlng.lng) - gx0) / (gx1 - gx0) * GRID.w);
    var cy = Math.floor((mercY(latlng.lat) - gy0) / (gy1 - gy0) * GRID.h);
    if (cx < 0 || cy < 0 || cx >= GRID.w || cy >= GRID.h) return -1;
    var v = gridBytes[cy * GRID.w + cx];
    return v === 255 ? -1 : v;
  }

  // Light rail stations (off until asked for)
  var railLayer = L.layerGroup(META.stations.map(function (s) {
    return L.circleMarker([s[0], s[1]], { radius: 5, color: INK, weight: 2, fillColor: '#fff', fillOpacity: 1 })
      .bindTooltip(s[2], { direction: 'top', className: 'rail-label', offset: [0, -4] });
  }));

  // One canvas for houses and places, redrawn after every move
  var canvas = L.DomUtil.create('canvas', 'hs-canvas leaflet-zoom-hide');
  map.createPane('hs').style.zIndex = 450;
  map.getPane('hs').style.pointerEvents = 'none';
  map.getPane('hs').appendChild(canvas);
  var ctx2 = canvas.getContext('2d');
  var vis = { n: 0, x: new Float32Array(0), y: new Float32Array(0), i: new Int32Array(0), r: 4 };
  var visPlaces = [];
  var showPlaces = true;

  function project(mx, my, scale, ox, oy) { return [mx * scale - ox, my * scale - oy]; }

  function draw() {
    var size = map.getSize(), dpr = window.devicePixelRatio || 1;
    L.DomUtil.setPosition(canvas, map.containerPointToLayerPoint([0, 0]));
    if (canvas.width !== size.x * dpr || canvas.height !== size.y * dpr) {
      canvas.width = size.x * dpr; canvas.height = size.y * dpr;
      canvas.style.width = size.x + 'px'; canvas.style.height = size.y + 'px';
    }
    var c = ctx2;
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, size.x, size.y);
    var z = map.getZoom(), scale = 256 * Math.pow(2, z), pb = map.getPixelBounds();
    var ox = pb.min.x, oy = pb.min.y, W = size.x, Hh = size.y;

    // places first, so houses sit on top
    visPlaces = [];
    var placesOn = showPlaces && z >= 15;
    $('places-hint').hidden = !showPlaces || z >= 15;
    if (placesOn) {
      c.fillStyle = 'rgba(27,36,48,0.78)'; c.strokeStyle = '#fff'; c.lineWidth = 1.2;
      for (var p = 0; p < PLACES.length; p++) {
        var pl = PLACES[p], px = mercX(pl[1]) * scale - ox, py = mercY(pl[0]) * scale - oy;
        if (px < -8 || py < -8 || px > W + 8 || py > Hh + 8) continue;
        c.beginPath();
        if (pl[2] === 0) c.rect(px - 3.5, py - 3.5, 7, 7); else c.arc(px, py, 2.6, 0, 6.2832);
        c.fill(); c.stroke();
        visPlaces.push([px, py, p]);
      }
      if (z >= 17 && visPlaces.length <= 220) {
        c.font = '500 11.5px Archivo, system-ui, sans-serif'; c.textBaseline = 'middle';
        c.lineWidth = 3; c.strokeStyle = 'rgba(255,255,255,0.92)'; c.fillStyle = INK;
        visPlaces.forEach(function (v) {
          var name = PLACES[v[2]][3]; if (!name) return;
          c.strokeText(name, v[0] + 7, v[1]); c.fillText(name, v[0] + 7, v[1]);
        });
      }
    }

    // houses, smallest garages first
    var base = z < 11 ? 1.5 : z < 13 ? 2.3 : z < 15 ? 3.4 : 4.6;
    var radii = [base, base * 1.45, base * 1.95];
    if (vis.x.length < match.length) {
      vis.x = new Float32Array(match.length); vis.y = new Float32Array(match.length); vis.i = new Int32Array(match.length);
    }
    var n = 0, cls = new Uint8Array(match.length);
    for (var m = 0; m < match.length; m++) {
      var h = match[m], x = MX[h] * scale - ox, y = MY[h] * scale - oy;
      if (x < -10 || y < -10 || x > W + 10 || y > Hh + 10) continue;
      var s = spaceOf(h);
      vis.x[n] = x; vis.y[n] = y; vis.i[n] = h; cls[n] = s >= 1200 ? 2 : s >= 900 ? 1 : 0; n++;
    }
    vis.n = n; vis.r = radii[2];
    c.fillStyle = HOUSE; c.strokeStyle = '#fff'; c.lineWidth = z < 12 ? 0.6 : 1.2;
    c.globalAlpha = n > 6000 ? 0.75 : 0.95;
    for (var k = 0; k < 3; k++) {
      var r = radii[k];
      c.beginPath();
      for (var q = 0; q < n; q++) {
        if (cls[q] !== k) continue;
        c.moveTo(vis.x[q] + r, vis.y[q]); c.arc(vis.x[q], vis.y[q], r, 0, 6.2832);
      }
      c.fill(); c.stroke();
    }
    c.globalAlpha = 1;
    ring(hovered, 2, 3.5);
    ring(selected, 3, 5);

    function ring(h, w, grow) {
      if (h < 0) return;
      var x = MX[h] * scale - ox, y = MY[h] * scale - oy, s = spaceOf(h);
      var r = radii[s >= 1200 ? 2 : s >= 900 ? 1 : 0] + grow;
      c.beginPath(); c.arc(x, y, r, 0, 6.2832);
      c.lineWidth = w + 2.5; c.strokeStyle = '#fff'; c.stroke();
      c.lineWidth = w; c.strokeStyle = INK; c.stroke();
      c.beginPath(); c.arc(x, y, r - grow, 0, 6.2832); c.fillStyle = HOUSE; c.fill();
    }
  }
  map.on('moveend zoomend resize', draw);
  // let the street map show through as you zoom in
  function fadeWalk() { var z = map.getZoom(); walkLayer.setOpacity(z >= 15 ? 0.3 : z >= 13 ? 0.46 : 0.62); }
  map.on('zoomend', fadeWalk);

  // pointer: nearest house wins, then nearest place, then the walkability under the pointer
  var tip = $('tip');
  function nearestHouse(pt) {
    var best = -1, bd = Math.pow(Math.max(9, vis.r + 5), 2);
    for (var q = 0; q < vis.n; q++) {
      var dx = vis.x[q] - pt.x, dy = vis.y[q] - pt.y, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = vis.i[q]; }
    }
    return best;
  }
  function nearestPlace(pt) {
    var best = -1, bd = 81;
    for (var q = 0; q < visPlaces.length; q++) {
      var dx = visPlaces[q][0] - pt.x, dy = visPlaces[q][1] - pt.y, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = visPlaces[q][2]; }
    }
    return best;
  }
  function showTip(pt, title, sub) {
    tip.textContent = '';
    tip.appendChild(el('b', null, title));
    if (sub) tip.appendChild(el('span', null, sub));
    tip.style.left = pt.x + 'px'; tip.style.top = pt.y + 'px';
    tip.hidden = false;
  }
  var pending = null;
  map.on('mousemove', function (e) {
    pending = e;
    if (pending.__q) return;
    pending.__q = true;
    requestAnimationFrame(function () {
      var ev = pending, pt = ev.containerPoint;
      var h = nearestHouse(pt);
      if (h !== hovered) { hovered = h; draw(); markRow(); }
      if (h >= 0) {
        showTip(pt, titleCase(H.addr[h]) || 'No street address',
          fmt(spaceOf(h)) + ' sq ft garage · walkability ' + H.walk[h]);
      } else {
        var p = nearestPlace(pt);
        if (p >= 0) showTip(pt, PLACES[p][3] || META.place_cats[PLACES[p][2]], PLACES[p][3] ? META.place_cats[PLACES[p][2]] : '');
        else tip.hidden = true;
      }
      map.getContainer().style.cursor = h >= 0 ? 'pointer' : '';
      var w = walkAt(ev.latlng);
      $('read').textContent = w < 0 ? '' : w + ' here · ' + walkWords(w);
    });
  });
  map.on('mouseout', function () { tip.hidden = true; $('read').textContent = ''; if (hovered >= 0) { hovered = -1; draw(); markRow(); } });
  map.on('click', function (e) {
    var h = nearestHouse(e.containerPoint);
    if (h >= 0) select(h, false);
  });

  // ---------------------------------------------------------------- filtering
  function applyFilters() {
    var out = new Int32Array(N), n = 0;
    var valCap = state.val >= 5050 ? Infinity : state.val;
    for (var h = 0; h < N; h++) {
      if (H.walk[h] < state.walk) continue;
      if (H.g[h] + (state.shop ? H.sh[h] : 0) < state.space) continue;
      if (H.liv[h] < state.liv) continue;
      if (H.lot[h] < state.lot) continue;
      if (valCap !== Infinity && (H.val[h] === 0 || H.val[h] > valCap)) continue;
      out[n++] = h;
    }
    match = out.subarray(0, n);
    if (state.sort !== 'walk') {            // data is already ordered most-walkable first
      var arr = Array.prototype.slice.call(match), key;
      if (state.sort === 'space') key = function (a, b) { return spaceOf(b) - spaceOf(a) || H.walk[b] - H.walk[a]; };
      else if (state.sort === 'liv') key = function (a, b) { return H.liv[b] - H.liv[a]; };
      else key = function (a, b) { return (H.val[a] || 1e9) - (H.val[b] || 1e9); };
      arr.sort(key);
      match = Int32Array.from(arr);
    }
    renderCount(); renderList(); draw(); persist();
  }

  function renderCount() {
    $('count-n').textContent = fmt(match.length);
    $('count-t').textContent = (match.length === 1 ? 'house matches' : 'houses match') +
      ', of ' + fmt(N) + ' with 600+ sq ft of garage';
  }

  var list = $('list');
  function renderList() {
    list.textContent = '';
    if (!match.length) {
      list.appendChild(el('p', 'empty', 'No houses match. Lower the garage space or the walkability to widen the search.'));
      $('list-more').hidden = true;
      return;
    }
    var frag = document.createDocumentFragment(), top = Math.min(match.length, LIST_MAX);
    for (var k = 0; k < top; k++) {
      var h = match[k], row = el('button', 'row');
      row.type = 'button'; row.dataset.h = h;
      var a = el('span', 'row-addr', titleCase(H.addr[h]) || 'No street address');
      a.appendChild(el('span', 'row-city', cityOf(h)));
      var g = el('span', 'row-g'); g.appendChild(el('b', null, fmt(spaceOf(h)))); g.appendChild(el('small', null, 'sq ft'));
      var w = el('span', 'row-w'); w.appendChild(el('b', null, H.walk[h])); w.appendChild(el('small', null, 'walk'));
      row.appendChild(a); row.appendChild(g); row.appendChild(w);
      frag.appendChild(row);
    }
    list.appendChild(frag);
    list.scrollTop = 0;
    var more = $('list-more');
    more.hidden = match.length <= LIST_MAX;
    more.textContent = 'Showing the first ' + LIST_MAX + '. All ' + fmt(match.length) + ' are on the map.';
  }
  list.addEventListener('click', function (e) {
    var row = e.target.closest('.row'); if (row) select(+row.dataset.h, true);
  });
  list.addEventListener('mouseover', function (e) {
    var row = e.target.closest('.row'), h = row ? +row.dataset.h : -1;
    if (h !== hovered) { hovered = h; draw(); }
  });
  list.addEventListener('mouseleave', function () { if (hovered >= 0) { hovered = -1; draw(); } });
  function markRow() {
    var old = list.querySelector('.row.is-hover'); if (old) old.classList.remove('is-hover');
    if (hovered >= 0) { var r = list.querySelector('.row[data-h="' + hovered + '"]'); if (r) r.classList.add('is-hover'); }
  }

  // ---------------------------------------------------------------- house detail
  function select(h, fly) {
    selected = h;
    if (fly) map.setView([H.lat[h], H.lon[h]], Math.max(map.getZoom(), 16)); else draw();
    renderDetail(h);
  }
  function fact(ul, label, value) {
    var li = el('li'); li.appendChild(el('span', null, label)); li.appendChild(el('span', null, value)); ul.appendChild(li);
  }
  function link(ul, text, href) {
    var li = el('li'), a = el('a', null, text);
    a.href = href; a.target = '_blank'; a.rel = 'noopener';
    li.appendChild(a); ul.appendChild(li);
  }
  function renderDetail(h) {
    var d = $('detail'); d.textContent = '';
    var back = el('button', 'back', 'Back to the list'); back.type = 'button';
    back.addEventListener('click', function () {
      selected = -1; d.hidden = true; $('results').hidden = false;
      document.querySelector('.panel').classList.remove('is-detail'); draw();
    });
    d.appendChild(back);

    var addr = titleCase(H.addr[h]) || 'No street address', city = cityOf(h);
    d.appendChild(el('h2', null, addr));
    d.appendChild(el('p', 'where', city + (H.zip[h] ? ' ' + H.zip[h] : '')));

    // listing and lookup links first, so they are one click away
    var plainCity = city.replace(' (uninc.)', ''), full = addr + ' ' + plainCity + ' WA ' + (H.zip[h] || '');
    var quick = el('ul', 'quick');
    link(quick, 'Zillow', 'https://www.zillow.com/homes/' + encodeURIComponent(full.trim().replace(/\s+/g, '-')) + '_rb/');
    link(quick, 'Find on Redfin', 'https://www.google.com/search?q=' + encodeURIComponent('site:redfin.com "' + addr + '" ' + plainCity));
    link(quick, 'Street View', 'https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=' + H.lat[h] + ',' + H.lon[h]);
    link(quick, 'Official Walk Score', 'https://www.walkscore.com/score/loc/lat=' + H.lat[h] + '/lng=' + H.lon[h]);
    link(quick, 'County record', 'https://blue.kingcounty.com/Assessor/eRealProperty/Dashboard.aspx?ParcelNbr=' + H.pin[h]);
    d.appendChild(quick);

    var pair = el('div', 'pair');
    var g = el('div', 'big'); g.appendChild(el('b', null, fmt(H.g[h]))); g.appendChild(el('span', null, 'sq ft of garage, ' + carsWords(H.g[h])));
    var w = el('div', 'big walk'); w.appendChild(el('b', null, H.walk[h])); w.appendChild(el('span', null, 'walkability, ' + walkWords(H.walk[h])));
    pair.appendChild(g); pair.appendChild(w); d.appendChild(pair);

    d.appendChild(el('h3', null, 'Garage and outbuildings'));
    var ul = el('ul', 'facts');
    if (H.ga[h]) fact(ul, 'Attached garage', fmt(H.ga[h]) + ' sq ft');
    if (H.gb[h]) fact(ul, 'Garage in basement', fmt(H.gb[h]) + ' sq ft');
    if (H.gd[h]) fact(ul, 'Detached garage', fmt(H.gd[h]) + ' sq ft');
    if (H.sh[h]) fact(ul, 'Shop or barn', fmt(H.sh[h]) + ' sq ft');
    if (H.cp[h]) fact(ul, 'Carport', fmt(H.cp[h]) + ' sq ft');
    d.appendChild(ul);
    if (H.note[h]) d.appendChild(el('p', 'note', 'County note: ' + H.note[h]));

    d.appendChild(el('h3', null, 'On foot from here'));
    ul = el('ul', 'facts');
    fact(ul, 'Grocery store', H.groc[h] >= 99 ? 'none within reach' : H.groc[h] + ' min walk');
    fact(ul, 'Restaurants and cafés', H.food[h] + ' within 10 min');
    fact(ul, 'Shops', H.shops[h] + ' within 10 min');
    fact(ul, 'Park', H.park[h] >= 99 ? 'none within reach' : H.park[h] + ' min walk');
    var st = META.stations[H.linkn[h]];
    if (st) fact(ul, 'Light rail', H.link[h] >= 99 ? 'over 90 min walk' : st[2] + ', ' + H.link[h] + ' min walk');
    d.appendChild(ul);

    d.appendChild(el('h3', null, 'House'));
    ul = el('ul', 'facts');
    fact(ul, 'Living area', fmt(H.liv[h]) + ' sq ft');
    fact(ul, 'Bedrooms, baths', H.bed[h] + ' bed, ' + H.bath[h] + ' bath');
    if (H.bsmt[h]) fact(ul, 'Basement', fmt(H.bsmt[h]) + ' sq ft' + (H.dayb[h] ? ', daylight' : ''));
    fact(ul, 'Lot', fmt(H.lot[h]) + ' sq ft (' + (H.lot[h] / 43560).toFixed(2) + ' acre)');
    fact(ul, 'Built', H.yr[h] ? String(H.yr[h]) : 'unknown');
    if (H.units[h] > 1) fact(ul, 'Living units', String(H.units[h]));
    fact(ul, 'County appraisal', money(H.val[h]));
    if (H.noise[h] > 0) fact(ul, 'Traffic noise', ['', 'moderate', 'high', 'extreme'][H.noise[h]] || 'noted');
    if (H.use && META.uses && META.uses[H.use[h]]) fact(ul, 'County use', META.uses[H.use[h]]);
    if (H.zone && META.zones && META.zones[H.zone[h]]) fact(ul, 'Zoning', META.zones[H.zone[h]]);
    d.appendChild(ul);

    $('results').hidden = true; d.hidden = false; d.scrollTop = 0;
    document.querySelector('.panel').classList.add('is-detail');
    back.focus();
  }

  // ---------------------------------------------------------------- controls
  var sliders = [
    { id: 'space', label: function (v) { return fmt(v) + ' sq ft or more'; } },
    { id: 'walk', label: function (v) { return v === 0 ? 'Any' : v + ' or higher'; } },
    { id: 'liv', label: function (v) { return v === 0 ? 'Any' : fmt(v) + ' sq ft or more'; } },
    { id: 'val', cap: true, label: function (v) { return v >= 5050 ? 'No limit' : 'Up to ' + money(v); } },
    { id: 'lot', label: function (v) { return v === 0 ? 'Any' : fmt(v) + ' sq ft or more'; } }
  ];
  function paint(s) {
    var inp = $('f-' + s.id), v = +inp.value;
    inp.style.setProperty('--p', ((v - inp.min) / (inp.max - inp.min) * 100) + '%');
    $('o-' + s.id).textContent = s.label(v);
  }
  sliders.forEach(function (s) {
    var inp = $('f-' + s.id);
    if (s.cap) inp.classList.add('cap');
    inp.value = state[s.id]; paint(s);
    inp.addEventListener('input', function () { state[s.id] = +inp.value; paint(s); applyFilters(); });
  });
  $('f-shop').checked = state.shop;
  $('f-shop').addEventListener('change', function (e) { state.shop = e.target.checked; applyFilters(); });
  $('sort').value = state.sort;
  $('sort').addEventListener('change', function (e) { state.sort = e.target.value; applyFilters(); });
  $('reset').addEventListener('click', function () {
    Object.assign(state, DEFAULTS);
    sliders.forEach(function (s) { $('f-' + s.id).value = state[s.id]; paint(s); });
    $('f-shop').checked = false; $('sort').value = 'walk';
    applyFilters();
  });

  walkLayer.addTo(map);
  $('l-walk').addEventListener('change', function (e) { e.target.checked ? walkLayer.addTo(map) : walkLayer.remove(); });
  $('l-places').addEventListener('change', function (e) { showPlaces = e.target.checked; draw(); });
  $('l-rail').addEventListener('change', function (e) { e.target.checked ? railLayer.addTo(map) : railLayer.remove(); });
  Array.prototype.forEach.call(document.querySelectorAll('input[name="base"]'), function (r) {
    r.checked = r.value === baseName;
    r.addEventListener('change', function () { if (r.checked) setBase(r.value); });
  });

  var src = META.sources || {};
  $('notes').textContent = 'Walkability is this map’s own estimate from OpenStreetMap places' +
    (src.osm ? ' (' + src.osm + ')' : '') + ', not the official Walk Score; each house links to the official one. ' +
    'Garage sizes are King County Assessor floor areas' + (src.assessor ? ' (' + src.assessor + ')' : '') +
    '. The county does not record door height.';

  applyFilters();
})();
