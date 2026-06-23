/**
 * notificationService — notifications in-app + préférences (tenant actif).
 */
import apiClient from "@/services/http/axios";

export const notificationService = {
  list(params = {}) {
    return apiClient.get("/notifications", { params });
  },
  unreadCount() {
    return apiClient.get("/notifications/unread-count");
  },
  markRead(id) {
    return apiClient.post(`/notifications/${id}/read`);
  },
  markAllRead() {
    return apiClient.post("/notifications/read-all");
  },
  getPreferences() {
    return apiClient.get("/notifications/preferences");
  },
  setPreference(payload) {
    // { type, in_app?, email? }
    return apiClient.put("/notifications/preferences", payload);
  },
};
