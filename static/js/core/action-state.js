import { beginActivity } from "./activity.js";

const originals = new Map();
let initialized = false;

function labelFor(element, state) {
  return element.dataset[`${state}Label`] || element.textContent;
}

export function setActionPending(element) {
  if (!element || originals.has(element)) return;
  const original = {
    disabled: element.disabled, minWidth: element.style.minWidth,
    label: element.querySelector('[data-action-label]'),
    nodes: [...element.childNodes],
    activity: beginActivity(labelFor(element, "pending"), element.dataset.actionIcon || 'auto_awesome'),
  };
  original.labelNodes = original.label ? [...original.label.childNodes] : [];
  originals.set(element, original);
  element.style.minWidth = `${element.getBoundingClientRect().width}px`;
  if (original.label) original.label.textContent = labelFor(element, "pending");
  else {
    const icon = element.querySelector('.material-symbols-outlined');
    const iconOnly = icon && original.nodes.every(node => node === icon || !node.textContent.trim());
    if (!iconOnly) {
      const label = document.createElement('span');
      label.textContent = labelFor(element, "pending");
      element.replaceChildren(...(icon ? [icon] : []), label);
    }
  }
  element.disabled = true;
  element.dataset.actionState = "pending";
  element.setAttribute("aria-busy", "true");
}

export function setActionSuccess(element) {
  if (!element || !originals.has(element)) return;
  originals.get(element).activity.success(element.dataset.successLabel || 'Ação concluída.');
  resetActionState(element);
}

export function setActionError(element) {
  if (!element || !originals.has(element)) return;
  originals.get(element).activity.error(element.dataset.errorLabel || 'Não foi possível concluir a ação.');
  resetActionState(element);
}

export function resetActionState(element) {
  const original = originals.get(element);
  if (!original) return;
  original.activity.cancel();
  if (original.label) original.label.replaceChildren(...original.labelNodes);
  else element.replaceChildren(...original.nodes);
  element.removeAttribute("aria-busy");
  element.disabled = original.disabled;
  element.style.minWidth = original.minWidth;
  element.dataset.actionState = "";
  originals.delete(element);
}

export function initActionStates() {
  if (initialized) return;
  initialized = true;
  document.addEventListener("submit", (event) => {
    if (event.defaultPrevented || event.target.method.toLowerCase() !== 'post') return;
    const button = event.submitter || event.target.querySelector('button[type="submit"], button:not([type])');
    if (!button) return;
    if (originals.has(button)) { event.preventDefault(); return; }
    button.setAttribute('data-action-state', '');
    if (!button.dataset.pendingLabel) button.dataset.pendingLabel = 'Salvando...';
    setActionPending(button);
  });
  window.addEventListener('pageshow', () => {
    for (const element of originals.keys()) resetActionState(element);
  });
}
