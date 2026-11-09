// Demonstrates an unresolved internal relative import for parser validation
import { missingFunc } from "./nonExistentFile.js";

export function brokenCall() {
  return missingFunc();
}
