const form = document.querySelector('[data-payment-form]');
if (form) {
  const panel = document.querySelector('[data-payment-panel]');
  const result = panel.querySelector('[data-payment-result]');
  const button = form.querySelector('button');
  const label = button.querySelector('[data-payment-button-label]');
  const steps = [...panel.querySelectorAll('[data-payment-step]')];
  let running = false;
  let uncertain = false;
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

  function stage(index, message) {
    steps.forEach((step, i) => {
      step.classList.toggle('is-complete', i < index);
      if (i === index) step.setAttribute('aria-current', 'step');
      else step.removeAttribute('aria-current');
    });
    result.textContent = message;
  }

  async function simulate(event) {
    event?.preventDefault();
    if (running) return;
    running = true;
    const data = new FormData(form);
    button.disabled = true;
    label.textContent = 'Processando pagamento...';
    panel.setAttribute('aria-busy', 'true');
    panel.dataset.status = 'PROCESSING';
    panel.querySelector('.payment-steps').hidden = false;
    const controller = new AbortController();
    let timeout;
    try {
      stage(0, 'Enviando pagamento ao ambiente de teste...');
      await wait(800);
      stage(1, 'Validando a transação e consultando a instituição...');
      await wait(900);
      stage(2, 'Aguardando a resposta do pagamento...');
      timeout = setTimeout(() => controller.abort(), 15000);
      const response = await fetch(form.action, {method: 'POST', body: data, headers: {Accept: 'application/json'}, signal: controller.signal});
      if (response.redirected) throw new Error('Sua sessão expirou. Entre novamente para consultar o pagamento.');
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Não foi possível consultar o pagamento. Atualize a página e tente novamente.');
      const payment = await response.json();
      if (payment.simulation_enabled === false) form.hidden = true;
      if (!response.ok || !payment.ok) throw new Error(payment.message || 'Não foi possível consultar o pagamento.');
      await wait(600);
      uncertain = false;
      panel.dataset.status = payment.status;
      const badge = document.querySelector('[data-payment-status]');
      badge.dataset.status = payment.status;
      badge.textContent = payment.status_label || {APPROVED: 'Aprovado', PENDING: 'Pendente', DECLINED: 'Recusado'}[payment.status];
      const timeline = document.querySelector('[data-order-timeline]');
      const entry = payment.timeline_entry;
      if (timeline && entry && ![...timeline.children].some(item => item.dataset.historyId === String(entry.id))) {
        const item = document.createElement('li');
        item.className = 'order-timeline-entry';
        item.dataset.status = entry.status;
        item.dataset.historyId = entry.id;
        const flag = document.createElement('span');
        flag.className = 'status-badge';
        flag.dataset.status = entry.status;
        flag.textContent = entry.label;
        const description = document.createElement('p');
        description.className = 'text-dust';
        description.textContent = `${entry.date} ${entry.note}`;
        item.append(flag, description);
        timeline.append(item);
      }
      steps.forEach(step => {step.classList.add('is-complete'); step.removeAttribute('aria-current');});
      result.textContent = payment.message;
      if (payment.status === 'APPROVED') {
        form.hidden = true;
        setTimeout(() => location.assign(payment.detail_url), 1600);
      } else {
        form.elements.idempotency_key.value = crypto.randomUUID();
        form.elements.retry.value = '1';
        label.textContent = payment.status === 'DECLINED' ? 'Tentar novamente' : 'Consultar pagamento';
      }
    } catch (error) {
      uncertain = true;
      panel.dataset.status = 'ERROR';
      result.textContent = error.name === 'AbortError' ? 'A consulta demorou mais que o esperado. Tente consultar novamente.' : error.message;
      label.textContent = 'Consultar novamente';
    } finally {
      clearTimeout(timeout);
      panel.removeAttribute('aria-busy');
      button.disabled = false;
      running = false;
    }
  }

  // Capture before the shared POST handler so it does not replace this feedback.
  form.addEventListener('submit', simulate);
  if (form.hasAttribute('data-auto-simulate')) simulate();
  window.addEventListener('pageshow', event => {
    if (event.persisted && !running && !uncertain) location.reload();
  });
}
