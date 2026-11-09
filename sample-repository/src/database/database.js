// Base dependency: Database connection pool and query runner
export class Database {
  constructor(connectionString) {
    this.connectionString = connectionString;
    this.connected = false;
  }

  connect() {
    this.connected = true;
    return this.connected;
  }

  query(sql, params = []) {
    if (!this.connected) {
      throw new Error("Database not connected");
    }
    return { status: "success", sql, params };
  }
}

export const dbConnection = new Database("postgres://localhost:5432/shop");
export default dbConnection;
