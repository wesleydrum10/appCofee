import { setActionPending, setActionSuccess, setActionError } from '../core/action-state.js';

export function initCartAdd() {
  const forms = [...document.querySelectorAll('[data-cart-add]')];
  if (!forms.length) return;
  let queue = Promise.resolve();
  const pending = new WeakSet();

  function render(summary) {
    document.querySelectorAll('[data-cart-count]').forEach(badge => { badge.textContent = summary.count; });
    document.querySelectorAll('[data-cart-product]').forEach(card => {
      const quantity = summary.product_quantities[card.dataset.cartProduct] || 0;
      card.dataset.inCart = String(quantity > 0);
      const state = card.querySelector('[data-product-cart-state]');
      if (!state) return;
      state.hidden = quantity === 0;
      state.querySelector('[data-product-cart-quantity]').textContent = quantity;
      state.querySelector('[data-product-cart-unit]').textContent = quantity === 1 ? 'unidade' : 'unidades';
    });
  }

  for (const form of forms) {
    form.addEventListener('submit', event => {
      event.preventDefault();
      if (pending.has(form)) return;
      const button = event.submitter || form.querySelector('button');
      const feedback = form.querySelector('[data-product-cart-feedback]');
      const data = new FormData(form);
      pending.add(form);
      feedback.hidden = true;
      setActionPending(button);
      queue = queue.then(async () => {
        try {
          const response = await fetch(form.action, {
            method: 'POST', body: data, credentials: 'same-origin',
            headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(15000),
          });
          if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) {
            throw new Error('Não foi possível adicionar. Atualize a página e confira sua sessão.');
          }
          const result = await response.json();
          if (!response.ok || !result.ok) throw new Error(result.message || 'Não foi possível adicionar este produto.');
          render(result);
          setActionSuccess(button);
        } catch (error) {
          feedback.textContent = error.name === 'TimeoutError' || error instanceof TypeError
            ? 'A conexão falhou. Atualize a página para conferir o carrinho antes de tentar novamente.'
            : error.message;
          feedback.hidden = false;
          setActionError(button);
        } finally {
          pending.delete(form);
        }
      });
    });
  }

  function refresh() {
    queue = queue.then(async () => {
      try {
        const response = await fetch(forms[0].dataset.cartSummaryUrl, { cache: 'no-store', credentials: 'same-origin', signal: AbortSignal.timeout(10000) });
        if (response.ok && response.headers.get('content-type')?.includes('application/json')) render(await response.json());
      } catch { /* Keep the last confirmed quantities until a new response arrives. */ }
    });
  }
  window.addEventListener('pageshow', event => { if (event.persisted) refresh(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
}
