import express from "express"; // External dependency
import { processPayment } from "../services/paymentService.js";

export function handlePaymentRequest(req, res) {
  const { userId, amount } = req.body;
  const paymentResult = processPayment(userId, amount);
  return res.json(paymentResult);
}

export default handlePaymentRequest;
