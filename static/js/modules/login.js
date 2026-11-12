import { getCsrfToken } from "../core/csrf.js";

const loginForm = document.getElementById("login-form");
const password = document.getElementById("id_password");
const toggle = document.getElementById("toggle-password");

toggle?.addEventListener("click", () => {
  const visible = password.type === "password";
  password.type = visible ? "text" : "password";
  toggle.setAttribute("aria-pressed", String(visible));
  toggle.setAttribute("aria-label", visible ? "Ocultar senha" : "Mostrar senha");
  toggle.querySelector("span").textContent = visible ? "visibility_off" : "visibility";
});

loginForm?.addEventListener("submit", () => {
  loginForm.elements.csrfmiddlewaretoken.value = getCsrfToken();
});
