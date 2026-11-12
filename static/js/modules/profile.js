const dialog = document.getElementById('logout-dialog');
const openButton = document.getElementById('open-logout');
if (dialog && openButton) {
  openButton.addEventListener('click', () => dialog.showModal());
  dialog.querySelectorAll('[data-close-logout]').forEach(button => button.addEventListener('click', () => dialog.close()));
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
  });
  dialog.addEventListener('close', () => openButton.focus());
}
