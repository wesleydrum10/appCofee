import { getCsrfToken } from '../core/csrf.js';

document.querySelectorAll('[data-password-toggle]').forEach(button => {
  const input = document.getElementById(button.dataset.passwordToggle);
  const label = document.querySelector(`label[for="${input.id}"]`).textContent.trim().toLowerCase();
  button.addEventListener('click', () => {
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    button.setAttribute('aria-pressed', String(visible));
    button.setAttribute('aria-label', `${visible ? 'Ocultar' : 'Mostrar'} ${label}`);
    button.querySelector('span').textContent = visible ? 'visibility_off' : 'visibility';
  });
});

const signupForm = document.getElementById('signup-form');
signupForm?.addEventListener('submit', () => {
  signupForm.elements.csrfmiddlewaretoken.value = getCsrfToken();
});
