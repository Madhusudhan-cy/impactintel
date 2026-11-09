import PaymentForm from "./PaymentForm.jsx";
import { processPayment } from "../services/paymentService.js";

export function Checkout() {
  const handlePay = (amount) => {
    processPayment("user_1", amount);
  };

  return (
    <div className="checkout-container">
      <h1>Checkout</h1>
      <PaymentForm onSubmit={handlePay} />
    </div>
  );
}

export default Checkout;
