import { formatBRL } from "../core/currency.js";
import { toNumber } from "../core/dom.js";

export function initProductCustomizer() {
  document.querySelectorAll("[data-product-customizer]").forEach((form) => {
    const total = form.querySelector("[data-product-total]");
    const quantity = form.querySelector("input[name='quantity']");
    if (!total || !quantity) return;

    const update = () => {
      const base = toNumber(total.dataset.basePrice);
      const addons = [...form.querySelectorAll("[data-addon-price]:checked")].reduce(
        (sum, addon) => sum + toNumber(addon.dataset.addonPrice),
        0,
      );
      total.textContent = formatBRL((base + addons) * toNumber(quantity.value || 1));
    };

    form.addEventListener("change", update);
    form.addEventListener("input", update);
    update();
  });
}
