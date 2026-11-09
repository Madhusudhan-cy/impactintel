// Level 2 dependent of database.js (Depth 2)
import { getRawDbStatus } from "./level1.js";

export function checkDbHealth() {
  return { healthy: getRawDbStatus() };
}
