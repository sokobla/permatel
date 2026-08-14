/**
 * telephonyService — lecture tenant-scopée du module Téléphonie (Supervision).
 * Définitions : voir backend app/routes/telephony.py (source de vérité).
 */
import apiClient from "@/services/http/axios";

export const telephonyService = {
  /** Appels en cours (snapshot au chargement — le WebSocket pousse les deltas ensuite). */
  getActiveCalls() {
    return apiClient.get("/telephony/active-calls");
  },
  /** Volumes, taux de décroché, temps de réponse moyen, sur la période { from, to } (ISO). */
  getKpisSummary(params = {}) {
    return apiClient.get("/telephony/kpis/summary", { params });
  },
  /** Appels par file d'attente, temps d'attente moyen, taux d'abandon. */
  getKpisQueues(params = {}) {
    return apiClient.get("/telephony/kpis/queues", { params });
  },
  /** Présence agent (disponible/pause/hors-ligne) + appels traités sur la période. */
  getAgentsStatus(params = {}) {
    return apiClient.get("/telephony/agents/status", { params });
  },

  // ── Rapports > Téléphonie (historique, export, enregistrements) ─────────

  /** Historique paginé/filtrable des appels terminés. */
  getCalls(params = {}) {
    return apiClient.get("/telephony/calls", { params });
  },
  /** Export CSV du même historique (mêmes filtres) — réponse blob. */
  exportCallsCsv(params = {}) {
    return apiClient.get("/telephony/calls/export", {
      params,
      responseType: "blob",
    });
  },
  /** Enregistrements paginés/filtrables (sous-ensemble des appels avec `recording_url`). */
  getRecordings(params = {}) {
    return apiClient.get("/telephony/recordings", { params });
  },
  /** Agents PBX du tenant (14/08) — alimente le filtre multi-select du CDR. */
  getAgentsRoster() {
    return apiClient.get("/telephony/agents/roster");
  },
  /** Files PBX du tenant (14/08) — alimente le filtre multi-select du CDR. */
  getQueuesRoster() {
    return apiClient.get("/telephony/queues/roster");
  },
  /** Téléchargement d'un enregistrement (proxy backend) — réponse blob. */
  downloadRecording(callUuid) {
    return apiClient.get(`/telephony/recordings/${callUuid}/download`, {
      responseType: "blob",
    });
  },
  /** Export groupé en ZIP — `callUuids` optionnel (sélection explicite), sinon filtres. */
  exportRecordingsBulk(callUuids, params = {}) {
    return apiClient.post(
      "/telephony/recordings/export",
      { call_uuids: callUuids && callUuids.length ? callUuids : undefined },
      { params, responseType: "blob" },
    );
  },

  // ── Webhook CDR (connecteur) ─────────────────────────────────────────────

  /** (Re)génère le jeton webhook CDR d'un connecteur — invalide l'ancienne URL. */
  regenerateCdrToken(connectorId) {
    return apiClient.post(
      `/telephony/connectors/${connectorId}/cdr-token/regenerate`,
    );
  },

  // ── Statut self-service (exécution à distance ESL, 13/08) ────────────────

  /** Change le statut FusionPBX de l'utilisateur courant ({ status, pause_code? }). */
  setMyStatus(payload) {
    return apiClient.post("/telephony/agents/me/status", payload);
  },
  /** Codes de pause configurés pour le tenant actif (dont "0", protégé). */
  getPauseCodes() {
    return apiClient.get("/telephony/pause-codes");
  },
  /** Crée un nouveau code de pause (Paramètres > Téléphonie, admin tenant). */
  createPauseCode(payload) {
    return apiClient.post("/telephony/pause-codes", payload);
  },
  /** Modifie un code de pause existant — refusé (409) si protégé. */
  updatePauseCode(id, payload) {
    return apiClient.put(`/telephony/pause-codes/${id}`, payload);
  },
  /** Supprime un code de pause — refusé (409) si protégé. */
  deletePauseCode(id) {
    return apiClient.delete(`/telephony/pause-codes/${id}`);
  },
};
