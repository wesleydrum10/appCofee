import { formatBRL } from '../core/currency.js';
import { beginActivity } from '../core/activity.js';

const page = document.querySelector('[data-cart-page]');
if (page) {
  let busy = false;
  const feedback = page.querySelector('[data-cart-feedback]');

  function render(cart) {
    for (const row of page.querySelectorAll('[data-cart-item]')) {
      const item = cart.items.find(item => String(item.id) === row.dataset.cartItem);
      if (!item) { row.remove(); continue; }
      row.querySelector('[name=quantity]').value = item.quantity;
      row.querySelector('[data-item-subtotal]').textContent = formatBRL(Number(item.subtotal));
    }
    document.querySelectorAll('[data-cart-count]').forEach(badge => { badge.textContent = cart.count; });
    for (const key of ['subtotal', 'discount', 'total']) {
      page.querySelector(`[data-cart-${key}]`).textContent = formatBRL(Number(cart.totals[key]));
    }
    const coupon = page.querySelector('[data-cart-coupon-message]');
    coupon.textContent = cart.totals.coupon_message;
    coupon.hidden = !cart.totals.coupon_message;
    if (cart.count === 0) location.reload();
  }

  async function update(form, submitter) {
    if (busy || !form.reportValidity()) return;
    busy = true;
    const data = new FormData(form);
    if (submitter?.name) data.set(submitter.name, submitter.value);
    const activity = beginActivity('Atualizando sacola...', 'shopping_bag');
    const controls = [...page.querySelectorAll('button, input')];
    const states = controls.map(control => control.disabled);
    controls.forEach(control => { control.disabled = true; });
    page.setAttribute('aria-busy', 'true');
    feedback.hidden = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(form.action, {method: 'POST', body: data, headers: {Accept:'application/json'}, signal: controller.signal});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Não foi possível atualizar a sacola. Atualize a página e tente novamente.');
      const cart = await response.json();
      if (cart.items && cart.totals) render(cart);
      feedback.textContent = cart.message;
      feedback.dataset.error = String(!cart.ok);
      feedback.hidden = false;
      if (!response.ok || !cart.ok) { activity.error(cart.message); return; }
      activity.success('Sacola atualizada.');
    } catch (error) {
      feedback.textContent = error.name === 'AbortError' ? 'A atualização demorou mais que o esperado. Atualize a página para conferir a quantidade antes de tentar novamente.' : error.message;
      feedback.dataset.error = 'true';
      feedback.hidden = false;
      activity.error(feedback.textContent);
    } finally {
      clearTimeout(timeout);
      controls.forEach((control, index) => { control.disabled = states[index]; });
      page.removeAttribute('aria-busy');
      busy = false;
    }
  }

  page.querySelectorAll('[data-cart-quantity-form]').forEach(form => {
    form.addEventListener('submit', event => { event.preventDefault(); update(form, event.submitter); });
    form.querySelector('[name=quantity]').addEventListener('change', () => update(form));
    form.querySelector('[name=quantity]').addEventListener('keydown', event => {
      if (event.key === 'Enter') { event.preventDefault(); update(form); }
    });
  });
  page.querySelector('[data-cart-checkout]')?.addEventListener('click', event => { if (busy) event.preventDefault(); });
}
