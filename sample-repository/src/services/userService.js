// Circular dependency test part 2: userService imports userRoutes
import { renderUserBadge } from "../routes/userRoutes.js";

export function getUserProfile(userId) {
  const role = "customer";
  return {
    id: userId,
    badge: renderUserBadge(role)
  };
}
