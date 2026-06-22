/**
 * tenantMemberService — gestion du roster du tenant actif (admin de tenant).
 * Endpoints tenant-scopés `/api/tenant/*` (le `tid` du JWT cible le tenant).
 */
import apiClient from "@/services/http/axios";

export const tenantMemberService = {
  listMembers() {
    return apiClient.get("/tenant/members");
  },
  updateMember(userId, patch) {
    return apiClient.patch(`/tenant/members/${userId}`, patch);
  },
  removeMember(userId) {
    return apiClient.delete(`/tenant/members/${userId}`);
  },

  listInvitations() {
    return apiClient.get("/tenant/invitations");
  },
  createInvitation(payload) {
    // { email, role, membership_role }
    return apiClient.post("/tenant/invitations", payload);
  },
  resendInvitation(id) {
    return apiClient.post(`/tenant/invitations/${id}/resend`);
  },
  revokeInvitation(id) {
    return apiClient.delete(`/tenant/invitations/${id}`);
  },
};
