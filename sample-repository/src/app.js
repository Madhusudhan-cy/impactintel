import express from "express"; // External dependency
import handlePaymentRequest from "./routes/paymentRoutes.js";
import { handleUserRoute } from "./routes/userRoutes.js";

export function createApp() {
  const app = {
    routes: {
      "/payment": handlePaymentRequest,
      "/user": handleUserRoute
    }
  };
  return app;
}

export default createApp;
