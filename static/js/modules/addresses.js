import { beginActivity } from '../core/activity.js';

export function formatPostalCode(value) {
  const digits = value.replace(/\D/g, '').slice(0, 8);
  return digits.length > 5 ? `${digits.slice(0, 5)}-${digits.slice(5)}` : digits;
}

export function initPostalCodeLookup(form, fetchAddress = fetch) {
  const postalCode = form.elements.postal_code;
  const button = form.querySelector('.address-postal-search');
  const status = form.querySelector('#postal-code-status');
  const fields = { street: 'logradouro', district: 'bairro', city: 'localidade', state: 'uf' };
  let controller;
  let debounce;
  let revision = 0;
  let completedCode = '';
  let activity;

  function message(text, state = '') {
    status.textContent = text;
    status.dataset.state = state;
    status.hidden = !text;
  }

  function cancel() {
    revision++;
    clearTimeout(debounce);
    controller?.abort();
    activity?.cancel();
    button.disabled = false;
    postalCode.removeAttribute('aria-busy');
  }

  async function lookup(force = false) {
    const code = postalCode.value.replace(/\D/g, '');
    if (code.length !== 8) {
      message('Informe os 8 dígitos do CEP.', 'error');
      return;
    }
    if (!force && code === completedCode) return;
    cancel();
    const current = revision;
    controller = new AbortController();
    const activeController = controller;
    const snapshot = Object.fromEntries(Object.keys(fields).map(name => [name, form.elements[name].value]));
    const edited = new Set();
    const listeners = Object.keys(fields).map(name => {
      const listener = () => edited.add(name);
      form.elements[name].addEventListener('input', listener);
      return [name, listener];
    });
    const timeout = setTimeout(() => activeController.abort(), 8000);
    button.disabled = true;
    postalCode.setAttribute('aria-busy', 'true');
    message('Buscando endereço...');
    activity = beginActivity('Buscando endereço pelo CEP', 'location_on');
    const currentActivity = activity;
    try {
      const response = await fetchAddress(`https://viacep.com.br/ws/${code}/json/`, {
        signal: activeController.signal, credentials: 'omit', headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error('Lookup failed');
      const data = await response.json();
      if (current !== revision || postalCode.value.replace(/\D/g, '') !== code) return;
      if (data.erro) {
        currentActivity.error('CEP não encontrado');
        message('CEP não encontrado. Confira o CEP ou preencha o endereço manualmente.', 'error');
        return;
      }
      if (typeof data.localidade !== 'string' || typeof data.uf !== 'string') throw new Error('Invalid address');
      for (const [name, key] of Object.entries(fields)) {
        const input = form.elements[name];
        if (!edited.has(name) && input.value === snapshot[name]) {
          input.value = typeof data[key] === 'string' ? data[key] : '';
        }
      }
      completedCode = code;
      currentActivity.success('Endereço encontrado');
      message('Endereço encontrado. Confira os dados e informe o número.', 'success');
    } catch {
      if (current === revision) {
        currentActivity.error('Não foi possível consultar o CEP');
        message('Não foi possível consultar o CEP. Tente novamente ou preencha o endereço manualmente.', 'error');
      }
    } finally {
      currentActivity.cancel();
      clearTimeout(timeout);
      for (const [name, listener] of listeners) form.elements[name].removeEventListener('input', listener);
      if (current === revision) {
        button.disabled = false;
        postalCode.removeAttribute('aria-busy');
      }
    }
  }

  postalCode.value = formatPostalCode(postalCode.value);
  postalCode.addEventListener('input', () => {
    const position = postalCode.selectionStart;
    const digitsBeforeCaret = postalCode.value.slice(0, position).replace(/\D/g, '').length;
    postalCode.value = formatPostalCode(postalCode.value);
    const caret = Math.min(postalCode.value.length, digitsBeforeCaret + (digitsBeforeCaret > 5 ? 1 : 0));
    postalCode.setSelectionRange(caret, caret);
    cancel();
    completedCode = '';
    message('');
    if (postalCode.value.length === 9) debounce = setTimeout(() => lookup(), 350);
  });
  postalCode.addEventListener('blur', () => {
    clearTimeout(debounce);
    if (postalCode.value && !postalCode.hasAttribute('aria-busy')) lookup();
  });
  button.addEventListener('click', () => lookup(true));
}

const addressForm = document.querySelector('.address-form');
if (addressForm) initPostalCodeLookup(addressForm);
