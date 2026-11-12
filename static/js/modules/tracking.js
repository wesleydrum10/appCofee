const root = document.querySelector('[data-delivery-tracking]');
if (root) {
  const content = root.querySelector('[data-tracking-content]');
  const button = root.querySelector('[data-tracking-refresh]');
  const feedback = root.querySelector('[data-tracking-feedback]');
  let timer;
  let loading = false;
  const terminal = () => content.querySelector('[data-terminal]')?.dataset.terminal === 'true';
  const schedule = () => {
    clearTimeout(timer);
    if (!terminal()) timer = setTimeout(refresh, 15000);
  };
  async function refresh() {
    if (loading) return;
    if (document.hidden) { schedule(); return; }
    loading = true;
    button.disabled = true;
    try {
      const response = await fetch(root.dataset.statusUrl, {
        credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000),
        headers: { Accept: 'application/json' },
      });
      if (!response.ok || response.redirected || !response.headers.get('content-type')?.includes('application/json')) {
        throw new Error('Não foi possível consultar a entrega. Verifique sua conexão e se continua conectado à conta.');
      }
      const data = await response.json();
      content.innerHTML = data.html;
      feedback.textContent = data.terminal ? 'Acompanhamento encerrado.' : `Atualizado às ${new Date().toLocaleTimeString('pt-BR')}. Nova consulta em 15 segundos.`;
    } catch (error) {
      feedback.textContent = 'Não foi possível atualizar. Verifique sua conexão e seu login. Tentaremos novamente; você também pode usar Atualizar agora.';
    } finally {
      loading = false;
      button.disabled = false;
      schedule();
    }
  }
  button.addEventListener('click', refresh);
  document.addEventListener('visibilitychange', () => { if (!document.hidden && !terminal()) refresh(); });
  window.addEventListener('pagehide', () => clearTimeout(timer));
  schedule();
}
