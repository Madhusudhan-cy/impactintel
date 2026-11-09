export function PaymentForm({ onSubmit }) {
  return (
    <form onSubmit={onSubmit}>
      <button type="submit">Pay Now</button>
    </form>
  );
}

export default PaymentForm;
