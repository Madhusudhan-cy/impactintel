// Level 4 dependent of database.js (Depth 4 - should be PRUNED by max_depth=3)
import { getHealthReport } from "./level3.js";

export function exportHealthMetrics() {
  return JSON.stringify(getHealthReport());
}
