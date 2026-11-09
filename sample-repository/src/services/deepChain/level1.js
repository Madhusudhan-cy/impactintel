// Level 1 dependent of database.js (Depth 1)
import { dbConnection } from "../../database/database.js";

export function getRawDbStatus() {
  return dbConnection.connected;
}
