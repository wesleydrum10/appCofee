export function toNumber(value) {
  return Number(String(value).replace(",", ".")) || 0;
}
