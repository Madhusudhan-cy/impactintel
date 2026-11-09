// Circular dependency test part 1: userRoutes imports userService
import { getUserProfile } from "../services/userService.js";

export function handleUserRoute(userId) {
  return getUserProfile(userId);
}

export function renderUserBadge(role) {
  return `Role: ${role}`;
}
