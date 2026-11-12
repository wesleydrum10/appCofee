export function showToast(message, type = "info") {
  const region = document.querySelector("[data-toast-region]");
  if (!region || !message) return;
  const toast = document.createElement("div");
  const tone = {
    success: "border-emerald-200 bg-emerald-50 text-emerald-900",
    error: "border-rose-200 bg-rose-50 text-rose-900",
    warning: "border-amber-200 bg-amber-50 text-amber-900",
    info: "border-stone-200 bg-white text-stone-900",
  }[type] || "border-stone-200 bg-white text-stone-900";
  toast.className = `flex items-start justify-between gap-3 rounded-lg border px-4 py-3 text-sm shadow-sm ${tone}`;
  toast.innerHTML = `<span>${message}</span><button type="button" class="min-h-11 min-w-11 text-lg" aria-label="Fechar">×</button>`;
  toast.querySelector("button").addEventListener("click", () => toast.remove());
  region.appendChild(toast);
  window.setTimeout(() => toast.remove(), 5000);
}

export function initToasts() {
  document.addEventListener("app:toast", (event) => {
    showToast(event.detail.message, event.detail.type);
  });
}
