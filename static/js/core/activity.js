const active = new Map();
let sequence = 0;
let hideTimer;
let initialized = false;

function render(label, state, icon) {
  const region = document.querySelector('[data-activity-indicator]');
  if (!region) return;
  clearTimeout(hideTimer);
  region.hidden = false;
  region.dataset.state = state;
  region.querySelector('[data-activity-label]').textContent = label;
  region.querySelector('[data-activity-icon]').textContent = icon;
  region.querySelector('[data-activity-detail]').textContent = state === 'pending'
    ? (active.size > 1 ? `${active.size} ações em andamento` : 'Em andamento')
    : (state === 'success' ? 'Concluído' : 'Tente novamente');
  region.querySelector('[data-activity-dismiss]').hidden = state === 'pending';
  if (state !== 'pending') hideTimer = setTimeout(() => { region.hidden = true; }, state === 'success' ? 2500 : 6000);
}

function renderPending() {
  const current = [...active.values()].at(-1);
  if (current) render(current.label, 'pending', current.icon);
}

export function beginActivity(label, icon = 'auto_awesome') {
  const id = ++sequence;
  active.set(id, { label, icon });
  renderPending();
  let finished = false;
  function finish(state, message) {
    if (finished || !active.has(id)) return;
    finished = true;
    active.delete(id);
    if (active.size) renderPending();
    else if (state) render(message, state, state === 'success' ? 'check' : 'error_outline');
    else {
      const region = document.querySelector('[data-activity-indicator]');
      if (region) region.hidden = true;
      clearTimeout(hideTimer);
    }
  }
  return {
    success: message => finish('success', message),
    error: message => finish('error', message),
    cancel: () => finish(),
  };
}

export function initActivityIndicator() {
  if (initialized) return;
  initialized = true;
  document.querySelector('[data-activity-dismiss]')?.addEventListener('click', () => {
    document.querySelector('[data-activity-indicator]').hidden = true;
    clearTimeout(hideTimer);
  });
  window.addEventListener('pageshow', () => {
    active.clear();
    clearTimeout(hideTimer);
    const region = document.querySelector('[data-activity-indicator]');
    if (region) region.hidden = true;
  });
}
