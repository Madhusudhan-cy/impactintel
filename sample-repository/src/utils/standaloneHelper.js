// Completely isolated helper with zero internal/external imports and zero dependents
export function formatCurrency(amount, currency = "USD") {
  return `${currency} ${Number(amount).toFixed(2)}`;
}

export function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1);
}
