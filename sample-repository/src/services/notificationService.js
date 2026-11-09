// Independent branch: depends on logger.js, but NOT database.js
import { logInfo } from "../utils/logger.js";

export function sendReceipt(userId, transactionId) {
  logInfo(`Sending receipt for transaction ${transactionId} to user ${userId}`);
  return { delivered: true, timestamp: Date.now() };
}
