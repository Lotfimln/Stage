const API = "http://127.0.0.1:5000";

async function login() {
  const user = document.getElementById('username').value.trim();
  const pass = document.getElementById('password').value;

  const res = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: user, password: pass })
  });

  if (!res.ok) {
    const msg = await res.text();
    alert('Échec connexion: ' + msg);
    return;
  }
  const data = await res.json();
  window._token = data.token;
  alert('Connexion OK');
}


async function countByTheme() {
  const r = await fetch(`${API}/api/positionnements/count_by_theme`);
  return r.json();
}

async function searchPositionnements(filters) {
  const r = await fetch(`${API}/api/positionnements/search`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(filters || {})
  });
  return r.json();
}
