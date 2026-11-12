import assert from 'node:assert/strict';
import test from 'node:test';

class Element extends EventTarget {
  hidden = true;
  dataset = {};
  textContent = '';
}
const selectors = ['label', 'icon', 'detail', 'dismiss'];
const parts = Object.fromEntries(selectors.map(name => [`[data-activity-${name}]`, new Element()]));
const region = new Element();
region.querySelector = selector => parts[selector];
globalThis.document = { querySelector: selector => selector === '[data-activity-indicator]' ? region : parts[selector] };
globalThis.window = new EventTarget();
const { beginActivity, initActivityIndicator } = await import('../static/js/core/activity.js');
initActivityIndicator();

test('shows contextual pending, success, error and concurrent actions', () => {
  const lookup = beginActivity('Buscando CEP', 'location_on');
  assert.equal(region.hidden, false);
  assert.equal(region.dataset.state, 'pending');
  assert.equal(parts['[data-activity-label]'].textContent, 'Buscando CEP');
  assert.equal(parts['[data-activity-dismiss]'].hidden, true);
  const save = beginActivity('Salvando endereço');
  assert.equal(parts['[data-activity-detail]'].textContent, '2 ações em andamento');
  lookup.success('CEP encontrado');
  assert.equal(region.dataset.state, 'pending');
  assert.equal(parts['[data-activity-label]'].textContent, 'Salvando endereço');
  save.success('Endereço salvo');
  assert.equal(region.dataset.state, 'success');
  save.cancel();
  assert.equal(region.hidden, false);
  const failure = beginActivity('Nova consulta');
  failure.error('Sem conexão');
  assert.equal(region.dataset.state, 'error');
  assert.equal(parts['[data-activity-icon]'].textContent, 'error_outline');
  parts['[data-activity-dismiss]'].dispatchEvent(new Event('click'));
  assert.equal(region.hidden, true);
});

test('cancellation and browser restoration clear pending state', () => {
  const canceled = beginActivity('Consulta cancelada');
  canceled.cancel();
  assert.equal(region.hidden, true);
  canceled.error('Resposta antiga');
  assert.equal(region.hidden, true);
  const old = beginActivity('Salvando');
  window.dispatchEvent(new Event('pageshow'));
  assert.equal(region.hidden, true);
  old.success('Resposta antiga');
  assert.equal(region.hidden, true);
  const next = beginActivity('Nova ação');
  assert.equal(parts['[data-activity-detail]'].textContent, 'Em andamento');
  next.cancel();
});
