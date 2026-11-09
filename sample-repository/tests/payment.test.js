import { processPayment } from "../src/services/paymentService.js";

export function testProcessPayment() {
  const res = processPayment("user_1", 100);
  console.assert(res.success === true, "Payment should succeed");
}
