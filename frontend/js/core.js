// core.js
(() => {
  const $ = (id) => document.getElementById(id);

  const state = {
    baseUrl: localStorage.getItem('csr.baseUrl') || 'http://127.0.0.1:5000',
    token:    localStorage.getItem('csr.token')  || '',
    user:     localStorage.getItem('csr.user')   || null,
    flat: [],
    tree: []
  };

  // --------- Vues ---------
  function showView(name) {
    const login = $('view-login');
    const app   = $('view-app');
    if (login) login.style.display = (name === 'login') ? '' : 'none';
    if (app)   app.style.display   = (name === 'app')   ? '' : 'none';
  }

  // --------- UI helpers ---------
  function setStatus(text, cls) {
    const el = $('status');
    if (!el) return;
    el.textContent = text;
    el.className = (cls === 'ok') ? 'ok' : (cls === 'err') ? 'err' : 'muted';
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'
    }[c]));
  }

  // --------- State setters ---------
  function setBaseUrl(url) {
    state.baseUrl = (url || '').trim();
    localStorage.setItem('csr.baseUrl', state.baseUrl);
    const inputs = [ $('baseUrl'), $('loginBaseUrl') ].filter(Boolean);
    inputs.forEach(i => i.value = state.baseUrl);
  }

  function setToken(t) {
    state.token = t || '';
    if (state.token) localStorage.setItem('csr.token', state.token);
    else localStorage.removeItem('csr.token');
    const tokenInput = $('token');
    if (tokenInput) tokenInput.value = state.token;
  }

  function setUser(u) {
    state.user = u || null;
    if (state.user) localStorage.setItem('csr.user', state.user);
    else localStorage.removeItem('csr.user');
    const who = $('whoami');
    if (who) who.textContent = state.user ? `Connecté en tant que ${state.user}` : '';
  }

  // --------- API ---------
  async function api(path, options = {}) {
    const url = new URL(path, state.baseUrl).toString();
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (state.token) headers['Authorization'] = 'Bearer ' + state.token;

    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status} – ${text}`);
    }
    const ct = res.headers.get('content-type') || '';
    return ct.includes('application/json') ? res.json() : res.text();
  }

  // --------- Auth ---------
  async function login(username, password) {
    const body = JSON.stringify({ username, password });
    const data = await api('/api/login', { method: 'POST', body });

    // accepte { token } ou { access_token }
    const tok = data.token || data.access_token;
    if (!tok) throw new Error('Réponse login invalide: token manquant');

    setToken(tok);
    setUser(data.user || username);

    showView('app');                    // bascule UI
    $('token') && ($('token').value = tok); // recopie dans l’en-tête si présent
    return tok;
  }

  function logout() {
    setToken('');
    setUser(null);
    showView('login');
  }

  // --------- Arbre des thèmes ---------
  function buildTree(rows) {
    const byId = new Map();
    rows.forEach(r => byId.set(r.id, { ...r, children: [] }));
    const roots = [];
    rows.forEach(r => {
      const node = byId.get(r.id);
      if (r.parent_id == null) roots.push(node);
      else {
        const parent = byId.get(r.parent_id);
        if (parent) parent.children.push(node);
        else roots.push(node);
      }
    });
    const sortRec = (arr) => { arr.sort((a,b) => a.label.localeCompare(b.label)); arr.forEach(n => sortRec(n.children)); };
    sortRec(roots);
    return roots;
  }

  function renderTree(nodes) {
    const container = $('tree');
    if (!container) return;
    container.innerHTML = '';
    container.appendChild(renderNodes(nodes));
  }

  function renderNodes(nodes) {
    const ul = document.createElement('ul');
    ul.className = 'list';
    nodes.forEach(n => {
      const li = document.createElement('li');
      li.className = 'node';
      if (n.children && n.children.length) {
        const details = document.createElement('details');
        details.open = (n.lvl === 0);
        const sum = document.createElement('summary');
        sum.innerHTML = `<strong>${escapeHtml(n.label)}</strong> <span class="tag">id:${n.id}</span>`;
        sum.onclick = (e) => { e.stopPropagation(); showDetails(n); };
        details.appendChild(sum);
        details.appendChild(renderNodes(n.children));
        li.appendChild(details);
      } else {
        li.innerHTML = `<span>${escapeHtml(n.label)}</span> <span class="tag">id:${n.id}</span>`;
        li.onclick = () => showDetails(n);
      }
      ul.appendChild(li);
    });
    return ul;
  }

  function showDetails(n) {
    const pane = $('details');
    if (!pane) return;
    pane.innerHTML =
      `<div><div class="small muted">Identifiant</div><div style="margin-bottom:6px">${n.id}</div>
        <div class="small muted">Libellé</div><div style="margin-bottom:6px">${escapeHtml(n.label)}</div>
        <div class="small muted">Niveau</div><div style="margin-bottom:6px">${n.lvl}</div>
        <div class="small muted">Parent</div><div>${n.parent_id ?? '—'}</div></div>`;
  }

  // --------- Init ---------
  (function init() {
    if ($('baseUrl'))      $('baseUrl').value      = state.baseUrl;
    if ($('loginBaseUrl')) $('loginBaseUrl').value = state.baseUrl;
    if ($('token'))        $('token').value        = state.token;
    if ($('whoami') && state.user) $('whoami').textContent = `Connecté en tant que ${state.user}`;

    // au chargement, choisit la vue
    if (state.token) showView('app'); else showView('login');
  })();

  // expose en global
  window.core = {
    $, state,
    setBaseUrl, setToken, setUser,
    api, login, logout,
    showView, setStatus,
    buildTree, renderTree, renderNodes, showDetails,
    escapeHtml
  };
})();
