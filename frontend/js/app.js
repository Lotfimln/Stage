// app.js
(() => {
  const { $, state, setBaseUrl, setToken, api, login, logout } = window.core;

  // --- état local
  let selectedThemeId = null;
  let selectedThemeLabel = null;
  let lastSearchBody = null;   // mémorise la dernière recherche personnes

  // ---------- Boot ----------
  document.addEventListener('DOMContentLoaded', () => {
    const bu = $('baseUrl') || $('loginBaseUrl');
    if (bu) bu.value = state.baseUrl;
    if ($('token')) $('token').value = state.token;

    bindLogin();
    bindToolbar();
    bindTreeActions();
    bindPeopleSearch();
    bindAddPosForm();
    bindAddPositionUI();
    setupAutocomplete();
    bindCSRQueries();
    updateAuthUI();
    bindDashboard();
});


  // ---------- View switcher ----------
  function showView(name) {
    const views = Array.from(document.querySelectorAll('[data-view]'));
    if (views.length) {
      views.forEach(el => {
        const isTarget = el.getAttribute('data-view') === name;
        el.style.display = isTarget ? '' : 'none';
      });
    }
    const vLogin = $('view-login');
    const vApp   = $('view-app');
    if (vLogin && vApp) {
      vLogin.style.display = (name === 'login') ? '' : 'none';
      vApp.style.display   = (name === 'app')   ? '' : 'none';
    }
  }

  function updateAuthUI() {
    const authed = !!state.token;
    if (authed) {
      showView('app');
      const who = $('whoami');
      if (who) who.textContent = state.user ? `Connecté : ${state.user}` : 'Connecté';
      const t = $('token'); if (t) t.value = state.token;
      const b = $('baseUrl'); if (b) b.value = state.baseUrl;
      const check = $('check'); if (check) check.click();
    } else {
      showView('login');
      const b = $('loginBaseUrl'); if (b) b.value = state.baseUrl;
      const u = $('loginUser'); if (u) u.focus();
    }
  }

  // ---------- Login / Logout ----------
  function bindLogin() {
    const form = $('loginForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        setBaseUrl(($('loginBaseUrl')?.value || '').trim());
        const user = $('loginUser').value.trim();
        const pass = $('loginPass').value;

        setStatus('Connexion…');
        const tok = await login(user, pass);
        $('token') && ($('token').value = tok);
        $('baseUrl') && ($('baseUrl').value = state.baseUrl);

        setStatus('✅ Connecté', 'ok');
        updateAuthUI();
        if (window.reloadCSRQueries) window.reloadCSRQueries();
      } catch (e) {
        setStatus('❌ ' + (e?.message || e), 'err');
        showView('login');
      }
    });

    const out = $('logoutBtn');
    if (out) {
      out.onclick = () => {
        logout();
        setStatus('Déconnecté');
        updateAuthUI();
        clearPeople();
      };
    }
  }

  // ---------- Toolbar ----------
  function bindToolbar() {
    const save = $('save');
    if (save) {
      save.onclick = () => {
        setBaseUrl(($('baseUrl')?.value) || '');
        setToken(($('token')?.value || '').trim());
        setStatus('✅ Paramètres enregistrés', 'ok');
        updateAuthUI();
      };
    }

    const check = $('check');
    if (check) {
      check.onclick = async () => {
        try {
          const r = await api('/api/health');
          setStatus('✅ API OK: ' + JSON.stringify(r), 'ok');
        } catch (e) {
          setStatus('❌ ' + e.message, 'err');
          if (String(e.message).includes('401')) { logout(); updateAuthUI(); }
        }
      };
    }
  }

  // ---------- Tree (thèmes) ----------
  function bindTreeActions() {
    const loadTree = $('loadTree');
    if (loadTree) {
      loadTree.onclick = async () => {
        try {
          setStatus('Chargement…');
          const rows = await api('/api/themes/tree');
          state.flat = rows;
          state.tree = buildTree(rows);
          renderTree(state.tree);
          setStatus(`✅ ${rows.length} lignes reçues, arbre construit.`, 'ok');
        } catch (e) {
          setStatus('❌ ' + e.message, 'err');
        }
      };
    }

    const expandAll = $('expandAll');
    if (expandAll) expandAll.onclick = () => document.querySelectorAll('#tree details').forEach(d => d.open = true);

    const collapseAll = $('collapseAll');
    if (collapseAll) collapseAll.onclick = () => document.querySelectorAll('#tree details').forEach(d => d.open = false);
  }

  function buildTree(rows) {
    const byId = new Map();
    rows.forEach(r => byId.set(r.id, { ...r, children: [] }));
    const roots = [];
    rows.forEach(r => {
      const node = byId.get(r.id);
      if (r.parent_id == null) roots.push(node);
      else (byId.get(r.parent_id)?.children || roots).push(node);
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
    selectedThemeId = n.id;
    selectedThemeLabel = n.label;

    const box = $('details');
    if (!box) return;
    box.innerHTML =
      `<div>
        <div class="small muted">Identifiant</div><div style="margin-bottom:6px">${n.id}</div>
        <div class="small muted">Libellé</div><div style="margin-bottom:6px">${escapeHtml(n.label)}</div>
        <div class="small muted">Niveau</div><div style="margin-bottom:6px">${n.lvl}</div>
        <div class="small muted">Parent</div><div style="margin-bottom:6px">${n.parent_id ?? '—'}</div>
        <hr style="border-color:#1f2937;margin:8px 0">
        <div class="small muted">Sélection courante :</div>
        <div><strong>Thème #${n.id}</strong> — ${escapeHtml(n.label)}</div>
      </div>`;
  }

  // ---------- Recherche personnes ----------
  function bindPeopleSearch() {
    const btnSearch = $('btnSearch');
    if (btnSearch) {
      btnSearch.onclick = async () => {
        if (!selectedThemeId) {
          setStatus('Sélectionne d’abord un thème dans l’arbre.', 'err');
          return;
        }
        try {
          setStatus('Recherche en cours…');
          const body = {
            theme_ids: [selectedThemeId],
            include_desc: !!$('chkIncludeDesc')?.checked,
            role: $('selRole')?.value || '*',
            temporalite: $('selTemp')?.value || '*',
            mode: $('selMode')?.value || '*',
            structure_id: (v => v ? parseInt(v, 10) : null)($('inputStructId')?.value?.trim() || '')
          };

          lastSearchBody = body;
          const rows = await api('/api/people/search', {
            method: 'POST',
            body: JSON.stringify(body)
          });

          renderPeople(rows);
          setStatus(`✅ ${rows.length} résultat(s) pour « ${selectedThemeLabel} »`, 'ok');
        } catch (e) {
          setStatus('❌ ' + e.message, 'err');
        }
      };
    }

    const btnNonPos = $('btnNonPos');
    if (btnNonPos) {
      btnNonPos.onclick = async () => {
        try {
          setStatus('Chargement des non positionnés…');
          // NB: on ne mémorise pas cette "recherche" dans lastSearchBody
          const data = await api('/api/stats/non_positionnes');
          renderPeople(data.people || []);
          setStatus(`✅ ${data.total} personne(s) sans positionnement`, 'ok');
        } catch (e) {
          setStatus('❌ ' + e.message, 'err');
        }
      };
    }
  }
function renderPeople(rows) {
  const tbody = $('peopleTbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  (rows || []).forEach(r => {
    const tr = document.createElement('tr');

    // champs avec tolérance de casse
    const nom   = pick(r, 'nom', 'NOM') || '';
    const pren  = pick(r, 'prenom', 'PRENOM') || '';
    const theme = pick(r, 'theme', 'THEME') || '';
    const role  = pick(r, 'libcontribution', 'LIBCONTRIBUTION', 'role', 'ROLE') || '';
    const temp  = pick(r, 'libelletemporalite', 'LIBELLETEMPORALITE', 'temp', 'TEMP') || '';
    const idStr = pick(r, 'idstructure', 'IDSTRUCTURE');

    const auto = pick(r, 'auto_genere', 'AUTO_GENERE');
    const isManual = (auto == null || String(auto) !== '0'); // MANU si auto_genere null ou != '0'

    tr.innerHTML = `
      <td>${escapeHtml(nom)}</td>
      <td>${escapeHtml(pren)}</td>
      <td>${escapeHtml(theme)}</td>
      <td>${escapeHtml(role)}</td>
      <td>${escapeHtml(temp)}</td>
      <td>${idStr ?? ''}</td>
      <td style="text-align:right; white-space:nowrap;"></td>
    `;

    const actions = tr.lastElementChild;

    // bouton "Ajouter" (ouvre le dialog prérempli)
    const btnAdd = document.createElement('button');
    btnAdd.textContent = 'Ajouter';
    btnAdd.title = 'Ajouter un positionnement pour cette personne';
    btnAdd.onclick = () => openAddPos({
      idpers: pick(r, 'idpers', 'IDPERS'),
      nom:    pick(r, 'nom', 'NOM'),
      prenom: pick(r, 'prenom', 'PRENOM'),
      idtheme: pick(r, 'idtheme', 'IDTHEME') || selectedThemeId,
      theme:   theme || selectedThemeLabel
    });
    actions.appendChild(btnAdd);

    // bouton "Supprimer" (uniquement si MANU)
    const btnDel = document.createElement('button');
    btnDel.textContent = 'Supprimer';
    btnDel.style.marginLeft = '6px';
    btnDel.disabled = !isManual;
    btnDel.title = isManual ? 'Supprimer ce positionnement' : 'Positionnement auto – suppression désactivée';
    btnDel.onclick = async () => {
      if (!confirm('Supprimer ce positionnement ?')) return;
      try {
        const payload = {
          idpers: pick(r, 'idpers', 'IDPERS'),
          idtheme: pick(r, 'idtheme', 'IDTHEME'),
          libcontr: pick(r, 'libcontribution', 'LIBCONTRIBUTION', 'role', 'ROLE'),
          libtemp:  pick(r, 'libelletemporalite', 'LIBELLETEMPORALITE', 'temp', 'TEMP')
        };
        await api('/api/positions', { method: 'DELETE', body: JSON.stringify(payload) });

        if (lastSearchBody) {
          const refreshed = await api('/api/people/search', {
            method: 'POST',
            body: JSON.stringify(lastSearchBody)
          });
          renderPeople(refreshed);
        } else {
          tr.remove();
        }
        setStatus('✅ Positionnement supprimé', 'ok');
      } catch (e) {
        setStatus('❌ ' + (e?.message || e), 'err');
      }
    };
    actions.appendChild(btnDel);

    tbody.appendChild(tr);
  });
}


  function clearPeople() {
    const tbody = $('peopleTbody');
    if (tbody) tbody.innerHTML = '';
  }

  // ---------- Ajout de positionnement (UI & form) ----------
function bindAddPositionUI() {
  // Ouvrir le dialogue global (sans personne pré-sélectionnée)
  const btnOpen = $('btnOpenAdd');
  if (btnOpen) {
    btnOpen.onclick = () => {
      openAddPos({
        idpers: '',
        nom: '',
        prenom: '',
        idtheme: selectedThemeId,
        theme: selectedThemeLabel
      });
    };
  }

  // Si on tape directement un ID de thème, renseigner le libellé
  const idThemeField = $('ap_idtheme');
  if (idThemeField && !idThemeField.dataset.autoBound) {
    idThemeField.dataset.autoBound = '1';
    idThemeField.addEventListener('input', () => {
      const id = parseInt(idThemeField.value, 10);
      const label = (!isNaN(id) ? lookupThemeLabelById(id) : '');
      if ($('ap_libtheme')) $('ap_libtheme').value = label || '';
    });
  }

  // ========== Pickers (personne / thème / structure) ==========
  // PERSONNE (single)
    const ipp = $('ap_person');
    if (ipp) ipp.removeAttribute('list');
    if (ipp && !ipp._pickerInstalled) {
      attachPicker(ipp, {
        mode: 'single',
        fetcher: fetchPeopleLike, // /api/people/find?q=
        minChars: 0,              // ouvre la liste même si on ne tape rien
        onPick: it => { $('ap_idpers').value = it.id; }
      });
    }

    const ipt = $('ap_theme');
    if (ipt) ipt.removeAttribute('list');
    if (ipt && !ipt._pickerInstalled) {
      attachPicker(ipt, {
        mode: 'single',
        fetcher: fetchThemesLike, // /api/themes/find?q=
        toItem: r => ({ id: Number(r.id ?? r.ID), label: String(r.label ?? r.LABEL) }),
        minChars: 0,
        onPick: it => {
          $('ap_idtheme').value  = it.id;
          $('ap_libtheme').value = it.label;
        }
      });
    }

    const ips = $('ap_libstruct'); // libellé structure (champ texte)
    if (ips && !ips._pickerInstalled) {
      attachPicker(ips, {
        mode: 'single',
        fetcher: fetchStructsLike, // /api/structures/find?q=
        toItem: r => ({ id: Number(r.id ?? r.ID), label: String(r.label ?? r.LABEL ?? r.id) }),
        minChars: 0,
        onPick: it => {
          $('ap_idstruct').value = it.id;
          $('ap_libstruct').value = it.label;
        }
      });
    }
    


}


function bindAddPosForm() {
    const form = $('formAddPos');
    const dlg  = $('dlgAddPos');
    const save = $('btnSavePos');
    if (!form || !dlg || !save) return;

    save.addEventListener('click', async (e) => {
    e.preventDefault();
    try {
        // récupérer idpers
        let idpers = parseInt($('ap_idpers').value, 10);
        if (!idpers) {
        idpers = extractIdFromTagged($('ap_person').value) || null;
        }
        // récupérer idtheme
        let idtheme = parseInt($('ap_idtheme').value, 10);
        if (!idtheme) {
        idtheme = extractIdFromTagged($('ap_theme').value) || null;
        }

        const body = {
        idpers: idpers,
        idtheme: idtheme,
        libcontr: $('ap_libcontr').value,
        libtemp: $('ap_libtemp').value,
        idstruct: valOrNull('ap_idstruct'),
        libstruct: valOrNull('ap_libstruct'),
        idtypestruct: valOrNull('ap_idtypestruct'),
        libtypestruct: valOrNull('ap_libtypestruct')
        };

        if (!body.idpers || !body.idtheme) {
        setApStatus('ID personne et ID thème sont requis', 'err');
        return;
        }

        await api('/api/positions', { method: 'POST', body: JSON.stringify(body) });

        setApStatus('✅ Positionnement enregistré', 'ok');

        // rafraîchir la dernière recherche si dispo
        if (lastSearchBody) {
        const refreshed = await api('/api/people/search', {
            method: 'POST',
            body: JSON.stringify(lastSearchBody)
        });
        renderPeople(refreshed);
        }

        setTimeout(() => dlg.close(), 400);
    } catch (err) {
        setApStatus('❌ ' + (err?.message || err), 'err');
    }
    });

    function valOrNull(id) {
    const v = $(id).value;
    return v === '' ? null : isNaN(v) ? v : Number(v);
    }
    function setApStatus(msg, cls) {
    const el = $('ap_status');
    el.textContent = msg;
    el.className = 'small ' + (cls === 'ok' ? 'ok' : cls === 'err' ? 'err' : 'muted');
    }
}

// Ouvre le dialogue "Ajouter un positionnement" avec des valeurs préremplies
function openAddPos({ idpers = '', nom = '', prenom = '', idtheme = '', theme = '' } = {}) {
  const dlg = $('dlgAddPos');
  if (!dlg) return;

  if ($('ap_idpers'))  $('ap_idpers').value = idpers || '';
  if ($('ap_person'))  $('ap_person').value = [prenom, nom].filter(Boolean).join(' ');
  if ($('ap_person_label')) $('ap_person_label').textContent = $('ap_person')?.value || '';

  if ($('ap_idtheme'))   $('ap_idtheme').value = idtheme || '';
  if ($('ap_theme'))     $('ap_theme').value = theme ? `${theme} (#${idtheme || ''})`.trim() : '';
  if ($('ap_libtheme'))  $('ap_libtheme').value = theme || '';

  // Valeurs par défaut "raisonnables"
  if ($('ap_libcontr') && !$('ap_libcontr').value) $('ap_libcontr').value = 'Contributeur';
  if ($('ap_libtemp')  && !$('ap_libtemp').value)  $('ap_libtemp').value  = 'Présent';

  dlg.showModal?.();
}


// ---------- Helpers ----------
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
// retourne la 1re valeur définie parmi une liste de noms de clés (gère la casse)
function pick(r, ...names) {
  for (const n of names) {
    if (r && r[n] !== undefined && r[n] !== null) return r[n];
  }
  return undefined;
}


function extractIdFromTagged(s) {
    if (!s) return null;
    const m = String(s).match(/\(#(\d+)\)/);
    return m ? parseInt(m[1], 10) : null;
}

function lookupThemeLabelById(id) {
    if (!id || !Array.isArray(state.flat) || !state.flat.length) return '';
    const row = state.flat.find(r => Number(r.id) === Number(id));
    return row ? row.label : '';
}

// tente un GET et renvoie [] si 404 / endpoint absent
async function safeFind(url) {
    try {
    const res = await fetch(new URL(url, state.baseUrl).toString(), {
        headers: state.token ? { 'Authorization': 'Bearer ' + state.token } : {}
    });
    if (!res.ok) return [];
    const ct = res.headers.get('content-type') || '';
    return ct.includes('application/json') ? (await res.json()) : [];
    } catch (e){
    return [];
    }
}

function debounce(fn, ms) {
    let t = null;
    return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
    };
}
    // --- AUTOCOMPLETE -----------------------------------------------------------
function setupAutocomplete() {
  // mémos des suggestions (clé = texte affiché dans le datalist)
  const mapPerson = new Map();
  const mapTheme  = new Map();
  let tPerson = null, tTheme = null;

  // PERSONNE
  const inpP = $('ap_person'), dlP = $('dlPersons');
  if (inpP && dlP) {
    inpP.addEventListener('input', () => {
      $('ap_idpers').value = ''; // reset tant que non validé
      const term = inpP.value.trim();
      if (term.length < 2) { dlP.innerHTML = ''; mapPerson.clear(); return; }
      clearTimeout(tPerson);
      tPerson = setTimeout(async () => {
        try {
          const rows = await api('/api/people/find?q=' + encodeURIComponent(term));
          dlP.innerHTML = ''; mapPerson.clear();
          rows.forEach(r => {
            const label = `${r.nom || ''} ${r.prenom || ''}`.trim();
            const value = `${label} (#${r.idpers})`;
            const opt = document.createElement('option');
            opt.value = value;
            dlP.appendChild(opt);
            mapPerson.set(value, r);
          });
        } catch (e) { /* silencieux */ }
      }, 200);
    });

    inpP.addEventListener('change', () => {
      const k = inpP.value;
      const r = mapPerson.get(k);
      if (r) {
        $('ap_idpers').value = r.idpers;
        const lbl = $('ap_person_label'); if (lbl) lbl.textContent = `${r.prenom || ''} ${r.nom || ''}`.trim();
      }
    });
  }

  // THEME
  const inpT = $('ap_theme'), dlT = $('dlThemes');
  const idTheme = $('ap_idtheme'), libTheme = $('ap_libtheme');
  if (inpT && dlT) {
    inpT.addEventListener('input', () => {
      if (idTheme) idTheme.value = '';
      if (libTheme) libTheme.value = '';
      const term = inpT.value.trim();
      if (term.length < 2) { dlT.innerHTML = ''; mapTheme.clear(); return; }
      clearTimeout(tTheme);
      tTheme = setTimeout(async () => {
        try {
          const rows = await api('/api/themes/find?q=' + encodeURIComponent(term));
          dlT.innerHTML = ''; mapTheme.clear();
          rows.forEach(r => {
            const value = `${r.label} (#${r.id})`;
            const opt = document.createElement('option');
            opt.value = value;
            dlT.appendChild(opt);
            mapTheme.set(value, r);
          });
        } catch (e) { /* silencieux */ }
      }, 200);
    });

    inpT.addEventListener('change', () => {
      const k = inpT.value;
      const r = mapTheme.get(k);
      if (r) {
        if (idTheme) idTheme.value = r.id;
        if (libTheme) libTheme.value = r.label;
      }
    });
  }

  // si l'utilisateur tape directement un ID thème, deviner le libellé depuis l'arbre déjà chargé
  if (idTheme) {
    idTheme.addEventListener('change', () => {
      const v = Number(idTheme.value);
      const found = state.flat?.find?.(x => Number(x.id) === v);
      if (libTheme) libTheme.value = found ? found.label : '';
    });
  }
}
// ---------- Requêtes CSR ----------
function normalizeFields(q) {
  // Nouveau format (schema.fields)
  if (q && q.schema && Array.isArray(q.schema.fields)) {
    return q.schema.fields.map(f => ({
      key: f.key,
      label: f.label || f.key,
      type: f.type || 'text',
      options: f.options || [],
      placeholder: f.placeholder || '',
      default: f.default,
      rawType: f.rawType || f.type || 'text'
    }));
  }

  // Ancien format (params: {name:'int', 'int[]', 'bool', 'str'…})
  const p = (q && q.params) ? q.params : {};
  const res = [];

  const SELECTS = {
    role:         ["*", "Expert", "Contributeur", "Utilisateur"],
    temporalite:  ["*", "Présent", "Passé"],
    mode:         ["*", "AUTO", "MANU"],
    match:        ["ANY", "ALL"]
  };

  Object.entries(p).forEach(([key, typ]) => {
    if (key in SELECTS) {
      res.push({ key, label: key, type: 'select', options: SELECTS[key], default: SELECTS[key][0], rawType: 'str' });
      return;
    }
    if (typ === 'bool') {
      res.push({ key, label: key, type: 'checkbox', default: true, rawType: 'bool' });
      return;
    }
    if (typ === 'int' || typ === 'int?') {
      res.push({ key, label: key, type: 'number', placeholder: typ, rawType: typ });
      return;
    }
    // int[] / str -> text (on garde le type d’origine dans rawType)
    res.push({ key, label: key, type: 'text', placeholder: typ, rawType: typ });
  });

  return res;
}



let csrInitDone = false; 

async function themesSuggest(q) {
  q = (q || '').trim();

  // 1) Essaye toujours l'API, même si q == '' (pour pré-ouvrir une liste)
  try {
    const rows = await safeFind('/api/themes/find?q=' + encodeURIComponent(q));
    if (Array.isArray(rows) && rows.length) return rows; // [{id,label}]
  } catch { /* ignore */ }

  // 2) Fallback local si l'arbre est dispo
  if (Array.isArray(state.flat) && state.flat.length) {
    const needle = q.toLowerCase();
    const take = (arr) => arr.slice(0, 50).map(t => ({ id: t.id, label: t.label }));
    if (!needle) return take(state.flat); // q vide → premières 50 locales
    const filtered = state.flat.filter(t =>
      String(t.id).startsWith(needle) ||
      (t.label || '').toLowerCase().includes(needle)
    );
    return take(filtered);
  }

  return [];
}
function themeMinChars() {
  return (Array.isArray(state.flat) && state.flat.length) ? 0 : 0;
}


async function bindCSRQueries() {
  const select    = $('csrQuery')   || $('csrSelect');
  const paramsBox = $('csrParams');
  const runBtn    = $('btnRunQuery')|| $('csrRun');
  if (!select || !runBtn || !paramsBox) return;

  // ---- form params (re)builder
  function renderParams() {
    paramsBox.innerHTML = '';
    const opt = select.options[select.selectedIndex];
    if (!opt || !opt.value) return;

    const q = JSON.parse(opt.dataset.q || '{}');
    const fields = normalizeFields(q);

    fields.forEach(f => {
      // pré-normalise quelques enums
      if (f.key === 'role')        { f.type = 'select'; f.options = ['*','Expert','Contributeur','Utilisateur']; f.default ??= '*'; }
      if (f.key === 'temporalite') { f.type = 'select'; f.options = ['*','Présent','Passé'];                       f.default ??= '*'; }
      if (f.key === 'mode')        { f.type = 'select'; f.options = ['*','AUTO','MANU'];                           f.default ??= '*'; }
      if (f.key === 'match')       { f.type = 'select'; f.options = ['ANY','ALL'];                                  f.default ??= 'ANY'; }

      const wrap = document.createElement('div');
      wrap.style.display = 'flex';
      wrap.style.flexDirection = 'column';
      wrap.style.minWidth = '200px';

      const lab = document.createElement('label');
      lab.className = 'small muted';
      lab.textContent = f.label;

      let input;
      if (f.type === 'checkbox') {
        input = document.createElement('input'); input.type = 'checkbox';
        if (f.default !== undefined) input.checked = !!f.default;
      } else if (f.type === 'number') {
        input = document.createElement('input'); input.type = 'text';
        if (f.placeholder) input.placeholder = f.placeholder;
        if (f.default !== undefined) input.value = f.default;
      } else if (f.type === 'select') {
        input = document.createElement('select');
        (f.options || []).forEach(v => {
          const o = document.createElement('option'); o.value = v; o.textContent = v;
          input.appendChild(o);
        });
        if (f.default !== undefined) input.value = f.default;
      } else {
        input = document.createElement('input'); input.type = 'text';
        if (f.placeholder) input.placeholder = f.placeholder;
        if (f.default !== undefined) input.value = f.default;
      }

      // --- MAPPING → PICKERS (zéro requête réseau pour les thèmes)
      input.id = 'csr_' + f.key;
      input.name = f.key;
      const k = String(f.key || '').toLowerCase();

      // PERSON (single)
      if (/(^|_)person(_id)?$/.test(k) || k === 'idpers') {
        if (input.tagName === 'INPUT') input.type = 'text';
        attachPicker(input, {
          mode: 'single',
          fetcher: fetchPeopleLike, 
          minChars: 0
        });

      } else if (k === 'structure_id') {
      // single structure
      if (input.tagName === 'INPUT') input.type = 'text';
      attachPicker(input, {
        mode: 'single',
        chipSingle : true,
        fetcher: fetchStructsLike,
        toItem: r => ({ id: r.id, label: r.label }),
        minChars: 0
      });
    } else if (['structure_ids','include_structures','exclude_structures'].includes(k)) {
      // multi structures
      if (input.tagName === 'INPUT') input.type = 'text';
      attachPicker(input, {
        mode: 'multi',
        fetcher: fetchStructsLike,
        toItem: r => ({ id: r.id, label: r.label }),
        minChars: 0
      });
      } else if (f.key === 'theme_ids' || f.key === 'exclude_theme_ids') {
        attachPicker(input, {
          mode: 'multi',
          fetcher: fetchThemesLike,
          toItem: r => ({ id: r.id, label: r.label }),
          minChars: 0              // ← ouvre une liste dès le focus
        });
      } else if (f.key === 'root_theme_id') {
        attachPicker(input, {
          mode: 'single',
          fetcher: fetchThemesLike,
          toItem: r => ({ id: r.id, label: r.label }),
          minChars: 0
        });
      }

      wrap.appendChild(lab);
      wrap.appendChild(input);
      paramsBox.appendChild(wrap);
    });
  }

  // ---- (re)charge le catalogue quand le token est là
  const loadQueries = async () => {
    paramsBox.innerHTML = '';
    if (!state.token) {
      select.innerHTML = '<option value="">— connecte-toi pour voir les requêtes —</option>';
      return;
    }
    try {
      const queries = await api('/api/queries');
      select.innerHTML = '<option value="">— choisir une requête —</option>';
      (queries || []).forEach(q => {
        const opt = document.createElement('option');
        opt.value = q.id;
        opt.textContent = q.label || q.id;
        opt.dataset.q = JSON.stringify(q);
        select.appendChild(opt);
      });
      renderParams();
    } catch (e) {
      const msg = String(e?.message || '');
      if (msg.includes('401')) {
        select.innerHTML = '<option value="">— session expirée : reconnecte-toi —</option>';
      } else {
        select.innerHTML = '<option value="">— erreur : ' + msg + ' —</option>';
      }
    }
  };

  window.reloadCSRQueries = loadQueries; // appelé après login / “Enregistrer”
  if (state.token) await loadQueries();

  select.onchange = renderParams;

  // ---- Exécution
  runBtn.onclick = async () => {
    try {
      const opt = select.options[select.selectedIndex];
      if (!opt || !opt.value) { setStatus('Choisis une requête.', 'err'); return; }

      const q = JSON.parse(opt.dataset.q || '{}');
      const fields = normalizeFields(q);

      const body = {};
      fields.forEach(f => {
        const el = $('csr_' + f.key);
        if (!el) return;

        let val;
        if (typeof el._getValue === 'function')      val = el._getValue();
        else if (f.type === 'checkbox')              val = el.checked;
        else if (f.type === 'number')                val = (el.value === '' ? null : Number(el.value));
        else                                         val = el.value;

        const t = String(f.rawType || '').toLowerCase();
        if (t === 'int' || t === 'int?')            val = (val === '' || val == null) ? null : Number(val);
        else if (t === 'int[]') {
          if (Array.isArray(val))                   val = val.map(n => Number(n)).filter(n => !Number.isNaN(n));
          else                                      val = String(val || '').split(/[,\s;]+/).filter(Boolean).map(Number).filter(n=>!Number.isNaN(n));
        } else if (t === 'bool')                    val = !!val;

        body[f.key] = val;
      });

      // console.debug('POST /api/queries/'+opt.value, body);

      const rows = await api(`/api/queries/${opt.value}`, {
        method: 'POST',
        body: JSON.stringify(body)
      });
      renderCSRTable(rows);
      setStatus(`✅ ${Array.isArray(rows) ? rows.length : 0} ligne(s)`, 'ok');
    } catch (e) {
      setStatus('❌ ' + (e?.message || e), 'err');
    }
  };
}

function renderCSRTable(rows) {
  // Compat : soit table avec thead/tbody, soit un conteneur libre (#csrOut)
  const thead = $('csrThead');
  const tbody = $('csrTbody');
  const out   = $('csrOut');

  if (thead && tbody) {
    thead.innerHTML = '';
    tbody.innerHTML = '';
    if (!rows || !rows.length) return;

    const cols = Object.keys(rows[0]);

    const trh = document.createElement('tr');
    cols.forEach(c => { const th = document.createElement('th'); th.textContent = c; trh.appendChild(th); });
    thead.appendChild(trh);

    rows.forEach(r => {
      const tr = document.createElement('tr');
      cols.forEach(c => { const td = document.createElement('td'); td.textContent = r[c] ?? ''; tr.appendChild(td); });
      tbody.appendChild(tr);
    });
  } else if (out) {
    out.innerHTML = '';
    if (!rows || !rows.length) { out.textContent = '(aucun résultat)'; return; }

    const cols = Object.keys(rows[0]);
    const tbl = document.createElement('table'); tbl.style.width = '100%'; tbl.style.borderCollapse = 'collapse';

    const thead = document.createElement('thead');
    const trh = document.createElement('tr');
    cols.forEach(c => { const th = document.createElement('th'); th.textContent = c; th.style.padding='8px 10px'; th.style.borderBottom='1px solid #1f2937'; trh.appendChild(th); });
    thead.appendChild(trh); tbl.appendChild(thead);

    const tbody = document.createElement('tbody');
    rows.forEach(r => {
      const tr = document.createElement('tr');
      cols.forEach(c => { const td = document.createElement('td'); td.textContent = r[c] ?? ''; td.style.padding='8px 10px'; td.style.borderBottom='1px solid #1f2937'; tr.appendChild(td); });
      tbody.appendChild(tr);
    });
    tbl.appendChild(tbody);
    out.appendChild(tbl);
  }
}
async function fetchThemesLike(q) {
  const term = (q ?? '').trim();
  try {
    const rows = await window.core.api('/api/themes/find?q=' + encodeURIComponent(term));
    if (Array.isArray(rows) && rows.length) {
      return rows.map(r => ({
        id: Number(r.id ?? r.ID ?? r.cs_th_cod ?? r['CS_TH_COD#'] ?? r.CS_TH_COD),
        label: String(r.label ?? r.LABEL ?? r.theme ?? r.THEME)
      }));
    }
  } catch {}
  // Fallback local si l'API ne renvoie rien
  return fetchThemesSmart(term); // utilise ensureThemesFlatLoaded() en interne
}


async function fetchPeopleLike(q) {
  const term = (q ?? '').trim();
  try {
    const rows = await window.core.api('/api/people/find?q=' + encodeURIComponent(term));
    return (rows || []).map(r => ({
      id: Number(r.idpers ?? r.IDPERS),
      label: `${r.prenom ?? r.PRENOM ?? ''} ${r.nom ?? r.NOM ?? ''}`.trim()
    }));
  } catch { return []; }
}


async function fetchStructsLike(q) {
  const term = (q ?? '').trim();
  try {
    const rows = await window.core.api('/api/structures/find?q=' + encodeURIComponent(term));
    return (rows || []).map(r => ({
      id: Number(r.id ?? r.ID),
      label: String(r.label ?? r.LABEL ?? r.id ?? r.ID)
    }));
  } catch { return []; }
}

// Ferme toutes les listes de pickers (sauf éventuellement une)
function hideAllPickerLists(except = null) {
  document.querySelectorAll('.picker-portal').forEach(el => {
    if (el !== except) el.style.display = 'none';
  });
}

/**
 * Petit picker générique (single|multi) avec suggestions.
 * Eléments attendus du fetcher: [{id, label}] (peut contenir {nom/prenom} -> label ajusté plus bas)
 */
function attachPicker(input, { mode = 'single', fetcher, toItem = (row)=>row, minChars = 2, chipSingle = false, onPick = null }) {
  if (!input || input._pickerInstalled) return;

  const ensureMounted = (cb, tries = 20) => {
    if (input.parentNode) return cb();
    if (tries <= 0) return;
    requestAnimationFrame(() => ensureMounted(cb, tries - 1));
  };

  ensureMounted(() => {
    if (input._pickerInstalled) return;
    input._pickerInstalled = true;
    input.autocomplete = 'off';

    // wrapper local (pour les chips) — pas de dropdown dedans
    const wrap = document.createElement('div');
    wrap.style.position = 'relative';
    wrap.style.display = 'inline-block';
    wrap.style.minWidth = input.style.minWidth || '200px';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    const chips = document.createElement('div');
    if (mode === 'multi'|| chipSingle)  {
      chips.style.display = 'flex';
      chips.style.flexWrap = 'wrap';
      chips.style.gap = '6px';
      chips.style.marginBottom = '4px';
      wrap.insertBefore(chips, input);
    }
    let clearBtn = null;
    if (mode === 'single' && !chipSingle) {
      clearBtn = document.createElement('button');
      clearBtn.type = 'button';
      clearBtn.textContent = '×';
      Object.assign(clearBtn.style, {
        position: 'absolute',
        right: '8px',
        top: '50%',
        transform: 'translateY(-50%)',
        border: 'none',
        background: 'transparent',
        color: '#9ca3af',
        fontSize: '18px',
        lineHeight: '1',
        padding: '0',
        cursor: 'pointer',
        display: 'none'
      });
      clearBtn.onclick = (ev) => {
        ev.stopPropagation();
        input.value = '';
        sel.splice(0, sel.length);
        hideList();
        updateClear();
        // rouvre une liste immédiate si minChars=0 (ex: structures)
        if (typeof openIfNeeded === 'function') openIfNeeded();
        input.focus();
      };
      wrap.appendChild(clearBtn);
    }
    
    const updateClear = () => {
      if (!clearBtn) return;
      clearBtn.style.display = (input.value || (sel && sel[0])) ? 'block' : 'none';
    };

    // --- DROPDOWN en portal (attaché au <body>)
    const list = document.createElement('div');
    list.className = 'picker-portal';
    Object.assign(list.style, {
      position: 'fixed',
      left: '0px',
      top: '0px',
      width: '200px',
      maxHeight: '240px',
      overflowY: 'auto',
      zIndex: '999999',
      display: 'none',
      background: '#0f172a',
      border: '1px solid #1f2937',
      borderRadius: '8px',
      padding: '4px 0',
      boxShadow: '0 8px 24px rgba(0,0,0,.35)'
      
      
    });
    
    const getPortalHost = () => {
      const d = input.closest('dialog');
      return (d && d.open) ? d : document.body;
    };
    const inDialog     = !!input.closest('dialog[open]');
    list.style.position = inDialog ? 'absolute' : 'fixed';
    getPortalHost().appendChild(list);

    let active = -1; // index dans list.children
    const HILITE_BG = '#2563eb';    // bleu bien visible
    const HILITE_TX = '#ffffff';    // texte blanc
    const HOVER_BG  = '#111827';    // hover souris (foncé)
    list.style.zIndex = '2147483646';

    const setActive = (i) => {
      const n = list.children.length;
      if (!n) { active = -1; return; }
      i = Math.max(0, Math.min(i, n - 1));
      if (active >= 0 && list.children[active]) {
        list.children[active].style.background = 'transparent';
        list.children[active].style.color = '';
      }
      active = i;
      const el = list.children[active];
      if (el) {
        el.style.background = HILITE_BG;
        el.style.color = HILITE_TX;
        el.scrollIntoView({ block: 'nearest' });
      }
    };

    const clearActive = () => {
      if (active >= 0 && list.children[active]) {
        list.children[active].style.background = 'transparent';
        list.children[active].style.color = '';
      }
      active = -1;
    };



    // nettoyage sur unload
    window.addEventListener('unload', () => list.remove());

    const sel = []; // [{id,label}]
    const redrawChips = () => {
      chips.innerHTML = '';
      // On veut des chips pour le multi ET pour le single si chipSingle
      if (!(mode === 'multi' || chipSingle)) return;

      const items = (mode === 'multi') ? sel : (sel[0] ? [sel[0]] : []);
      items.forEach((it, idx) => {
        const b = document.createElement('span');
        b.textContent = it.label;
        Object.assign(b.style, {
          display: 'inline-flex', alignItems: 'center', gap: '6px',
          padding: '2px 8px', border: '1px solid #1f2937',
          borderRadius: '999px', fontSize: '12px'
        });

        const x = document.createElement('button');
        x.type = 'button'; x.textContent = '×';
        Object.assign(x.style, {
          border:'none', background:'transparent', cursor:'pointer', color:'inherit'
        });

        x.onclick = (ev) => {
          ev.stopPropagation();
          if (mode === 'multi') {
            sel.splice(idx, 1);
          } else {
            sel.splice(0, sel.length);   // single + chipSingle → retire l’unique sélection
          }
          // vide le champ visuel aussi
          input.value = '';
          redrawChips();
          updateClear();
        };

        b.appendChild(x);
        chips.appendChild(b);
      });
    };

    const choose = (item) => {
      if (mode === 'multi') {
        if (!sel.find(s => s.id === item.id)) {
          sel.push(item);
          redrawChips();
        }
        input.value = '';
      } else {
        sel.splice(0, sel.length, item);
        if (chipSingle) {
          input.value = '';
          redrawChips();
        } else {
          input.value = item.label;
        }
      }
      hideList();
      updateClear();
      if (typeof onPick === 'function') {
        try { onPick(item); } catch {}
      }
    };


    const positionList = () => {
      const r = input.getBoundingClientRect();
      if (inDialog) {
        const host = portalHost.getBoundingClientRect();
        list.style.left  = `${Math.round(r.left - host.left)}px`;
        list.style.top   = `${Math.round(r.bottom - host.top + 2)}px`;
        list.style.width = `${Math.round(r.width)}px`;
      } else {
        list.style.left  = `${Math.round(r.left)}px`;
        list.style.top   = `${Math.round(r.bottom + 2)}px`;
        list.style.width = `${Math.round(r.width)}px`;
      }
    };


    const showList = () => {
      const host = getPortalHost();
      if (list.parentNode !== host) host.appendChild(list);
      hideAllPickerLists(list);
      positionList();
      list.style.display = 'block';
      window.addEventListener('scroll', positionList, true);
      window.addEventListener('resize', positionList, true);
    };
    const hideList = () => {
      list.style.display = 'none';
      clearActive();
      window.removeEventListener('scroll', positionList, true);
      window.removeEventListener('resize', positionList, true);
    };

    let lastQ = '';
    let t = null;

    const renderList = (rows) => {
    list.innerHTML = '';
    clearActive(); // ← AJOUT

    (rows || []).slice(0, 25).forEach(r => {
      const it = toItem(r);
      const a = document.createElement('div');
      a.textContent = it.label || '';
      Object.assign(a.style, { padding:'8px 10px', cursor:'pointer' });

      const idx = list.children.length;
      a._item = it;
      a.onmouseenter = () => setActive(idx);
      a.onmouseleave = () => { if (active !== idx) { a.style.background = 'transparent'; a.style.color = ''; } };
      a.onmousedown = (ev) => {
        ev.preventDefault();    // évite de déplacer le focus
        ev.stopPropagation();
        choose(it);
      };
      // on neutralise le click qui suivra le mousedown
      a.onclick = (ev) => ev.preventDefault();
      list.appendChild(a);
    });
    if (list.children.length) showList(); else hideList();
  };


    const runSearch = async (q) => {
      lastQ = q;
      let rows = [];
      try { rows = await fetcher(q); } catch { rows = []; }
      if (q !== lastQ) return;
      renderList(rows);
    };

    // saisie + debounce
    input.addEventListener('input', () => {
      const q = input.value.trim();
      updateClear();

      clearTimeout(t);
      if (q.length < minChars) { hideList(); return; }
      t = setTimeout(() => runSearch(q), 200);
    });

    // ouverture au focus / clic
    const openIfNeeded = () => {
      const q = input.value.trim();
      if (q.length >= minChars) runSearch(q);
      else if (minChars === 0)  runSearch('');
    };
    input.addEventListener('focus', (e) => {
      e.stopPropagation();
      hideAllPickerLists(list);
        if (minChars === 0) runSearch(''); else openIfNeeded();
;
    });
    input.addEventListener('click', (e) => {
      e.stopPropagation();
      hideAllPickerLists(list);
        if (minChars === 0) runSearch(''); else openIfNeeded();
    });

    // fermeture si clic ailleurs
    document.addEventListener('click', (e) => {
      if (e.target !== input && !list.contains(e.target)) hideList();
    });
    document.addEventListener('focusin', (e) => {                 // ← NEW
      if (e.target !== input && !list.contains(e.target)) hideList();
    });
    input.addEventListener('keydown', (e) => {
    const open = list.style.display !== 'none' && list.children.length > 0;

    if (e.key === 'ArrowDown') {
      if (!open) { openIfNeeded(); }
      if (list.children.length) {
        setActive(active < 0 ? 0 : Math.min(active + 1, list.children.length - 1));
      }
      e.preventDefault();
    } else if (e.key === 'ArrowUp') {
      if (open && list.children.length) {
        setActive(active <= 0 ? 0 : active - 1);
      }
      e.preventDefault();
    } else if (e.key === 'Enter') {
      if (open && active >= 0 && list.children[active]?._item) {
        choose(list.children[active]._item);
        e.preventDefault();
      }
    } else if (e.key === 'Escape') {
      hideList();
      e.preventDefault();
    }
  });


    // expose pour la collecte de valeur
  input._getValue = () => (mode === 'multi' ? sel.map(s => s.id) : (sel[0]?.id ?? null));
  updateClear();
  });
}





function localThemesLike(q) {
  // Utilise l’arbre déjà chargé (bouton "Charger l’arbre")
  const flat = Array.isArray(state.flat) ? state.flat : [];
  const term = String(q || '').trim().toLowerCase();
  let src = flat;
  if (term) {
    src = flat.filter(t =>
      String(t.id).includes(term) ||
      (t.label || '').toLowerCase().includes(term)
    );
  }
  // on renvoie une promesse pour rester compatible avec attachPicker
  return Promise.resolve(
    src.slice(0, 80).map(t => ({ id: t.id, label: `${t.label} (id:${t.id})` }))
  );
}
// Charge une fois l'arbre et le met à plat dans state.flat si absent
async function ensureThemesFlatLoaded() {
  if (Array.isArray(state.flat) && state.flat.length) return;
  try {
    const rows = await api('/api/themes/tree'); // [{id,label,parent_id,lvl,...}]
    state.flat = rows || [];
  } catch {
    state.flat = state.flat || []; // au pire un tableau vide
  }
}

// Filtre local: par libellé (contient) ou par id (si q est numérique)
async function fetchThemesSmart(q) {
  await ensureThemesFlatLoaded();
  const all = Array.isArray(state.flat) ? state.flat : [];
  const s = String(q || '').trim().toLowerCase();
  const isNum = /^\d+$/.test(s);

  let out = all;
  if (s) {
    out = all.filter(t => {
      const byLabel = (t.label || '').toLowerCase().includes(s);
      const byId    = isNum && String(t.id).includes(s);
      return byLabel || byId;
    });
  }

  // dédoublonne + limite
  const seen = new Set();
  const list = [];
  for (const t of out) {
    if (!seen.has(t.id)) {
      seen.add(t.id);
      list.push({ id: t.id, label: t.label });
      if (list.length >= 50) break;
    }
  }

  // si rien trouvé mais on a tapé juste un id, on propose quand même l'id brut
  if (!list.length && isNum) {
    list.push({ id: Number(s), label: `#${s}` });
  }
  return list;
}

})();
