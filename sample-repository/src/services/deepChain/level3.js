// Level 3 dependent of database.js (Depth 3)
import { checkDbHealth } from "./level2.js";

export function getHealthReport() {
  return { service: "database", ...checkDbHealth() };
}
