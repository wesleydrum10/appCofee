import { formatBRL } from '../core/currency.js';

const cards = document.querySelector('[data-checkout-cards]');
if (cards) {
  const select = cards.querySelector('select');
  const updateCards = () => {
    const useCard = document.querySelector('input[name="payment_method"]:checked')?.value === 'CARD';
    cards.hidden = !useCard;
    if (select) { select.disabled = !useCard; select.required = useCard; }
  };
  document.querySelectorAll('input[name="payment_method"]').forEach(input => input.addEventListener('change', updateCards));
  updateCards();
}

const options = document.getElementById('checkout-delivery-options');
if (options) {
  const quotes = JSON.parse(options.textContent);
  document.querySelectorAll('input[name="address_id"]').forEach(input => {
    input.addEventListener('change', () => {
      const quote = quotes.find(option => String(option.id) === input.value);
      if (!quote) return;
      document.querySelectorAll('[data-address-heading]').forEach(heading => { heading.hidden = heading.dataset.addressHeading !== input.value; });
      document.querySelectorAll('[data-address-info]').forEach(info => { info.hidden = info.dataset.addressInfo !== input.value; });
      document.querySelector('[data-delivery-estimate]').textContent = `Previsão: ${quote.minutes} min`;
      document.querySelector('[data-delivery-message]').textContent = quote.message;
      document.querySelector('[data-delivery-fee]').textContent = formatBRL(Number(quote.fee));
      document.querySelector('[data-checkout-total]').textContent = formatBRL(Number(quote.total));
      document.querySelector('[data-confirm-total]').textContent = formatBRL(Number(quote.total));
      input.closest('details').open = false;
    });
  });
}
