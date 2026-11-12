export function initPwa() {
  if (!window.isSecureContext) return;
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/service-worker.js', { scope: '/', updateViaCache: 'none' })
      .catch(error => console.warn('Não foi possível iniciar o aplicativo instalável.', error));
  }

  const panel = document.querySelector('[data-pwa-install]');
  if (!panel) return;
  const button = panel.querySelector('[data-pwa-install-button]');
  const dialog = document.querySelector('[data-pwa-help]');
  const standalone = window.matchMedia('(display-mode: standalone)');
  const installed = () => standalone.matches || navigator.standalone === true;
  const dismissed = () => { try { return sessionStorage.getItem('pwa-install-dismissed') === '1'; } catch { return false; } };
  const iosSafari = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  let prompt;
  const show = () => { panel.hidden = installed() || dismissed() || !(prompt || iosSafari); };

  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    prompt = event;
    show();
  });
  window.addEventListener('appinstalled', () => { prompt = null; panel.hidden = true; });
  standalone.addEventListener('change', show);
  panel.querySelector('[data-pwa-dismiss]').addEventListener('click', () => {
    panel.hidden = true;
    try { sessionStorage.setItem('pwa-install-dismissed', '1'); } catch { /* Storage may be unavailable. */ }
  });
  button.addEventListener('click', async () => {
    if (!prompt) { if (iosSafari) dialog?.showModal(); return; }
    button.disabled = true;
    try {
      await prompt.prompt();
      await prompt.userChoice;
    } catch { /* A browser may withdraw an installation prompt. */ }
    finally { prompt = null; button.disabled = false; panel.hidden = true; }
  });
  dialog?.querySelector('[data-pwa-help-close]').addEventListener('click', () => dialog.close());
  show();
}
