import assert from 'node:assert/strict';
import test from 'node:test';

globalThis.document = { querySelector: () => null };
const { formatPostalCode, initPostalCodeLookup } = await import('../static/js/modules/addresses.js');

class Field extends EventTarget {
  value = '';
  disabled = false;
  dataset = {};
  attributes = new Map();
  selectionStart = 0;
  setAttribute(key, value) { this.attributes.set(key, value); }
  removeAttribute(key) { this.attributes.delete(key); }
  hasAttribute(key) { return this.attributes.has(key); }
  setSelectionRange(start) { this.selectionStart = start; }
}

function fixture(fetchAddress) {
  const elements = Object.fromEntries(['postal_code', 'street', 'district', 'city', 'state', 'number', 'complement'].map(name => [name, new Field()]));
  const button = new Field();
  const status = new Field();
  const form = { elements, querySelector: selector => selector === '.address-postal-search' ? button : status };
  initPostalCodeLookup(form, fetchAddress);
  elements.postal_code.value = '01001-000';
  return { elements, button, status };
}
const flush = () => new Promise(resolve => setImmediate(resolve));
const address = { logradouro: 'Praça da Sé', bairro: 'Sé', localidade: 'São Paulo', uf: 'SP', complemento: 'lado ímpar' };
const response = data => ({ ok: true, json: async () => data });

test('masks typing, pasted punctuation and excess digits', () => {
  assert.equal(formatPostalCode('14409360'), '14409-360');
  assert.equal(formatPostalCode('01.001-000999'), '01001-000');
  assert.equal(formatPostalCode('abc14409'), '14409');
});

test('fills address and preserves number and complement', async () => {
  const f = fixture(async (url, options) => {
    assert.equal(url, 'https://viacep.com.br/ws/01001000/json/');
    assert.equal(options.credentials, 'omit');
    return response(address);
  });
  f.elements.number.value = '123';
  f.elements.complement.value = 'Apto 2';
  f.button.dispatchEvent(new Event('click'));
  await flush();
  assert.equal(f.elements.street.value, address.logradouro);
  assert.equal(f.elements.city.value, address.localidade);
  assert.equal(f.elements.state.value, 'SP');
  assert.equal(f.elements.number.value, '123');
  assert.equal(f.elements.complement.value, 'Apto 2');
  assert.equal(f.status.dataset.state, 'success');
});

test('does not request incomplete postal codes', async () => {
  let requests = 0;
  const f = fixture(async () => { requests++; return response(address); });
  f.elements.postal_code.value = '14409';
  f.button.dispatchEvent(new Event('click'));
  await flush();
  assert.equal(requests, 0);
  assert.equal(f.status.dataset.state, 'error');
});

test('handles nonexistent codes and network failures without clearing manual data', async () => {
  for (const fetchAddress of [async () => response({ erro: true }), async () => { throw new Error('offline'); }]) {
    const f = fixture(fetchAddress);
    f.elements.street.value = 'Rua digitada';
    f.button.dispatchEvent(new Event('click'));
    await flush();
    assert.equal(f.elements.street.value, 'Rua digitada');
    assert.equal(f.status.dataset.state, 'error');
    assert.equal(f.button.disabled, false);
  }
});

test('preserves corrections made while a lookup is pending', async () => {
  let resolve;
  const f = fixture(() => new Promise(r => { resolve = r; }));
  f.button.dispatchEvent(new Event('click'));
  f.elements.street.value = 'Minha correção';
  f.elements.street.dispatchEvent(new Event('input'));
  resolve(response(address));
  await flush();
  assert.equal(f.elements.street.value, 'Minha correção');
  assert.equal(f.elements.city.value, address.localidade);
});

test('ignores responses for a postal code that has changed', async () => {
  let resolve;
  const f = fixture(() => new Promise(r => { resolve = r; }));
  f.button.dispatchEvent(new Event('click'));
  f.elements.postal_code.value = '14409';
  f.elements.postal_code.dispatchEvent(new Event('input'));
  resolve(response(address));
  await flush();
  assert.equal(f.elements.city.value, '');
  assert.equal(f.status.textContent, '');
});
