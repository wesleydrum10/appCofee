const number = document.querySelector('[data-card-number]');
if (number) {
  const format = value => (value.replace(/\D/g, '').slice(0, 16).match(/.{1,4}/g) || []).join(' ');
  const update = () => {
    const position = number.selectionStart ?? number.value.length;
    const digitsBefore = number.value.slice(0, position).replace(/\D/g, '').length;
    const formatted = format(number.value);
    if (number.value === formatted) return;
    number.value = formatted;
    let cursor = 0;
    let digits = 0;
    while (cursor < formatted.length && digits < digitsBefore) {
      if (/\d/.test(formatted[cursor])) digits++;
      cursor++;
    }
    number.setSelectionRange(cursor, cursor);
  };
  number.addEventListener('input', update);
  update();
}
