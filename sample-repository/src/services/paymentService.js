import axios from "axios"; // External dependency
import { dbConnection } from "../database/database.js";
import { logInfo, logError } from "../utils/logger.js";

export function processPayment(userId, amount) {
  logInfo(`Processing payment of ${amount} for user ${userId}`);
  try {
    const result = dbConnection.query("INSERT INTO payments (user_id, amount) VALUES ($1, $2)", [userId, amount]);
    return { success: true, transactionId: "tx_12345", result };
  } catch (error) {
    logError("Payment failed", error);
    return { success: false, error: error.message };
  }
}
