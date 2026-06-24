<template>
  <v-container fluid class="rp-container">

    <!-- ── Filtre global ───────────────────────────────────────────────── -->
    <v-row>
      <v-col>
        <v-sheet color="#FFFFFF" class="pa-2 d-flex align-center flex-wrap gap-3"
          style="border: 1px solid rgba(197,198,206,0.15)">
          <span class="rp-filter-lbl">PÉRIODE</span>
          <v-chip-group
            v-model="filterPeriod"
            mandatory
            selected-class="text-teal-accent-3"
            :disabled="useCustomRange"
          >
            <v-chip v-for="p in PERIODS" :key="p.value" :value="p.value" size="small">{{ p.label }}</v-chip>
          </v-chip-group>

          <v-divider vertical class="mx-2" style="height:24px" />

          <span class="rp-filter-lbl">DU</span>
          <input v-model="customFrom" type="date" class="rp-date" :max="customTo || undefined" />
          <span class="rp-filter-lbl">AU</span>
          <input v-model="customTo" type="date" class="rp-date" :min="customFrom || undefined" />
          <v-btn
            v-if="useCustomRange"
            size="x-small"
            variant="text"
            icon="mdi-close"
            title="Réinitialiser la plage"
            @click="customFrom = null; customTo = null"
          />

          <v-divider vertical class="mx-2" style="height:24px" />

          <span class="rp-filter-lbl">CLIENT</span>
          <v-select
            v-model="filterClientId"
            :items="clientOptions"
            item-title="nom"
            item-value="id"
            clearable
            density="compact"
            variant="outlined"
            hide-details
            placeholder="Tous"
            style="max-width:180px"
          />

          <v-spacer />

          <div class="rp-status">
            <span :class="['rp-status__dot', loading ? 'rp-status__dot--loading' : 'rp-status__dot--ok']" />
            <span class="rp-status__lbl">{{ loading ? 'CHARGEMENT…' : 'OPÉRATIONNEL' }}</span>
          </div>
        </v-sheet>
      </v-col>
    </v-row>

    <!-- ── Onglets ─────────────────────────────────────────────────────── -->
    <v-row class="mt-2 mb-0">
      <v-col>
        <div class="rp-tabs">
          <button
            v-for="tab in TABS" :key="tab.key"
            :class="['rp-tab', activeTab === tab.key && 'rp-tab--active']"
            @click="activeTab = tab.key"
          >
            <v-icon size="13" class="mr-1">{{ tab.icon }}</v-icon>
            {{ tab.label }}
          </button>
        </div>
      </v-col>
    </v-row>

    <!-- ══ PRODUCTION ══════════════════════════════════════════════════════ -->
    <template v-if="activeTab === 'production'">

      <v-row>
        <v-col v-for="kpi in productionKpis" :key="kpi.label" cols="12" sm="6" md="4" lg="2">
          <v-card elevation="0" :class="['rp-kpi-card', kpi.alert && 'rp-kpi-card--alert']">
            <v-card-text class="rp-kpi-body">
              <div class="rp-kpi-top">
                <v-icon :color="kpi.alert ? '#e74c3c' : '#00a8a8'" size="16">{{ kpi.icon }}</v-icon>
                <span class="rp-kpi-lbl">{{ kpi.label }}</span>
              </div>
              <div :class="['rp-kpi-val', kpi.alert && 'rp-kpi-val--alert']">{{ kpi.value }}</div>
              <div v-if="kpi.sub" class="rp-kpi-sub">{{ kpi.sub }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- ── SLA (résolution) ──────────────────────────────────────────── -->
      <v-row>
        <v-col v-for="kpi in slaKpis" :key="kpi.label" cols="12" sm="6" md="3">
          <v-card elevation="0" :class="['rp-kpi-card', kpi.alert && 'rp-kpi-card--alert']">
            <v-card-text class="rp-kpi-body">
              <div class="rp-kpi-top">
                <v-icon :color="kpi.alert ? '#e74c3c' : '#00a8a8'" size="16">{{ kpi.icon }}</v-icon>
                <span class="rp-kpi-lbl">{{ kpi.label }}</span>
                <v-icon v-if="kpi.info" size="13" class="rp-info" color="#9aa0aa">mdi-information-outline
                  <v-tooltip activator="parent" location="top" max-width="280">{{ kpi.info }}</v-tooltip>
                </v-icon>
              </div>
              <div :class="['rp-kpi-val', kpi.alert && 'rp-kpi-val--alert']">{{ kpi.value }}</div>
              <div v-if="kpi.sub" class="rp-kpi-sub">{{ kpi.sub }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12">
          <v-card elevation="0" class="rp-chart-card">
            <div class="rp-chart-hdr"><span class="rp-chart-title">SLA RÉSOLUTION PAR PRIORITÉ</span></div>
            <v-divider />
            <v-card-text class="pa-0">
              <table class="rp-table">
                <thead>
                  <tr>
                    <th class="rp-th">Priorité</th>
                    <th class="rp-th rp-th--r">Total</th>
                    <th class="rp-th rp-th--r">Respect</th>
                    <th class="rp-th rp-th--r">À risque</th>
                    <th class="rp-th rp-th--r">Hors délai</th>
                    <th class="rp-th rp-th--r">% dans les délais</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!slaByPriorite.length"><td colspan="6" class="rp-td-empty">Aucune donnée SLA sur la période</td></tr>
                  <tr v-for="r in slaByPriorite" :key="r.priorite" class="rp-tr">
                    <td class="rp-td" style="text-transform:capitalize">{{ r.priorite }}</td>
                    <td class="rp-td rp-td--mono rp-td--r">{{ r.total }}</td>
                    <td class="rp-td rp-td--mono rp-td--r">{{ r.met }}</td>
                    <td class="rp-td rp-td--mono rp-td--r" :class="r.at_risk ? 'rp-td--warn' : ''">{{ r.at_risk }}</td>
                    <td class="rp-td rp-td--mono rp-td--r" :class="r.breached ? 'rp-td--warn' : ''">{{ r.breached }}</td>
                    <td class="rp-td rp-td--mono rp-td--r">{{ r.pct_on_time }}%</td>
                  </tr>
                </tbody>
              </table>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12" lg="7">
          <v-card elevation="0" class="rp-chart-card">
            <div class="rp-chart-hdr">
              <span class="rp-chart-title">VOLUME PAR PÉRIODE</span>
              <div class="rp-chart-legend">
                <span class="rp-legend-item"><span class="rp-legend-dot" style="background:#e74c3c"></span>Anomalies</span>
                <span class="rp-legend-item"><span class="rp-legend-dot" style="background:#00a8a8"></span>Commandes</span>
              </div>
            </div>
            <v-divider />
            <v-card-text class="rp-chart-body">
              <ApexChart type="bar" height="220" :options="trendOptions" :series="trendSeries" />
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" lg="5">
          <v-card elevation="0" class="rp-chart-card">
            <div class="rp-chart-hdr"><span class="rp-chart-title">RÉPARTITION PAR STATUT</span></div>
            <v-divider />
            <v-card-text class="rp-chart-body">
              <div v-if="!filteredAll.length" class="rp-chart-empty">Aucune donnée</div>
              <ApexChart v-else type="donut" height="220" :options="statutOptions" :series="statutSeries" />
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12" lg="7">
          <v-card elevation="0" class="rp-chart-card">
            <div class="rp-chart-hdr"><span class="rp-chart-title">TOP CLIENTS — ANOMALIES</span></div>
            <v-divider />
            <v-card-text class="rp-chart-body">
              <div v-if="!top5Clients.length" class="rp-chart-empty">Aucune donnée</div>
              <ApexChart v-else type="bar" height="220" :options="topClientsOptions" :series="topClientsSeries" />
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" lg="5">
          <v-card elevation="0" class="rp-chart-card">
            <div class="rp-chart-hdr"><span class="rp-chart-title">RÉPARTITION PAR PRIORITÉ</span></div>
            <v-divider />
            <v-card-text class="rp-chart-body">
              <div v-if="!filteredAll.length" class="rp-chart-empty">Aucune donnée</div>
              <ApexChart v-else type="donut" height="220" :options="prioriteOptions" :series="prioriteSeries" />
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

    </template>

    <!-- ══ PRISES DE SERVICE ═══════════════════════════════════════════════ -->
    <template v-if="activeTab === 'vacations'">

      <v-row>
        <v-col v-for="kpi in vacationsKpis" :key="kpi.label" cols="12" sm="6" md="4" lg="2">
          <v-card elevation="0" :class="['rp-kpi-card', kpi.alert && 'rp-kpi-card--alert']">
            <v-card-text class="rp-kpi-body">
              <div class="rp-kpi-top">
                <v-icon :color="kpi.alert ? '#e74c3c' : '#00a8a8'" size="16">{{ kpi.icon }}</v-icon>
                <span class="rp-kpi-lbl">{{ kpi.label }}</span>
              </div>
              <div :class="['rp-kpi-val', kpi.alert && 'rp-kpi-val--alert']">{{ kpi.value }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12" md="6">
          <v-card elevation="0" class="rp-chart-card">
            <div class="rp-chart-hdr"><span class="rp-chart-title">PRISES DE SERVICE PAR CLIENT</span></div>
            <v-divider />
            <v-card-text class="pa-0">
              <table class="rp-table">
                <thead>
                  <tr><th>Client</th><th style="text-align:right">Vacations</th></tr>
                </thead>
                <tbody>
                  <tr v-for="[name, count] in vacationsByClient" :key="name">
                    <td>{{ name }}</td>
                    <td style="text-align:right">{{ count }}</td>
                  </tr>
                  <tr v-if="vacationsByClient.length === 0">
                    <td colspan="2" style="text-align:center; color:#bbb; padding:24px 0">
                      Aucune prise de service sur la période
                    </td>
                  </tr>
                </tbody>
              </table>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

    </template>

    <!-- ══ AGENTS ══════════════════════════════════════════════════════════ -->
    <template v-if="activeTab === 'agents'">

      <v-row>
        <v-col v-for="kpi in agentsKpis" :key="kpi.label" cols="12" sm="6" md="4">
          <v-card elevation="0" class="rp-kpi-card">
            <v-card-text class="rp-kpi-body">
              <div class="rp-kpi-top">
                <v-icon color="#00a8a8" size="16">{{ kpi.icon }}</v-icon>
                <span class="rp-kpi-lbl">{{ kpi.label }}</span>
              </div>
              <div class="rp-kpi-val">{{ kpi.value }}</div>
              <div v-if="kpi.sub" class="rp-kpi-sub">{{ kpi.sub }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row>
        <v-col>
          <v-card elevation="0" class="rp-chart-card">
            <div class="rp-chart-hdr">
              <span class="rp-chart-title">CLASSEMENT DES AGENTS</span>
              <div class="rp-chart-legend">
                <span class="rp-legend-item"><span class="rp-score-dot rp-score-dot--green"></span>Fiable</span>
                <span class="rp-legend-item"><span class="rp-score-dot rp-score-dot--orange"></span>À surveiller</span>
                <span class="rp-legend-item"><span class="rp-score-dot rp-score-dot--red"></span>À risque</span>
              </div>
            </div>
            <v-divider />
            <v-card-text class="pa-0">
              <table class="rp-table">
                <thead>
                  <tr>
                    <th class="rp-th" style="width:36px">#</th>
                    <th class="rp-th">Agent</th>
                    <th class="rp-th rp-th--r">
                      Incidents
                      <v-icon size="12" class="rp-info" color="#9aa0aa">mdi-information-outline
                        <v-tooltip activator="parent" location="top" max-width="260">Anomalies discriminantes (natures pénalisantes ou impact sécurité). Impactent le score.</v-tooltip>
                      </v-icon>
                    </th>
                    <th class="rp-th rp-th--r">
                      Anomalies
                      <v-icon size="12" class="rp-info" color="#9aa0aa">mdi-information-outline
                        <v-tooltip activator="parent" location="top" max-width="260">Toutes les anomalies impliquant l'agent (incidents inclus).</v-tooltip>
                      </v-icon>
                    </th>
                    <th class="rp-th rp-th--c">Score</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="agentKpiLoading">
                    <td colspan="5" class="rp-td-empty">Chargement…</td>
                  </tr>
                  <tr v-else-if="!agentRanking.length">
                    <td colspan="5" class="rp-td-empty">Aucun agent impliqué sur la période</td>
                  </tr>
                  <tr v-for="(ag, i) in agentRanking" :key="ag.id" class="rp-tr">
                    <td class="rp-td rp-td--rank">{{ i + 1 }}</td>
                    <td class="rp-td">
                      <div class="rp-cell-person">
                        <span :class="['rp-avatar', `rp-avatar--${ag.scoreColor}`]">{{ initials(ag.nom) }}</span>
                        <span class="rp-person-name">{{ ag.nom }}</span>
                      </div>
                    </td>
                    <td class="rp-td rp-td--mono rp-td--r" :class="ag.incidents > 0 ? 'rp-td--warn' : ''">{{ ag.incidents }}</td>
                    <td class="rp-td rp-td--mono rp-td--r">{{ ag.anomalies }}</td>
                    <td class="rp-td rp-td--c">
                      <span :class="['rp-score', `rp-score--${ag.scoreColor}`]">{{ ag.score }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

    </template>

    <!-- ══ PERMANENCIERS ════════════════════════════════════════════════════ -->
    <template v-if="activeTab === 'permanenciers'">

      <v-row>
        <v-col v-for="kpi in permanenciersKpis" :key="kpi.label" cols="12" sm="6" md="4">
          <v-card elevation="0" :class="['rp-kpi-card', kpi.alert && 'rp-kpi-card--alert']">
            <v-card-text class="rp-kpi-body">
              <div class="rp-kpi-top">
                <v-icon :color="kpi.alert ? '#e74c3c' : '#00a8a8'" size="16">{{ kpi.icon }}</v-icon>
                <span class="rp-kpi-lbl">{{ kpi.label }}</span>
              </div>
              <div :class="['rp-kpi-val', kpi.alert && 'rp-kpi-val--alert']">{{ kpi.value }}</div>
              <div v-if="kpi.sub" class="rp-kpi-sub">{{ kpi.sub }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row>
        <v-col>
          <v-card elevation="0" class="rp-chart-card">
            <div class="rp-chart-hdr"><span class="rp-chart-title">PERFORMANCE PAR OPÉRATEUR</span></div>
            <v-divider />
            <v-card-text class="pa-0">
              <table class="rp-table">
                <thead>
                  <tr>
                    <th class="rp-th">Utilisateur</th>
                    <th class="rp-th rp-th--c">Rôle</th>
                    <th class="rp-th rp-th--r">Créées</th>
                    <th class="rp-th" style="min-width:180px">Complétude</th>
                    <th class="rp-th rp-th--r">En souffrance</th>
                    <th class="rp-th rp-th--r">Délai moy.</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!permanencierRanking.length">
                    <td colspan="6" class="rp-td-empty">Aucune donnée sur la période</td>
                  </tr>
                  <tr v-for="u in permanencierRanking" :key="u.id" class="rp-tr">
                    <td class="rp-td">
                      <div class="rp-cell-person">
                        <span class="rp-avatar rp-avatar--teal">{{ initials(u.nom) }}</span>
                        <span class="rp-person-name">{{ u.nom }}</span>
                      </div>
                    </td>
                    <td class="rp-td rp-td--c">
                      <span class="rp-role-badge">{{ u.role ?? '—' }}</span>
                    </td>
                    <td class="rp-td rp-td--mono rp-td--r">{{ u.total }}</td>
                    <td class="rp-td">
                      <div class="rp-completude">
                        <div class="rp-bar-track">
                          <div class="rp-bar-fill"
                            :style="{ width: u.completude + '%', background: completudeColor(u.completude) }"
                          />
                        </div>
                        <span class="rp-completude-pct">{{ u.completude }}%</span>
                      </div>
                    </td>
                    <td class="rp-td rp-td--mono rp-td--r" :class="u.souffrance > 0 ? 'rp-td--warn' : ''">
                      {{ u.souffrance }}
                    </td>
                    <td class="rp-td rp-td--mono rp-td--r">{{ u.delai > 0 ? u.delai + 'h' : '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

    </template>

    <!-- ══ SESSIONS ════════════════════════════════════════════════════════ -->
    <template v-if="activeTab === 'sessions'">

      <!-- Filtre par utilisateur -->
      <v-row class="mt-1">
        <v-col cols="12" class="d-flex align-center flex-wrap gap-3">
          <span class="rp-filter-lbl">UTILISATEUR</span>
          <v-select
            v-model="sessionUserId"
            :items="sessionUsers"
            item-title="label"
            item-value="id"
            clearable
            density="compact"
            variant="outlined"
            hide-details
            placeholder="Tous les utilisateurs"
            style="max-width: 280px"
          />
          <span v-if="sessionUserId" class="rp-filter-hint">
            KPI restreints à l'utilisateur sélectionné
          </span>
        </v-col>
      </v-row>

      <!-- Erreur -->
      <v-row v-if="sessionError">
        <v-col>
          <div class="rp-sess-error">{{ sessionError }}</div>
        </v-col>
      </v-row>

      <!-- Cartes KPI scalaires -->
      <v-row>
        <v-col v-for="kpi in sessionKpis" :key="kpi.key" cols="12" sm="6" md="4" lg="3" xl="2">
          <v-card elevation="0" :class="['rp-kpi-card', kpi.alert && 'rp-kpi-card--alert']">
            <v-card-text class="rp-kpi-body">
              <div class="rp-kpi-top">
                <v-icon :color="kpi.alert ? '#e74c3c' : '#00a8a8'" size="16">{{ kpi.icon }}</v-icon>
                <span class="rp-kpi-lbl">{{ kpi.label }}</span>
                <v-icon size="13" class="rp-info" color="#9aa0aa">
                  mdi-information-outline
                  <v-tooltip activator="parent" location="top" max-width="300" open-delay="100">
                    {{ kpi.info }}
                  </v-tooltip>
                </v-icon>
              </div>
              <div :class="['rp-kpi-val', kpi.alert && 'rp-kpi-val--alert']">
                {{ sessionLoading ? '…' : kpi.value }}
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Blocs de répartition / séries -->
      <v-row>
        <!-- Connexions par jour -->
        <v-col cols="12" md="6" lg="4">
          <v-card elevation="0" class="rp-block">
            <div class="rp-block-hd">
              <span class="rp-block-title">CONNEXIONS / JOUR</span>
              <v-icon size="13" class="rp-info" color="#9aa0aa">
                mdi-information-outline
                <v-tooltip activator="parent" location="top" max-width="300">
                  Nombre de connexions réussies par jour sur la période. Permet de visualiser la tendance d'usage et les jours creux/pleins.
                </v-tooltip>
              </v-icon>
            </div>
            <div v-if="sessionLogins.length" class="rp-bars">
              <div v-for="d in sessionLogins" :key="d.date" class="rp-bar-col" :title="`${d.date} : ${d.count}`">
                <div class="rp-bar" :style="{ height: Math.max(4, d.pct) + '%' }"></div>
              </div>
            </div>
            <p v-else class="rp-block-empty">Aucune donnée.</p>
          </v-card>
        </v-col>

        <!-- Heures de pointe -->
        <v-col cols="12" md="6" lg="4">
          <v-card elevation="0" class="rp-block">
            <div class="rp-block-hd">
              <span class="rp-block-title">HEURES DE POINTE</span>
              <v-icon size="13" class="rp-info" color="#9aa0aa">
                mdi-information-outline
                <v-tooltip activator="parent" location="top" max-width="300">
                  Répartition des connexions par heure de la journée (0–23 h), cumulée sur la période. Identifie les créneaux de forte affluence.
                </v-tooltip>
              </v-icon>
            </div>
            <div class="rp-bars rp-bars--hours">
              <div v-for="h in sessionPeakHours" :key="h.hour" class="rp-bar-col" :title="`${h.hour}h : ${h.count}`">
                <div class="rp-bar rp-bar--alt" :style="{ height: Math.max(2, h.pct) + '%' }"></div>
              </div>
            </div>
            <div class="rp-axis"><span>0h</span><span>12h</span><span>23h</span></div>
          </v-card>
        </v-col>

        <!-- Top IP échecs -->
        <v-col cols="12" md="6" lg="4">
          <v-card elevation="0" class="rp-block">
            <div class="rp-block-hd">
              <span class="rp-block-title">TOP IP — ÉCHECS</span>
              <v-icon size="13" class="rp-info" color="#9aa0aa">
                mdi-information-outline
                <v-tooltip activator="parent" location="top" max-width="300">
                  Adresses IP ayant généré le plus de tentatives de connexion échouées. Outil de détection d'attaques par force brute. (Hors tentatives sur identifiants inexistants.)
                </v-tooltip>
              </v-icon>
            </div>
            <ul v-if="sessionTopIps.length" class="rp-iplist">
              <li v-for="ip in sessionTopIps" :key="ip.ip">
                <span class="rp-mono">{{ ip.ip }}</span>
                <span class="rp-ipcount">{{ ip.count }}</span>
              </li>
            </ul>
            <p v-else class="rp-block-empty">Aucun échec enregistré.</p>
          </v-card>
        </v-col>

        <!-- Répartition par rôle -->
        <v-col cols="12" md="6">
          <v-card elevation="0" class="rp-block">
            <div class="rp-block-hd">
              <span class="rp-block-title">SESSIONS PAR RÔLE</span>
              <v-icon size="13" class="rp-info" color="#9aa0aa">
                mdi-information-outline
                <v-tooltip activator="parent" location="top" max-width="300">
                  Répartition des sessions actives selon le rôle de l'utilisateur (Admin / Manager / Permanencier). Vue de qui est connecté.
                </v-tooltip>
              </v-icon>
            </div>
            <div v-if="sessionByRole.length" class="rp-hbars">
              <div v-for="r in sessionByRole" :key="r.label" class="rp-hbar-row">
                <span class="rp-hbar-lbl">{{ r.label }}</span>
                <div class="rp-hbar-track"><div class="rp-hbar-fill" :style="{ width: r.pct + '%' }"></div></div>
                <span class="rp-hbar-val">{{ r.count }}</span>
              </div>
            </div>
            <p v-else class="rp-block-empty">Aucune session active.</p>
          </v-card>
        </v-col>

        <!-- Raisons de fin de session -->
        <v-col cols="12" md="6">
          <v-card elevation="0" class="rp-block">
            <div class="rp-block-hd">
              <span class="rp-block-title">RAISONS DE FIN DE SESSION</span>
              <v-icon size="13" class="rp-info" color="#9aa0aa">
                mdi-information-outline
                <v-tooltip activator="parent" location="top" max-width="300">
                  Répartition des sessions de la période par statut final : déconnexion volontaire, expiration par inactivité, révocation, ou encore en cours / en pause.
                </v-tooltip>
              </v-icon>
            </div>
            <div v-if="sessionEndReasons.length" class="rp-hbars">
              <div v-for="r in sessionEndReasons" :key="r.key" class="rp-hbar-row">
                <span class="rp-hbar-lbl">{{ r.label }}</span>
                <div class="rp-hbar-track">
                  <div class="rp-hbar-fill" :style="{ width: r.pct + '%', background: r.color }"></div>
                </div>
                <span class="rp-hbar-val">{{ r.count }} ({{ r.pct }}%)</span>
              </div>
            </div>
            <p v-else class="rp-block-empty">Aucune donnée.</p>
          </v-card>
        </v-col>
      </v-row>

    </template>

    <!-- ══ EMAIL ═══════════════════════════════════════════════════════════ -->
    <template v-if="activeTab === 'email'">

      <!-- Filtre par utilisateur -->
      <v-row class="mt-1">
        <v-col cols="12" class="d-flex align-center flex-wrap gap-3">
          <span class="rp-filter-lbl">UTILISATEUR</span>
          <v-select
            v-model="emailUserId"
            :items="sessionUsers"
            item-title="label"
            item-value="id"
            clearable
            density="compact"
            variant="outlined"
            hide-details
            placeholder="Tous les utilisateurs"
            style="max-width: 280px"
          />
          <span v-if="emailUserId" class="rp-filter-hint">KPI restreints à l'utilisateur sélectionné</span>
        </v-col>
      </v-row>

      <v-row v-if="emailError"><v-col><div class="rp-sess-error">{{ emailError }}</div></v-col></v-row>

      <!-- Cartes KPI -->
      <v-row>
        <v-col v-for="kpi in emailKpis" :key="kpi.key" cols="12" sm="6" md="4" lg="2">
          <v-card elevation="0" :class="['rp-kpi-card', kpi.alert && 'rp-kpi-card--alert']">
            <v-card-text class="rp-kpi-body">
              <div class="rp-kpi-top">
                <v-icon :color="kpi.alert ? '#e74c3c' : '#00a8a8'" size="16">{{ kpi.icon }}</v-icon>
                <span class="rp-kpi-lbl">{{ kpi.label }}</span>
                <v-icon v-if="kpi.hint" size="13" class="rp-info" color="#9aa0aa">
                  mdi-information-outline
                  <v-tooltip activator="parent" location="top" max-width="240">{{ kpi.hint }}</v-tooltip>
                </v-icon>
              </div>
              <div :class="['rp-kpi-val', kpi.alert && 'rp-kpi-val--alert']">
                {{ emailLoading ? '…' : kpi.value }}
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row>
        <!-- Emails envoyés / jour -->
        <v-col cols="12" md="6">
          <v-card elevation="0" class="rp-block">
            <div class="rp-block-hd"><span class="rp-block-title">EMAILS ENVOYÉS / JOUR</span></div>
            <div v-if="emailPerDay.length" class="rp-bars">
              <div v-for="d in emailPerDay" :key="d.date" class="rp-bar-col" :title="`${d.date} : ${d.count}`">
                <div class="rp-bar" :style="{ height: Math.max(4, d.pct) + '%' }"></div>
              </div>
            </div>
            <p v-else class="rp-block-empty">Aucune donnée sur la période.</p>
          </v-card>
        </v-col>

        <!-- Volume par utilisateur -->
        <v-col cols="12" md="6">
          <v-card elevation="0" class="rp-block">
            <div class="rp-block-hd"><span class="rp-block-title">VOLUME PAR UTILISATEUR</span></div>
            <div v-if="emailByUser.length" class="rp-hbars">
              <div v-for="u in emailByUser" :key="u.user_id" class="rp-hbar-row">
                <span class="rp-hbar-lbl">{{ u.username }}</span>
                <div class="rp-hbar-track"><div class="rp-hbar-fill" :style="{ width: u.pct + '%' }"></div></div>
                <span class="rp-hbar-val">{{ u.count }}</span>
              </div>
            </div>
            <p v-else class="rp-block-empty">Aucun envoi sur la période.</p>
          </v-card>
        </v-col>
      </v-row>

    </template>

  </v-container>
</template>

<style scoped>
/* ── Onglet Sessions ─────────────────────────────────────────────────── */
.rp-info { cursor: help; margin-left: auto; }
.rp-filter-hint { font-size: 11px; color: #00a8a8; font-style: italic; }
.rp-date {
  height: 30px;
  padding: 0 8px;
  border: 1px solid rgba(197, 198, 206, 0.5);
  border-radius: 4px;
  font-family: "Fira Code", monospace;
  font-size: 12px;
  color: #1a1a2e;
  background: #fff;
  outline: none;
}
.rp-date:focus { border-color: #00a8a8; }
.rp-sess-error {
  padding: 10px 14px;
  border-radius: 6px;
  background: rgba(231, 76, 60, 0.08);
  border: 1px solid rgba(231, 76, 60, 0.3);
  color: #a93226;
  font-size: 13px;
}
.rp-block {
  background: #fff;
  border: 1px solid rgba(197, 198, 206, 0.25);
  padding: 14px 16px;
  height: 100%;
}
.rp-block-hd { display: flex; align-items: center; gap: 6px; margin-bottom: 12px; }
.rp-block-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #6b7280;
}
.rp-block-empty { font-size: 12px; color: #9aa0aa; margin: 8px 0 0; }
.rp-mono { font-family: "Fira Code", monospace; }

/* Barres verticales (séries) */
.rp-bars {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 90px;
}
.rp-bars--hours { gap: 1px; }
.rp-bar-col { flex: 1; display: flex; align-items: flex-end; height: 100%; }
.rp-bar { width: 100%; background: #00a8a8; border-radius: 2px 2px 0 0; min-height: 2px; }
.rp-bar--alt { background: #3498db; }
.rp-axis {
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  color: #9aa0aa;
  font-family: "Fira Code", monospace;
  margin-top: 4px;
}

/* Barres horizontales (répartitions) */
.rp-hbars { display: flex; flex-direction: column; gap: 9px; }
.rp-hbar-row { display: flex; align-items: center; gap: 10px; }
.rp-hbar-lbl { width: 96px; font-size: 12px; color: #1a1a2e; flex-shrink: 0; }
.rp-hbar-track { flex: 1; height: 10px; background: #f0f1f3; border-radius: 5px; overflow: hidden; }
.rp-hbar-fill { height: 100%; background: #00a8a8; border-radius: 5px; }
.rp-hbar-val { width: 84px; text-align: right; font-size: 12px; font-weight: 600; color: #1a1a2e; flex-shrink: 0; }

/* Liste IP */
.rp-iplist { list-style: none; padding: 0; margin: 0; }
.rp-iplist li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid rgba(197, 198, 206, 0.2);
  font-size: 13px;
}
.rp-iplist li:last-child { border-bottom: none; }
.rp-ipcount {
  font-family: "Fira Code", monospace;
  font-weight: 700;
  color: #e74c3c;
}
</style>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import ApexChart from "vue3-apexcharts";
import { listDemandes } from "@/services/demandeService";
import { listPrisesDeService } from "@/services/priseDeServiceService";
import { sessionService } from "@/services/sessionService";
import { userService } from "@/services/userService";
import { emailService } from "@/services/emailService";
import { agentKpiService } from "@/services/agentKpiService";
import { useAuthStore } from "@/store/auth";

const authStore = useAuthStore();

// ── Constants ────────────────────────────────────────────────────────

const PERIODS = [
  { value: "today", label: "Aujourd'hui" },
  { value: "7j",   label: "7 Jours" },
  { value: "30j",  label: "30 Jours" },
  { value: "3m",   label: "3 Mois" },
  { value: "all",  label: "Tout" },
];

const TABS = [
  { key: "production",    label: "Production",    icon: "mdi-chart-bar" },
  { key: "vacations",     label: "Prises de service", icon: "mdi-clock-start" },
  { key: "agents",        label: "Agents",        icon: "mdi-shield-account-outline" },
  { key: "permanenciers", label: "Opérateurs",    icon: "mdi-account-key-outline" },
  { key: "sessions",      label: "Sessions",      icon: "mdi-monitor-account" },
  { key: "email",         label: "Email",         icon: "mdi-email-outline" },
];

const STATUT_META = {
  nouvelle:   { label: "Nouvelle",   color: "#3498db" },
  en_cours:   { label: "En cours",   color: "#f39c12" },
  en_attente: { label: "En attente", color: "#8e44ad" },
  resolue:    { label: "Résolue",    color: "#27ae60" },
  cloturee:   { label: "Clôturée",   color: "#00a8a8" },
  annulee:    { label: "Annulée",    color: "#bdc3c7" },
};

const PRIORITE_META = {
  basse:   { label: "Basse",   color: "#27ae60" },
  normale: { label: "Normale", color: "#3498db" },
  haute:   { label: "Haute",   color: "#f39c12" },
  urgente: { label: "Urgente", color: "#e74c3c" },
};

const SOUFFRANCE_DAYS = 3;

// ── State ────────────────────────────────────────────────────────────

const activeTab      = ref("production");
const filterPeriod   = ref("30j");
const filterClientId = ref(null);
const loading        = ref(false);

// Période libre (daterange) — prioritaire sur les chips si renseignée
const customFrom     = ref(null); // 'YYYY-MM-DD'
const customTo       = ref(null); // 'YYYY-MM-DD'
const useCustomRange = computed(() => !!(customFrom.value || customTo.value));

const rawAnomalies = ref([]);
const rawCommandes = ref([]);
const rawPrises    = ref([]);

// ── Load ─────────────────────────────────────────────────────────────

async function loadData() {
  loading.value = true;
  try {
    const [a, c, p] = await Promise.all([
      listDemandes({ type_demande: "anomalie" }),
      listDemandes({ type_demande: "commande" }),
      listPrisesDeService().catch(() => []),
    ]);
    rawAnomalies.value = Array.isArray(a) ? a : (a.items ?? []);
    rawCommandes.value = Array.isArray(c) ? c : (c.items ?? []);
    rawPrises.value    = Array.isArray(p) ? p : (p.items ?? []);
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);

// ── KPI Sessions ─────────────────────────────────────────────────────

const sessionStats   = ref(null);
const sessionLoading = ref(false);
const sessionError   = ref("");
const sessionUserId  = ref(null);
const sessionUsers   = ref([]);

function periodRange() {
  // Plage libre prioritaire
  if (useCustomRange.value) {
    const from = customFrom.value
      ? new Date(customFrom.value + "T00:00:00")
      : new Date(Date.now() - 10 * 365 * 86400000);
    const to = customTo.value ? new Date(customTo.value + "T23:59:59") : new Date();
    return { from: from.toISOString(), to: to.toISOString() };
  }
  const to = new Date();
  const from = new Date(to);
  switch (filterPeriod.value) {
    case "today": from.setHours(0, 0, 0, 0); break;
    case "7j":    from.setDate(from.getDate() - 7); break;
    case "30j":   from.setDate(from.getDate() - 30); break;
    case "3m":    from.setMonth(from.getMonth() - 3); break;
    case "all":   from.setFullYear(from.getFullYear() - 10); break;
    default:      from.setDate(from.getDate() - 30);
  }
  return { from: from.toISOString(), to: to.toISOString() };
}

async function loadSessionStats() {
  sessionLoading.value = true;
  sessionError.value = "";
  try {
    const { from, to } = periodRange();
    const params = { from, to };
    if (sessionUserId.value) params.user_id = sessionUserId.value;
    const { data } = await sessionService.getMonitoringStats(params);
    sessionStats.value = data;
  } catch (err) {
    sessionError.value =
      err?.response?.data?.error || "Impossible de charger les statistiques de sessions.";
    sessionStats.value = null;
  } finally {
    sessionLoading.value = false;
  }
}

async function loadSessionUsers() {
  if (sessionUsers.value.length) return;
  try {
    if (authStore.isAdmin) {
      // ADMIN : tous les utilisateurs (tous tenants)
      const { data } = await userService.getUsers({ per_page: 1000 });
      const list = data.users ?? data ?? [];
      sessionUsers.value = list.map((u) => ({
        id: u.id,
        label: `${u.username}${u.role ? ` — ${u.role}` : ""}`,
      }));
    } else {
      // MANAGER : utilisateurs du tenant actif
      const tid = authStore.activeTenantId;
      if (!tid) return;
      const { data } = await sessionService.getTenantUsers(tid);
      const list = Array.isArray(data) ? data : [];
      sessionUsers.value = list.map((u) => ({
        id: u.user_id,
        label: `${u.username}${u.role ? ` — ${u.role}` : ""}`,
      }));
    }
  } catch {
    sessionUsers.value = [];
  }
}

// Charge à l'ouverture de l'onglet, au changement de période/plage ou d'utilisateur
watch(
  [activeTab, filterPeriod, sessionUserId, customFrom, customTo],
  () => {
    if (activeTab.value === "sessions") {
      loadSessionUsers();
      loadSessionStats();
    }
  },
  { immediate: true },
);

// ── KPI Email ────────────────────────────────────────────────────────
const emailStats = ref(null);
const emailLoading = ref(false);
const emailError = ref("");
const emailUserId = ref(null); // réutilise sessionUsers pour la liste

async function loadEmailStats() {
  emailLoading.value = true;
  emailError.value = "";
  try {
    const { from, to } = periodRange();
    const params = { from, to };
    if (emailUserId.value) params.user_id = emailUserId.value;
    emailStats.value = await emailService.getStats(params);
  } catch (err) {
    emailError.value = err?.response?.data?.error || "Impossible de charger les statistiques email.";
    emailStats.value = null;
  } finally {
    emailLoading.value = false;
  }
}

watch(
  [activeTab, filterPeriod, emailUserId, customFrom, customTo],
  () => {
    if (activeTab.value === "email") {
      loadSessionUsers(); // même liste d'utilisateurs (role-aware)
      loadEmailStats();
    }
  },
  { immediate: true },
);

function fmtMinutes(min) {
  if (!min) return "—";
  if (min < 60) return `${Math.round(min)} min`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m ? `${h} h ${m}` : `${h} h`;
}

const emailKpis = computed(() => {
  const k = emailStats.value?.kpi;
  if (!k) return [];
  return [
    { key: "sent", label: "Emails envoyés", icon: "mdi-send-outline", value: k.sent_total },
    { key: "recv", label: "Emails reçus", icon: "mdi-inbox-arrow-down-outline", value: k.received_total },
    { key: "fail", label: "Échecs d'envoi", icon: "mdi-alert-circle-outline", value: k.failed_total, alert: k.failed_total > 0 },
    { key: "rate", label: "Taux d'échec", icon: "mdi-percent-outline", value: k.failure_rate_pct + " %", alert: k.failure_rate_pct >= 20 },
    { key: "resp", label: "Taux de réponse", icon: "mdi-reply-outline", value: k.response_rate_pct + " %",
      info: "Part des emails reçus ayant reçu une réponse (corrélation In-Reply-To)." },
    { key: "delay", label: "Délai moyen de réponse", icon: "mdi-timer-outline", value: fmtMinutes(k.avg_response_minutes),
      info: "Temps moyen entre la réception et la première réponse." },
    { key: "unans", label: "Sans réponse", icon: "mdi-email-alert-outline", value: k.unanswered, alert: k.unanswered > 0,
      info: "Emails reçus non traités, non archivés et restés sans réponse." },
    { key: "att", label: "Avec pièce jointe", icon: "mdi-paperclip", value: k.with_attachments },
  ];
});

const emailPerDay = computed(() => {
  const s = emailStats.value?.per_day ?? [];
  const max = Math.max(1, ...s.map((d) => d.count));
  return s.map((d) => ({ ...d, pct: Math.round((d.count / max) * 100) }));
});

const emailByUser = computed(() => {
  const s = emailStats.value?.by_user ?? [];
  const max = Math.max(1, ...s.map((u) => u.count));
  return s.map((u) => ({ ...u, pct: Math.round((u.count / max) * 100) }));
});

const ROLE_LABELS = { ADMIN: "Admin", MANAGER: "Manager", PERMANENCIER: "Permanencier", inconnu: "Inconnu" };
const END_REASON_META = {
  ended:   { label: "Déconnexion",  color: "#00a8a8" },
  expired: { label: "Inactivité",   color: "#f39c12" },
  revoked: { label: "Révocation",   color: "#e74c3c" },
  active:  { label: "En cours",     color: "#22c55e" },
  paused:  { label: "En pause",     color: "#8e44ad" },
};

// Cartes KPI scalaires (chaque entrée porte une description `info`)
const sessionKpis = computed(() => {
  const s = sessionStats.value;
  if (!s) return [];
  return [
    { key: "active_now", label: "Sessions actives", icon: "mdi-access-point", value: s.realtime.active_now,
      info: "Nombre de sessions au statut ACTIVE à l'instant présent pour le tenant courant. Reflète les utilisateurs actuellement connectés (hors pauses téléphoniques)." },
    { key: "unique_users", label: "Utilisateurs connectés", icon: "mdi-account-multiple", value: s.realtime.unique_users_connected,
      info: "Nombre d'utilisateurs distincts ayant au moins une session active. Un même utilisateur avec plusieurs onglets/appareils n'est compté qu'une fois." },
    { key: "peak", label: "Pic simultané", icon: "mdi-chart-bell-curve", value: s.realtime.peak_concurrent,
      info: "Maximum de sessions ouvertes en même temps sur la période sélectionnée, calculé par balayage des intervalles début/fin de chaque session." },
    { key: "paused", label: "Sessions en pause", icon: "mdi-pause-circle-outline", value: s.realtime.paused_now,
      info: "Sessions au statut PAUSED (pause téléphonique ESL). L'utilisateur reste authentifié mais momentanément indisponible." },
    { key: "logins", label: "Connexions", icon: "mdi-login", value: s.activity.logins_total,
      info: "Total des connexions réussies (LOGIN_SUCCESS) enregistrées sur la période, issues du journal d'audit." },
    { key: "avg_dur", label: "Durée moyenne", icon: "mdi-timer-outline", value: fmtDuration(s.activity.avg_duration_min),
      info: "Durée moyenne des sessions terminées sur la période (fin − début). Indique la durée typique d'utilisation continue." },
    { key: "med_dur", label: "Durée médiane", icon: "mdi-timer-sand", value: fmtDuration(s.activity.median_duration_min),
      info: "Durée médiane des sessions terminées : la moitié des sessions durent moins, l'autre moitié plus. Moins sensible aux valeurs extrêmes que la moyenne." },
    { key: "fail_rate", label: "Taux d'échec connexion", icon: "mdi-alert-circle-outline", value: s.security.failure_rate_pct + " %",
      alert: s.security.failure_rate_pct >= 30,
      info: "Part des tentatives de connexion en échec : LOGIN_FAILED / (LOGIN_SUCCESS + LOGIN_FAILED). Un taux élevé peut signaler des erreurs de mot de passe ou une attaque. (Limite : les tentatives sur des identifiants inexistants ne sont pas comptées.)" },
    { key: "lockouts", label: "Verrouillages", icon: "mdi-lock-alert", value: s.security.lockouts,
      alert: s.security.lockouts > 0,
      info: "Nombre de verrouillages temporaires déclenchés par l'anti-brute-force (trop de tentatives échouées sur un compte existant)." },
    { key: "expired", label: "Expirées (inactivité)", icon: "mdi-timer-off-outline", value: s.security.expired_inactivity,
      info: "Sessions terminées automatiquement pour inactivité au-delà du délai configuré (30 min). Détecté au refresh ou par la tâche de fond." },
    { key: "revoked", label: "Révoquées", icon: "mdi-account-cancel-outline", value: s.security.revoked,
      alert: s.security.revoked > 0,
      info: "Sessions coupées manuellement via la supervision (révocation à distance par un administrateur ou l'utilisateur lui-même)." },
  ];
});

const sessionByRole = computed(() => {
  const s = sessionStats.value;
  if (!s) return [];
  const entries = Object.entries(s.distribution.by_role);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return entries.map(([role, count]) => ({
    label: ROLE_LABELS[role] ?? role, count, pct: Math.round((count / max) * 100),
  }));
});

const sessionEndReasons = computed(() => {
  const s = sessionStats.value;
  if (!s) return [];
  const entries = Object.entries(s.distribution.end_reasons);
  const total = entries.reduce((a, [, v]) => a + v, 0) || 1;
  return entries
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({
      key: k, label: END_REASON_META[k]?.label ?? k, color: END_REASON_META[k]?.color ?? "#999",
      count: v, pct: Math.round((v / total) * 100),
    }));
});

const sessionPeakHours = computed(() => {
  const s = sessionStats.value;
  if (!s) return [];
  const max = Math.max(1, ...s.activity.peak_hours.map(h => h.count));
  return s.activity.peak_hours.map(h => ({ ...h, pct: Math.round((h.count / max) * 100) }));
});

const sessionLogins = computed(() => {
  const s = sessionStats.value;
  if (!s) return [];
  const max = Math.max(1, ...s.activity.logins_per_day.map(d => d.count));
  return s.activity.logins_per_day.map(d => ({ ...d, pct: Math.round((d.count / max) * 100) }));
});

const sessionTopIps = computed(() => sessionStats.value?.security.top_failed_ips ?? []);

function fmtDuration(min) {
  if (!min) return "0 min";
  if (min < 60) return `${Math.round(min)} min`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m ? `${h} h ${m}` : `${h} h`;
}

// ── Helpers ──────────────────────────────────────────────────────────

function isoWeek(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const y = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil((((d - y) / 86400000) + 1) / 7);
}

function initials(name) {
  if (!name) return "?";
  return name.split(" ").map(p => p[0] ?? "").join("").slice(0, 2).toUpperCase();
}

function completudeColor(pct) {
  if (pct >= 80) return "#27ae60";
  if (pct >= 50) return "#f39c12";
  return "#e74c3c";
}

function apexFont() {
  return { fontFamily: "Fira Code, monospace", fontSize: "9px", colors: "#aaa" };
}

// ── Period cutoff ─────────────────────────────────────────────────────

// Borne basse de la période (from). Priorité à la plage libre.
const cutoff = computed(() => {
  if (useCustomRange.value) {
    return customFrom.value ? new Date(customFrom.value + "T00:00:00") : null;
  }
  const now = new Date();
  if (filterPeriod.value === "today") {
    const d = new Date(now); d.setHours(0, 0, 0, 0); return d;
  }
  if (filterPeriod.value === "7j")  return new Date(now.getTime() - 7  * 86400000);
  if (filterPeriod.value === "30j") return new Date(now.getTime() - 30 * 86400000);
  if (filterPeriod.value === "3m")  return new Date(now.getTime() - 90 * 86400000);
  return null;
});

// Borne haute de la période (to). Uniquement en mode plage libre.
const rangeTo = computed(() => {
  if (useCustomRange.value && customTo.value) {
    return new Date(customTo.value + "T23:59:59");
  }
  return null;
});

// ── Client options ────────────────────────────────────────────────────

const allRaw = computed(() => [...rawAnomalies.value, ...rawCommandes.value]);

const clientOptions = computed(() => {
  const seen = new Map();
  allRaw.value.forEach(d => {
    if (d.client_id && d.client_nom && !seen.has(d.client_id))
      seen.set(d.client_id, d.client_nom);
  });
  return [...seen.entries()]
    .map(([id, nom]) => ({ id, nom }))
    .sort((a, b) => a.nom.localeCompare(b.nom));
});

// ── Filtered sets ─────────────────────────────────────────────────────

function applyFilters(list) {
  let d = list;
  if (cutoff.value) d = d.filter(x => new Date(x.created_at) >= cutoff.value);
  if (rangeTo.value) d = d.filter(x => new Date(x.created_at) <= rangeTo.value);
  if (filterClientId.value != null) d = d.filter(x => x.client_id === filterClientId.value);
  return d;
}

const filteredA   = computed(() => applyFilters(rawAnomalies.value));
const filteredC   = computed(() => applyFilters(rawCommandes.value));
const filteredAll = computed(() => [...filteredA.value, ...filteredC.value]);

// ══ PRISES DE SERVICE (vacations) ═════════════════════════════════════
// Filtré sur date_debut + client, cohérent avec la période globale.
const filteredPrises = computed(() => {
  let d = rawPrises.value;
  if (cutoff.value)  d = d.filter(x => new Date(x.date_debut) >= cutoff.value);
  if (rangeTo.value) d = d.filter(x => new Date(x.date_debut) <= rangeTo.value);
  if (filterClientId.value != null) d = d.filter(x => x.client_id === filterClientId.value);
  return d;
});

const vacationsKpis = computed(() => {
  const list = filteredPrises.value;
  const total = list.length;
  const enCours = list.filter(p => p.statut === "en_cours").length;
  const terminees = total - enCours;
  const done = list.filter(p => p.statut === "terminee");
  const avgMin = done.length
    ? Math.round(done.reduce((s, p) => s + (p.duree_minutes || 0), 0) / done.length)
    : 0;
  const avgTxt = avgMin ? `${Math.floor(avgMin / 60)}h ${String(avgMin % 60).padStart(2, "0")}` : "—";
  const agents = new Set(list.map(p => p.agent_id)).size;
  return [
    { icon: "mdi-clock-start",          label: "Prises de service", value: total },
    { icon: "mdi-progress-clock",       label: "En cours",          value: enCours, alert: enCours > 0 ? false : false },
    { icon: "mdi-check-circle-outline", label: "Terminées",         value: terminees },
    { icon: "mdi-timer-outline",        label: "Durée moyenne",     value: avgTxt },
    { icon: "mdi-shield-account-outline", label: "Agents actifs",   value: agents },
  ];
});

const vacationsByClient = computed(() => {
  const map = {};
  for (const p of filteredPrises.value) {
    const name = p.client_nom || `Client #${p.client_id}`;
    map[name] = (map[name] || 0) + 1;
  }
  return Object.entries(map).sort((a, b) => b[1] - a[1]).slice(0, 8);
});

// ══ PRODUCTION ════════════════════════════════════════════════════════

const productionKpis = computed(() => {
  const total    = filteredAll.value.length;
  const nA       = filteredA.value.length;
  const nC       = filteredC.value.length;
  const resolved = filteredAll.value.filter(d => ["resolue", "cloturee"].includes(d.statut)).length;
  const txRes    = total ? Math.round(resolved / total * 100) : 0;

  const withDelay = filteredAll.value.filter(d => d.date_resolution && d.created_at);
  const delai = withDelay.length
    ? Math.round(withDelay.reduce((s, d) =>
        s + (new Date(d.date_resolution) - new Date(d.created_at)) / 3600000, 0
      ) / withDelay.length * 10) / 10
    : 0;

  const budget = filteredC.value.reduce((s, c) => {
    const b = parseFloat(c.budget_estime);
    return s + (isNaN(b) ? 0 : b);
  }, 0);

  return [
    { icon: "mdi-alert-circle-outline",   label: "Anomalies",        value: nA,  alert: nA > 20 },
    { icon: "mdi-package-variant-outline", label: "Commandes",        value: nC },
    { icon: "mdi-check-circle-outline",   label: "Taux résolution",  value: `${txRes}%`,  alert: txRes < 50 },
    { icon: "mdi-clock-outline",          label: "Délai moyen",      value: delai ? `${delai}h` : "—" },
    { icon: "mdi-currency-eur",           label: "Budget commandes", value: budget > 0 ? `${Math.round(budget / 1000)}k€` : "—" },
  ];
});

// ── SLA (résolution) — calculé depuis le bloc `sla` de chaque demande ──────
const slaResolution = computed(() =>
  filteredAll.value
    .map((d) => d.sla?.resolution?.status)
    .filter(Boolean),
);

const slaKpis = computed(() => {
  const s = slaResolution.value;
  const met = s.filter((x) => x === "met").length;
  const missed = s.filter((x) => x === "missed").length;
  const breached = s.filter((x) => x === "breached").length;   // ouvertes hors délai
  const atRisk = s.filter((x) => x === "at_risk").length;
  const resolved = met + missed;
  const pct = resolved ? Math.round((met / resolved) * 100) : null;
  return [
    { icon: "mdi-check-decagram-outline", label: "Résolues dans les délais",
      value: pct == null ? "—" : `${pct}%`, alert: pct != null && pct < 80,
      sub: resolved ? `${met}/${resolved} résolues` : "aucune résolue",
      info: "Part des demandes résolues avant l'échéance SLA (met / met+missed)." },
    { icon: "mdi-timer-alert-outline", label: "Hors délai (en cours)",
      value: breached, alert: breached > 0,
      info: "Demandes ouvertes dont l'échéance de résolution est dépassée." },
    { icon: "mdi-progress-alert", label: "À risque",
      value: atRisk, alert: atRisk > 0,
      info: "Demandes ouvertes proches de l'échéance (≥ seuil d'alerte)." },
    { icon: "mdi-close-octagon-outline", label: "Résolues en retard",
      value: missed, alert: missed > 0,
      info: "Demandes résolues après l'échéance SLA." },
  ];
});

const slaByPriorite = computed(() => {
  const order = ["urgente", "haute", "normale", "basse"];
  const map = {};
  for (const d of filteredAll.value) {
    const st = d.sla?.resolution?.status;
    if (!st) continue;
    const p = d.priorite || "normale";
    map[p] ??= { priorite: p, total: 0, met: 0, missed: 0, breached: 0, at_risk: 0 };
    map[p].total++;
    if (st in map[p]) map[p][st]++;
  }
  return Object.values(map)
    .map((r) => ({ ...r, pct_on_time: (r.met + r.missed) ? Math.round((r.met / (r.met + r.missed)) * 100) : 0 }))
    .sort((a, b) => order.indexOf(a.priorite) - order.indexOf(b.priorite));
});

// ── Trend ─────────────────────────────────────────────────────────────

const trendBuckets = computed(() => {
  const use3m = ["3m", "all"].includes(filterPeriod.value);
  const n = filterPeriod.value === "today" ? 7
          : filterPeriod.value === "7j"    ? 7
          : filterPeriod.value === "30j"   ? 30
          : 13;

  const buckets = [];
  for (let i = n - 1; i >= 0; i--) {
    if (use3m) {
      const end   = new Date(Date.now() - i * 7 * 86400000);
      const start = new Date(end.getTime() - 7 * 86400000);
      buckets.push({ label: `S${isoWeek(end)}`, startMs: start.getTime(), endMs: end.getTime(), a: 0, c: 0 });
    } else {
      const s = new Date(Date.now() - i * 86400000);
      s.setHours(0, 0, 0, 0);
      buckets.push({
        label: s.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" }),
        startMs: s.getTime(),
        endMs: s.getTime() + 86400000,
        a: 0, c: 0,
      });
    }
  }

  filteredA.value.forEach(d => {
    const t = new Date(d.created_at).getTime();
    const b = buckets.find(b => t >= b.startMs && t < b.endMs);
    if (b) b.a++;
  });
  filteredC.value.forEach(d => {
    const t = new Date(d.created_at).getTime();
    const b = buckets.find(b => t >= b.startMs && t < b.endMs);
    if (b) b.c++;
  });

  return buckets;
});

const trendSeries = computed(() => [
  { name: "Anomalies", data: trendBuckets.value.map(b => b.a) },
  { name: "Commandes", data: trendBuckets.value.map(b => b.c) },
]);

const trendOptions = computed(() => ({
  chart: { type: "bar", toolbar: { show: false }, background: "transparent" },
  colors: ["#e74c3c", "#00a8a8"],
  plotOptions: { bar: { columnWidth: "60%", borderRadius: 2 } },
  xaxis: {
    categories: trendBuckets.value.map(b => b.label),
    labels: { rotate: -45, style: apexFont() },
    axisBorder: { show: false }, axisTicks: { show: false },
  },
  yaxis: { labels: { style: apexFont(), formatter: v => Math.round(v) }, min: 0 },
  grid: { borderColor: "rgba(0,0,0,0.05)", strokeDashArray: 4 },
  legend: { show: false },
  tooltip: { theme: "light", style: { fontFamily: "Fira Sans, sans-serif", fontSize: "11px" } },
  dataLabels: { enabled: false },
}));

// ── Statut donut ──────────────────────────────────────────────────────

const statutCounts = computed(() => {
  const c = {};
  filteredAll.value.forEach(d => { c[d.statut] = (c[d.statut] || 0) + 1; });
  return c;
});
const statutSeries  = computed(() => Object.values(statutCounts.value));
const statutOptions = computed(() => {
  const keys = Object.keys(statutCounts.value);
  return {
    labels:  keys.map(k => STATUT_META[k]?.label ?? k),
    colors:  keys.map(k => STATUT_META[k]?.color ?? "#999"),
    chart:   { type: "donut", toolbar: { show: false }, background: "transparent" },
    legend:  { position: "bottom", fontFamily: "Fira Sans, sans-serif", fontSize: "10px" },
    dataLabels: { style: { fontFamily: "Fira Code, monospace", fontSize: "10px" } },
    tooltip: { style: { fontFamily: "Fira Sans, sans-serif", fontSize: "11px" } },
    plotOptions: { pie: { donut: { size: "62%" } } },
  };
});

// ── Top clients ───────────────────────────────────────────────────────

const top5Clients = computed(() => {
  const c = {};
  filteredA.value.forEach(d => { if (d.client_nom) c[d.client_nom] = (c[d.client_nom] || 0) + 1; });
  return Object.entries(c).sort((a, b) => b[1] - a[1]).slice(0, 5);
});

const topClientsSeries  = computed(() => [{ name: "Anomalies", data: top5Clients.value.map(([, v]) => v) }]);
const topClientsOptions = computed(() => ({
  chart: { type: "bar", toolbar: { show: false }, background: "transparent" },
  colors: ["#e74c3c"],
  plotOptions: { bar: { horizontal: true, barHeight: "55%", borderRadius: 2 } },
  xaxis: {
    categories: top5Clients.value.map(([k]) => k),
    labels: { style: { fontFamily: "Fira Sans, sans-serif", fontSize: "10px", colors: "#555" } },
    axisBorder: { show: false }, axisTicks: { show: false },
  },
  yaxis: { labels: { style: apexFont(), formatter: v => Math.round(v) } },
  grid: { borderColor: "rgba(0,0,0,0.05)", strokeDashArray: 4 },
  tooltip: { theme: "light", style: { fontFamily: "Fira Sans, sans-serif", fontSize: "11px" } },
  dataLabels: { enabled: false },
  legend: { show: false },
}));

// ── Priorité donut ────────────────────────────────────────────────────

const prioriteCounts = computed(() => {
  const c = {};
  filteredAll.value.forEach(d => { c[d.priorite] = (c[d.priorite] || 0) + 1; });
  return c;
});
const prioriteSeries  = computed(() => Object.values(prioriteCounts.value));
const prioriteOptions = computed(() => {
  const keys = Object.keys(prioriteCounts.value);
  return {
    labels:  keys.map(k => PRIORITE_META[k]?.label ?? k),
    colors:  keys.map(k => PRIORITE_META[k]?.color ?? "#999"),
    chart:   { type: "donut", toolbar: { show: false }, background: "transparent" },
    legend:  { position: "bottom", fontFamily: "Fira Sans, sans-serif", fontSize: "10px" },
    dataLabels: { style: { fontFamily: "Fira Code, monospace", fontSize: "10px" } },
    tooltip: { style: { fontFamily: "Fira Sans, sans-serif", fontSize: "11px" } },
    plotOptions: { pie: { donut: { size: "62%" } } },
  };
});

// ══ AGENTS — KPI discriminants (source backend /agents/kpis) ═══════════
// Définitions stables : Anomalies = toutes les anomalies impliquant l'agent ;
// Incidents agent = sous-ensemble discriminant (impacte le score). Le calcul
// (discrimination par nature + impact_securite, malus) est fait côté backend.

const agentKpiRows    = ref([]);
const agentKpiLoading = ref(false);

async function loadAgentKpis() {
  agentKpiLoading.value = true;
  try {
    const { from, to } = periodRange();
    const { data } = await agentKpiService.getAgentsKpis({ from, to });
    agentKpiRows.value = data.agents ?? [];
  } catch {
    agentKpiRows.value = [];
  } finally {
    agentKpiLoading.value = false;
  }
}

watch(
  [activeTab, filterPeriod, customFrom, customTo],
  () => { if (activeTab.value === "agents") loadAgentKpis(); },
  { immediate: true },
);

function scoreColor(score) {
  return score >= 80 ? "green" : score >= 50 ? "orange" : "red";
}

// Classement : agents impliqués (≥1 anomalie), les plus à risque en tête (ordre backend).
const agentRanking = computed(() =>
  agentKpiRows.value
    .filter(a => a.anomalies > 0)
    .map(a => ({
      id: a.agent_id,
      nom: a.nom || a.matricule || `Agent #${a.agent_id}`,
      anomalies: a.anomalies,
      incidents: a.incidents,
      score: a.score,
      scoreColor: scoreColor(a.score),
    })),
);

const agentsKpis = computed(() => {
  const rows = agentKpiRows.value;
  const impliques = rows.filter(r => r.anomalies > 0);
  const incidentsTot = rows.reduce((s, r) => s + r.incidents, 0);
  const anomaliesTot = rows.reduce((s, r) => s + r.anomalies, 0);
  const worst = [...impliques].sort((a, b) => a.score - b.score)[0];
  return [
    { icon: "mdi-shield-account-outline", label: "Agents impliqués",        value: impliques.length },
    { icon: "mdi-alert",                  label: "Incidents (discriminants)", value: incidentsTot },
    { icon: "mdi-alert-circle-outline",   label: "Anomalies (toutes)",      value: anomaliesTot },
    { icon: "mdi-trending-down",          label: "Score le plus bas",       value: worst ? `${worst.score}/100` : "—",
      sub: worst ? (worst.nom || worst.matricule) : null },
  ];
});

// ══ PERMANENCIERS ══════════════════════════════════════════════════════

function completudeDemande(d) {
  const base = [d.titre, d.priorite, d.contact_id];
  const spec = d.type_demande === "anomalie" ? [d.nature_anomalie]
             : d.type_demande === "commande"  ? [d.type_commande]
             : [];
  const all = [...base, ...spec];
  return Math.round(all.filter(v => v != null && v !== "").length / all.length * 100);
}

const souffranceCutoffMs = Date.now() - SOUFFRANCE_DAYS * 86400000;

const permanencierGroups = computed(() => {
  const groups = new Map();
  filteredAll.value.forEach(d => {
    const uid  = d.created_by_id;
    const unom = d.created_by_nom  ?? `Utilisateur #${uid}`;
    const role = d.created_by_role ?? null;
    if (!uid) return;
    if (!groups.has(uid)) groups.set(uid, { id: uid, nom: unom, role, items: [] });
    groups.get(uid).items.push(d);
  });
  return [...groups.values()];
});

const permanencierRanking = computed(() =>
  permanencierGroups.value.map(g => {
    const total = g.items.length;
    const completude = total
      ? Math.round(g.items.reduce((s, d) => s + completudeDemande(d), 0) / total)
      : 0;
    const souffrance = g.items.filter(d =>
      !["resolue", "cloturee", "annulee"].includes(d.statut) &&
      new Date(d.created_at).getTime() < souffranceCutoffMs
    ).length;
    const withDelay = g.items.filter(d => d.date_resolution && d.created_at);
    const delai = withDelay.length
      ? Math.round(withDelay.reduce((s, d) =>
          s + (new Date(d.date_resolution) - new Date(d.created_at)) / 3600000, 0
        ) / withDelay.length * 10) / 10
      : 0;
    return { ...g, total, completude, souffrance, delai };
  }).sort((a, b) => b.total - a.total)
);

const permanenciersKpis = computed(() => {
  const actifs  = permanencierGroups.value.length;
  const soufTot = permanencierRanking.value.reduce((s, u) => s + u.souffrance, 0);
  const compMoy = actifs
    ? Math.round(permanencierRanking.value.reduce((s, u) => s + u.completude, 0) / actifs)
    : 0;
  return [
    { icon: "mdi-account-multiple-outline", label: "Opérateurs actifs",   value: actifs },
    { icon: "mdi-clipboard-check-outline",  label: "Complétude moyenne",  value: `${compMoy}%`, alert: compMoy < 70 },
    { icon: "mdi-timer-sand",               label: "Dossiers souffrance", value: soufTot,        alert: soufTot > 0,
      sub: soufTot > 0 ? `Ouverts > ${SOUFFRANCE_DAYS}j sans mise à jour` : null },
  ];
});
</script>

<style scoped>
/* ── Container ─────────────────────────────────────────────────────── */
.rp-container {
  background-color: #f2f2f2;
  font-family: "Fira Sans", sans-serif;
  min-height: 100%;
}

/* ── Filter bar ────────────────────────────────────────────────────── */
.rp-filter-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #555;
  white-space: nowrap;
}

.rp-status { display: flex; align-items: center; gap: 6px; }
.rp-status__dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.rp-status__dot--ok      { background: #27ae60; box-shadow: 0 0 0 2px rgba(39,174,96,0.2); }
.rp-status__dot--loading { background: #f39c12; animation: rp-pulse 1s ease-in-out infinite; }
@keyframes rp-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
.rp-status__lbl {
  font-family: "Fira Code", monospace;
  font-size: 9px; font-weight: 700; letter-spacing: 0.12em; color: #888; text-transform: uppercase;
}

/* ── Tabs ──────────────────────────────────────────────────────────── */
.rp-tabs {
  display: flex;
  gap: 2px;
  border-bottom: 2px solid rgba(0, 0, 0, 0.06);
}
.rp-tab {
  display: inline-flex;
  align-items: center;
  height: 36px;
  padding: 0 16px;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  background: transparent;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #888;
  text-transform: uppercase;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.rp-tab:hover { color: #000b23; }
.rp-tab--active { color: #00a8a8; border-bottom-color: #00a8a8; }

/* ── KPI cards ─────────────────────────────────────────────────────── */
.rp-kpi-card {
  border: 1px solid rgba(197, 198, 206, 0.15) !important;
  border-left: 3px solid #00a8a8 !important;
  height: 100%;
}
.rp-kpi-card--alert { border-left-color: #e74c3c !important; }
.rp-kpi-body { display: flex; flex-direction: column; gap: 6px; padding: 14px 14px 12px !important; }
.rp-kpi-top  { display: flex; align-items: center; gap: 6px; }
.rp-kpi-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.7rem; font-weight: 700; color: #555;
  text-transform: uppercase; letter-spacing: 0.07em; line-height: 1.2;
}
.rp-kpi-val {
  font-family: "Fira Code", monospace;
  font-size: 2.25rem; line-height: 1; font-weight: 500; color: #000b23;
}
.rp-kpi-val--alert { color: #e74c3c; }
.rp-kpi-sub { font-family: "Fira Sans", sans-serif; font-size: 0.65rem; color: #999; font-weight: 500; }

/* ── Chart cards ───────────────────────────────────────────────────── */
.rp-chart-card { border: 1px solid rgba(197, 198, 206, 0.15) !important; height: 100%; }
.rp-chart-hdr {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px 8px; flex-wrap: wrap; gap: 8px;
}
.rp-chart-title { font-family: "Fira Sans", sans-serif; font-size: 1rem; font-weight: 700; color: #000b23; }
.rp-chart-body  { padding: 4px 8px 8px !important; }
.rp-chart-empty { padding: 40px; text-align: center; color: #ccc; font-size: 12px; }

/* ── Legend ────────────────────────────────────────────────────────── */
.rp-chart-legend { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.rp-legend-item {
  display: flex; align-items: center; gap: 5px;
  font-family: "Fira Sans", sans-serif; font-size: 0.7rem; font-weight: 600;
  color: #555; text-transform: uppercase; letter-spacing: 0.06em;
}
.rp-legend-dot  { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }
.rp-score-dot   { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.rp-score-dot--green  { background: #27ae60; }
.rp-score-dot--orange { background: #f39c12; }
.rp-score-dot--red    { background: #e74c3c; }

/* ── Table ─────────────────────────────────────────────────────────── */
.rp-table { width: 100%; border-collapse: collapse; font-family: "Fira Sans", sans-serif; font-size: 12px; }
.rp-th {
  padding: 8px 12px; text-align: left;
  font-family: "Fira Sans", sans-serif; font-size: 0.65rem; font-weight: 800;
  color: #aaa; text-transform: uppercase; letter-spacing: 0.1em;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06); white-space: nowrap;
}
.rp-th--r { text-align: right; }
.rp-th--c { text-align: center; }
.rp-tr { border-bottom: 1px solid rgba(0, 0, 0, 0.04); }
.rp-tr:hover { background: rgba(0, 168, 168, 0.03); }
.rp-tr:last-child { border-bottom: none; }
.rp-td { padding: 10px 12px; color: #333; vertical-align: middle; }
.rp-td--mono { font-family: "Fira Code", monospace; font-size: 12px; }
.rp-td--r    { text-align: right; }
.rp-td--c    { text-align: center; }
.rp-td--rank { font-family: "Fira Code", monospace; font-size: 11px; color: #bbb; font-weight: 700; }
.rp-td--warn { color: #e74c3c; font-weight: 700; }
.rp-td-empty { padding: 28px; text-align: center; color: #bbb; font-size: 12px; font-style: italic; }

/* ── Person cell ───────────────────────────────────────────────────── */
.rp-cell-person { display: flex; align-items: center; gap: 8px; }
.rp-avatar {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: 4px; flex-shrink: 0;
  font-family: "Fira Code", monospace; font-size: 10px; font-weight: 700;
}
.rp-avatar--teal   { background: rgba(0,168,168,0.12);  color: #00a8a8; }
.rp-avatar--green  { background: rgba(39,174,96,0.12);  color: #27ae60; }
.rp-avatar--orange { background: rgba(243,156,18,0.12); color: #d68910; }
.rp-avatar--red    { background: rgba(231,76,60,0.12);  color: #e74c3c; }
.rp-person-name { font-size: 12px; font-weight: 600; color: #222; }

/* ── Score badge ───────────────────────────────────────────────────── */
.rp-score {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 36px; height: 22px; border-radius: 3px; padding: 0 6px;
  font-family: "Fira Code", monospace; font-size: 11px; font-weight: 700;
}
.rp-score--green  { background: rgba(39,174,96,0.12);  color: #27ae60; }
.rp-score--orange { background: rgba(243,156,18,0.12); color: #d68910; }
.rp-score--red    { background: rgba(231,76,60,0.12);  color: #e74c3c; }

/* ── Trend ─────────────────────────────────────────────────────────── */
.rp-trend {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 3px;
  font-size: 13px; font-weight: 700;
}
.rp-trend--up     { background: rgba(231,76,60,0.1);  color: #e74c3c; }
.rp-trend--down   { background: rgba(39,174,96,0.1);  color: #27ae60; }
.rp-trend--stable { background: rgba(0,0,0,0.05);     color: #aaa; }

/* ── Role badge ────────────────────────────────────────────────────── */
.rp-role-badge {
  display: inline-flex; align-items: center; height: 20px; padding: 0 6px;
  border-radius: 3px; background: rgba(0,11,35,0.06);
  font-family: "Fira Code", monospace; font-size: 9px; font-weight: 700;
  color: #555; text-transform: uppercase; letter-spacing: 0.06em;
}

/* ── Completude bar ────────────────────────────────────────────────── */
.rp-completude { display: flex; align-items: center; gap: 8px; }
.rp-bar-track  { flex: 1; height: 6px; background: rgba(0,0,0,0.06); border-radius: 3px; overflow: hidden; }
.rp-bar-fill   { height: 100%; border-radius: 3px; transition: width 0.5s ease; min-width: 2px; }
.rp-completude-pct { font-family: "Fira Code", monospace; font-size: 11px; min-width: 34px; text-align: right; color: #555; }
</style>
