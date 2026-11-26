<script setup lang="ts">
import type { Agent } from "~/utils/agent";
import { sortAgentsByGradeAndArrival } from "~/utils/agent";
import ConfirmDialog from "~/components/ConfirmDialog.vue";
import ShareDialog from "~/components/ShareDialog.vue";
import { useAppToast } from "~/composables/useAppToast";

definePageMeta({ layout: "dispatch" });
useHead({ title: "Ressources humaines • BCES" });

interface AccountOption {
  id: number;
  name: string;
  discord_username: string;
}

interface GradeOption {
  id: number;
  name: string;
  level: number;
  color: string;
}

interface CurrentUser {
  is_super_admin: boolean;
  /** Droits donnés par les formations (et droits RH de la Direction). */
  training_permissions: string[];
}

const requestHeaders = import.meta.server
  ? useRequestHeaders(["cookie"])
  : undefined;
const { data: currentUser } = await useAsyncData("hr-current-user", () =>
  $fetch<CurrentUser>("/api/me", {
    credentials: "include",
    headers: requestHeaders,
  }),
);
/** Le droit RH (formation ou Direction) permet toutes les actions de la page. */
const isHr = computed(() =>
  Boolean(
    currentUser.value?.is_super_admin ||
    currentUser.value?.training_permissions.includes("human_resources.manage"),
  ),
);
const canManageEmployees = isHr;
const canLinkAccounts = isHr;
const [{ data: initialEmployees }, { data: initialGrades }] = await Promise.all(
  [
    useAsyncData("hr-employees", () =>
      $fetch<Agent[]>("/api/employees", {
        credentials: "include",
        headers: requestHeaders,
      }),
    ),
    useAsyncData("hr-grades", () =>
      $fetch<GradeOption[]>("/api/employee-grades", {
        credentials: "include",
        headers: requestHeaders,
      }),
    ),
  ],
);
const { data: accounts } = await useAsyncData("hr-accounts", () =>
  canLinkAccounts.value
    ? $fetch<AccountOption[]>("/api/employee-accounts", {
        credentials: "include",
        headers: requestHeaders,
      })
    : Promise.resolve([]),
);

const employees = ref<Agent[]>(initialEmployees.value ?? []);
const accountOptions = accounts.value ?? [];
const grades = initialGrades.value ?? [];
const actionError = ref("");
const employeeDialogError = ref("");
const savingEmployee = ref(false);
const workingEmployeeIds = ref<number[]>([]);
const editingEmployeeId = ref<number | null>(null);
const employeeDialogVisible = ref(false);
const deleteConfirmVisible = ref(false);
const employeeToDelete = ref<Agent | null>(null);
const search = ref("");
const showInactive = ref(false);
const revealedEmails = ref<number[]>([]);
const employeeForm = reactive({
  first_name: "",
  last_name: "",
  phone: "",
  email: "",
  arrival_date: "",
  gender: "" as "" | "homme" | "femme" | "autre",
  birth_date: "",
  diploma: false,
  boat_license: false,
  boat_license_date: "",
  helicopter_license: false,
  helicopter_license_date: "",
  grade_id: "",
  account_id: "",
});

const visibleEmployees = computed(() => {
  const query = search.value.trim().toLocaleLowerCase("fr");
  return sortAgentsByGradeAndArrival(
    employees.value.filter((employee) => {
      if (!showInactive.value && !employee.is_active) return false;
      const text = [
        employee.first_name,
        employee.last_name,
        employee.phone,
        employee.email,
        employee.account_username,
        employee.grade_name,
        ...employee.competencies,
      ]
        .join(" ")
        .toLocaleLowerCase("fr");
      return !query || text.includes(query);
    }),
  );
});
const maleEmployeeCount = computed(
  () =>
    employees.value.filter((employee) => employee.gender === "homme").length,
);
const femaleEmployeeCount = computed(
  () =>
    employees.value.filter((employee) => employee.gender === "femme").length,
);
const otherGenderEmployeeCount = computed(
  () =>
    employees.value.filter((employee) => employee.gender === "autre").length,
);
const averageAge = computed(() => {
  const ages = employees.value
    .map((employee) => ageFromBirthDate(employee.birth_date))
    .filter((age): age is number => age !== null);
  return ages.length
    ? Number((ages.reduce((sum, age) => sum + age, 0) / ages.length).toFixed(1))
    : null;
});
const averageAgeDisplay = computed(() =>
  averageAge.value === null
    ? "—"
    : `${averageAge.value.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ans`,
);
const employeesWithBirthDateCount = computed(
  () =>
    employees.value.filter(
      (employee) => ageFromBirthDate(employee.birth_date) !== null,
    ).length,
);
const gradeDistribution = computed(() => {
  const byGrade = new Map<
    string,
    {
      key: string;
      name: string;
      level: number | null;
      count: number;
      color: string | null;
    }
  >();
  for (const employee of employees.value) {
    const key =
      employee.grade_id === null ? "unassigned" : String(employee.grade_id);
    const grade = byGrade.get(key);
    if (grade) grade.count += 1;
    else {
      byGrade.set(key, {
        key,
        name: employee.grade_name || "Sans grade",
        level: employee.grade_level,
        count: 1,
        color:
          employee.grade_color ??
          (employee.grade_id === null ? "#68737e" : "#46996d"),
      });
    }
  }
  return [...byGrade.values()]
    .sort((a, b) => {
      if (a.level === null)
        return b.level === null ? a.name.localeCompare(b.name, "fr") : 1;
      if (b.level === null) return -1;
      return a.level - b.level || a.name.localeCompare(b.name, "fr");
    })
    .map((grade) => ({
      ...grade,
      percent: employees.value.length
        ? (grade.count / employees.value.length) * 100
        : 0,
    }));
});

function messageFromError(cause: unknown, fallback: string) {
  if (typeof cause === "object" && cause !== null && "data" in cause) {
    const data = cause.data;
    if (typeof data === "object" && data !== null && "detail" in data) {
      const detail = data.detail;
      if (typeof detail === "string") {
        return detail;
      }
      if (Array.isArray(detail)) {
        // Erreurs de validation FastAPI 422 (liste de détails)
        const messages = detail
          .filter((e: any) => e && typeof e.msg === "string")
          .map((e: any) => e.msg)
          .filter(Boolean);
        if (messages.length > 0) {
          return messages.join(" · ");
        }
      }
    }
  }
  return fallback;
}

function resetEmployeeForm() {
  editingEmployeeId.value = null;
  employeeForm.first_name = "";
  employeeForm.last_name = "";
  employeeForm.phone = "";
  employeeForm.email = "";
  employeeForm.arrival_date = "";
  employeeForm.gender = "";
  employeeForm.birth_date = "";
  employeeForm.diploma = false;
  employeeForm.boat_license = false;
  employeeForm.boat_license_date = "";
  employeeForm.helicopter_license = false;
  employeeForm.helicopter_license_date = "";
  employeeForm.grade_id = "";
  employeeForm.account_id = "";
}

async function openEmployeeDialog(employee?: Agent) {
  resetEmployeeForm();
  employeeDialogError.value = "";
  if (employee) {
    editingEmployeeId.value = employee.id;
    employeeForm.first_name = employee.first_name;
    employeeForm.last_name = employee.last_name;
    employeeForm.phone = employee.phone ?? "";
    employeeForm.email = employee.email ?? "";
    employeeForm.arrival_date = employee.arrival_date ?? "";
    employeeForm.gender = employee.gender ?? "";
    employeeForm.birth_date = employee.birth_date ?? "";
    employeeForm.diploma = employee.diploma;
    employeeForm.boat_license = employee.boat_license;
    employeeForm.boat_license_date = employee.boat_license_date ?? "";
    employeeForm.helicopter_license = employee.helicopter_license;
    employeeForm.helicopter_license_date =
      employee.helicopter_license_date ?? "";
    employeeForm.grade_id = employee.grade_id ? String(employee.grade_id) : "";
    employeeForm.account_id = employee.account_user_id
      ? String(employee.account_user_id)
      : "";
  }
  actionError.value = "";
  employeeDialogVisible.value = true;
  await nextTick();
}

function closeEmployeeDialog() {
  if (savingEmployee.value) return;
  employeeDialogVisible.value = false;
}

function onEmployeeDialogVisibleChange(visible: boolean) {
  if (!visible) {
    employeeDialogError.value = "";
  }
}

function onEmployeeDialogClose() {
  resetEmployeeForm();
  employeeDialogError.value = "";
}

async function saveEmployee() {
  if (savingEmployee.value) return;
  employeeDialogError.value = "";
  savingEmployee.value = true;
  const payload = {
    first_name: employeeForm.first_name.trim(),
    last_name: employeeForm.last_name.trim(),
    phone: employeeForm.phone.trim() || null,
    email: employeeForm.email.trim() || null,
    arrival_date: employeeForm.arrival_date || null,
    gender: employeeForm.gender || null,
    birth_date: employeeForm.birth_date || null,
    diploma: employeeForm.diploma,
    boat_license: employeeForm.boat_license,
    boat_license_date:
      employeeForm.boat_license && employeeForm.boat_license_date
        ? employeeForm.boat_license_date
        : null,
    helicopter_license: employeeForm.helicopter_license,
    helicopter_license_date:
      employeeForm.helicopter_license && employeeForm.helicopter_license_date
        ? employeeForm.helicopter_license_date
        : null,
    grade_id: employeeForm.grade_id ? Number(employeeForm.grade_id) : null,
    account_user_id: employeeForm.account_id
      ? Number(employeeForm.account_id)
      : null,
  };
  try {
    const saved = editingEmployeeId.value
      ? await $fetch<Agent>(`/api/employees/${editingEmployeeId.value}`, {
          method: "PATCH",
          body: payload,
          credentials: "include",
        })
      : await $fetch<Agent>("/api/employees", {
          method: "POST",
          body: payload,
          credentials: "include",
        });
    const existingIndex = employees.value.findIndex(
      (employee) => employee.id === saved.id,
    );
    if (existingIndex < 0) employees.value.push(saved);
    else employees.value.splice(existingIndex, 1, saved);
    employeeDialogVisible.value = false;
  } catch (cause) {
    employeeDialogError.value = messageFromError(
      cause,
      "Enregistrement de l’employé impossible.",
    );
  } finally {
    savingEmployee.value = false;
  }
}

async function copyEmail(email: string) {
  const toast = useAppToast();
  try {
    await navigator.clipboard.writeText(email);
    toast.success("E-mail copié dans le presse-papier.");
  } catch {
    // fallback pour les navigateurs qui ne supportent pas clipboard API
    const textarea = document.createElement("textarea");
    textarea.value = email;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "absolute";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
    toast.success("E-mail copié dans le presse-papier.");
  }
}

function formatDateFr(value: string | null) {
  if (!value) return "";
  const [year, month, day] = value.slice(0, 10).split("-");
  return `${day}/${month}/${year}`;
}

function todayDateInput() {
  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${today.getFullYear()}-${month}-${day}`;
}

function ageFromBirthDate(value: string | null) {
  if (!value) return null;
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  if (!year || !month || !day) return null;
  const today = new Date();
  let age = today.getFullYear() - year;
  const birthdayThisYear = new Date(today.getFullYear(), month - 1, day);
  if (birthdayThisYear.getMonth() !== month - 1) birthdayThisYear.setDate(0);
  if (today < birthdayThisYear) age -= 1;
  return age >= 0 ? age : null;
}

function formatArrivalDate(value: string | null) {
  if (!value) return "Date d’arrivée non renseignée";
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  const arrival = Date.UTC(year, month - 1, day);
  const today = new Date();
  const todayUtc = Date.UTC(
    today.getFullYear(),
    today.getMonth(),
    today.getDate(),
  );
  const days = Math.floor((todayUtc - arrival) / 86_400_000);
  const duration =
    days >= 0
      ? `${days} jour${days > 1 ? "s" : ""}`
      : `dans ${Math.abs(days)} jour${Math.abs(days) > 1 ? "s" : ""}`;
  return `Arrivée le ${formatDateFr(value)} · ${duration}`;
}

async function setEmployeeActive(employee: Agent) {
  if (workingEmployeeIds.value.includes(employee.id)) return;
  actionError.value = "";
  workingEmployeeIds.value.push(employee.id);
  try {
    const updated = await $fetch<Agent>(`/api/employees/${employee.id}`, {
      method: "PATCH",
      body: { is_active: !employee.is_active },
      credentials: "include",
    });
    employees.value.splice(
      employees.value.findIndex((item) => item.id === updated.id),
      1,
      updated,
    );
  } catch (cause) {
    actionError.value = messageFromError(
      cause,
      "Changement de statut impossible.",
    );
  } finally {
    workingEmployeeIds.value = workingEmployeeIds.value.filter(
      (id) => id !== employee.id,
    );
  }
}

function deleteEmployee(employee: Agent) {
  if (workingEmployeeIds.value.includes(employee.id)) return;
  employeeToDelete.value = employee;
  deleteConfirmVisible.value = true;
}

async function confirmDeleteEmployee() {
  const employee = employeeToDelete.value;
  if (!employee) return;
  if (workingEmployeeIds.value.includes(employee.id)) return;
  actionError.value = "";
  workingEmployeeIds.value.push(employee.id);
  try {
    await $fetch(`/api/employees/${employee.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    employees.value = employees.value.filter((item) => item.id !== employee.id);
    if (editingEmployeeId.value === employee.id) closeEmployeeDialog();
  } catch (cause) {
    actionError.value = messageFromError(
      cause,
      "Suppression de l’employé impossible.",
    );
  } finally {
    workingEmployeeIds.value = workingEmployeeIds.value.filter(
      (id) => id !== employee.id,
    );
    employeeToDelete.value = null;
    deleteConfirmVisible.value = false;
  }
}
</script>

<template>
  <main class="hr-page">
    <header class="hr-header">
      <div class="hr-header__top">
        <div class="hr-header__intro">
          <p class="hr-eyebrow"><span></span> BCES <b>/</b> ÉQUIPE</p>
          <h1>Ressources humaines</h1>
          <p>Gérez les employés, leurs compétences et leur grade de service.</p>
        </div>
        <div class="hr-overview" aria-label="Effectif par genre et âge moyen">
          <article class="hr-stat hr-stat--total">
            <span class="hr-stat__icon"
              ><Icon name="lucide:users-round" size="18"
            /></span>
            <span class="hr-stat__value"
              ><strong>{{ employees.length }}</strong
              ><small>Total</small></span
            >
          </article>
          <article class="hr-stat hr-stat--male">
            <span class="hr-stat__icon"
              ><Icon name="lucide:mars" size="18"
            /></span>
            <span class="hr-stat__value"
              ><strong>{{ maleEmployeeCount }}</strong
              ><small>Homme</small></span
            >
          </article>
          <article class="hr-stat hr-stat--female">
            <span class="hr-stat__icon"
              ><Icon name="lucide:venus" size="18"
            /></span>
            <span class="hr-stat__value"
              ><strong>{{ femaleEmployeeCount }}</strong
              ><small>Femme</small></span
            >
          </article>
          <article
            v-if="otherGenderEmployeeCount > 0"
            class="hr-stat hr-stat--other"
          >
            <span class="hr-stat__icon"
              ><Icon name="lucide:users-round" size="18"
            /></span>
            <span class="hr-stat__value"
              ><strong>{{ otherGenderEmployeeCount }}</strong
              ><small>Autre</small></span
            >
          </article>
          <article
            class="hr-stat hr-stat--age"
            :title="`Âge moyen calculé sur ${employeesWithBirthDateCount} date${employeesWithBirthDateCount > 1 ? 's' : ''} de naissance`"
          >
            <span class="hr-stat__icon"
              ><Icon name="lucide:cake" size="18"
            /></span>
            <span class="hr-stat__value"
              ><strong>{{ averageAgeDisplay }}</strong
              ><small>Moyen d’âge</small></span
            >
          </article>
        </div>
      </div>
      <section
        class="hr-grade-summary"
        aria-label="Répartition de l’effectif par grade"
      >
        <div class="hr-grade-summary__heading">
          <span class="hr-grade-summary__icon"
            ><Icon name="lucide:chart-no-axes-column-increasing" size="17"
          /></span>
          <div class="hr-grade-summary__title">
            <span>STRUCTURE DE L’EFFECTIF</span>
            <h2>Répartition par grade</h2>
          </div>
          <span class="hr-grade-summary__total"
            >{{ employees.length }} employé{{
              employees.length > 1 ? "s" : ""
            }}</span
          >
        </div>
        <template v-if="gradeDistribution.length">
          <div
            class="hr-grade-summary__stack"
            role="img"
            :aria-label="`Répartition des ${employees.length} employés par grade`"
          >
            <span
              v-for="grade in gradeDistribution"
              :key="grade.key"
              :title="`${grade.name} : ${grade.percent.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`"
              :style="{
                width: `${grade.percent}%`,
                backgroundColor: grade.color || '#68737e',
              }"
            ></span>
          </div>
          <div class="hr-grade-summary__list">
            <div
              v-for="grade in gradeDistribution"
              :key="grade.key"
              class="hr-grade-stat"
              :style="{ '--hr-stat-color': grade.color || '#68737e' }"
            >
              <div class="hr-grade-stat__label">
                <span class="hr-grade-stat__name"><i></i>{{ grade.name }}</span>
                <strong
                  >{{
                    grade.percent.toLocaleString("fr-FR", {
                      maximumFractionDigits: 1,
                    })
                  }}
                  %</strong
                >
              </div>
              <small
                >{{ grade.count }} employé{{
                  grade.count > 1 ? "s" : ""
                }}</small
              >
            </div>
          </div>
        </template>
        <p v-else class="hr-grade-summary__empty">
          Aucun employé à répartir par grade.
        </p>
      </section>
    </header>

    <div v-if="actionError" class="hr-error" role="alert">
      <Icon name="lucide:circle-alert" size="17" />
      <span>{{ actionError }}</span>
      <button type="button" aria-label="Fermer" @click="actionError = ''">
        <Icon name="lucide:x" size="15" />
      </button>
    </div>

    <section class="hr-section">
      <div class="hr-section__heading">
        <div class="hr-section__title">
          <h2>Employés</h2>
          <p>
            Les employés peuvent être ajoutés avant d’avoir un compte
            utilisateur.
          </p>
        </div>
        <div class="hr-section__tools">
          <label class="hr-filter">
            <Icon name="lucide:search" size="15" />
            <input
              v-model="search"
              type="search"
              aria-label="Rechercher dans les employés"
              placeholder="Nom, compétence, grade…"
            />
          </label>
          <button
            v-if="canManageEmployees"
            type="button"
            class="hr-primary hr-add"
            @click="openEmployeeDialog()"
          >
            <Icon name="lucide:plus" size="17" /> Ajouter
          </button>
        </div>
      </div>

      <ShareDialog
        v-if="canManageEmployees"
        v-model:visible="employeeDialogVisible"
        :title="
          editingEmployeeId ? 'Modifier un employé' : 'Ajouter un employé'
        "
        :error="employeeDialogError"
        confirm-label="Enregistrer"
        cancel-label="Annuler"
        @confirm="saveEmployee"
        @update:visible="onEmployeeDialogVisibleChange"
      >
        <template #content>
          <div class="hr-employee-form">
            <section class="hr-form-block">
              <header class="hr-form-block__heading">
                <span class="hr-form-block__icon"
                  ><Icon name="lucide:user-round" size="16"
                /></span>
                <div>
                  <h3>Informations personnelles</h3>
                  <p>Identité et coordonnées de l’employé.</p>
                </div>
              </header>
              <div class="hr-form-grid">
                <label>
                  <span>Prénom <i>*</i></span>
                  <input
                    v-model="employeeForm.first_name"
                    required
                    maxlength="64"
                    autocomplete="given-name"
                  />
                </label>
                <label>
                  <span>Nom</span>
                  <input
                    v-model="employeeForm.last_name"
                    maxlength="64"
                    autocomplete="family-name"
                  />
                </label>
                <label>
                  <span>Téléphone</span>
                  <input
                    v-model="employeeForm.phone"
                    maxlength="20"
                    autocomplete="tel"
                  />
                </label>
                <label>
                  <span>E-mail</span>
                  <input
                    v-model="employeeForm.email"
                    type="email"
                    maxlength="254"
                    autocomplete="email"
                  />
                </label>
                <label>
                  <span>Sexe</span>
                  <select v-model="employeeForm.gender">
                    <option value="">Non renseigné</option>
                    <option value="homme">Homme</option>
                    <option value="femme">Femme</option>
                    <option value="autre">Autre</option>
                  </select>
                </label>
                <label>
                  <span>Date de naissance</span>
                  <input
                    v-model="employeeForm.birth_date"
                    type="date"
                    :max="todayDateInput()"
                  />
                  <small
                    v-if="ageFromBirthDate(employeeForm.birth_date) !== null"
                    class="hr-field-note"
                  >
                    {{ ageFromBirthDate(employeeForm.birth_date) }} ans
                  </small>
                </label>
              </div>
            </section>

            <section class="hr-form-block">
              <header class="hr-form-block__heading">
                <span class="hr-form-block__icon"
                  ><Icon name="lucide:badge-check" size="16"
                /></span>
                <div>
                  <h3>Qualifications</h3>
                  <p>Diplôme obtenu et licences détenues par l’employé.</p>
                </div>
              </header>
              <div class="hr-qualification-grid">
                <label
                  class="hr-qualification hr-qualification--diploma"
                  :class="{ 'is-checked': employeeForm.diploma }"
                >
                  <span class="hr-qualification__symbol"
                    ><Icon name="lucide:graduation-cap" size="18"
                  /></span>
                  <span class="hr-qualification__copy"
                    ><strong>Diplôme obtenu</strong
                    ><small>{{
                      employeeForm.diploma
                        ? "Diplôme renseigné"
                        : "Aucun diplôme renseigné"
                    }}</small></span
                  >
                  <span class="hr-switch">
                    <input
                      v-model="employeeForm.diploma"
                      type="checkbox"
                      aria-label="Diplôme obtenu"
                    />
                    <span class="hr-switch__track" aria-hidden="true"></span>
                  </span>
                </label>

                <article
                  class="hr-license"
                  :class="{ 'is-checked': employeeForm.boat_license }"
                >
                  <header class="hr-license__header">
                    <span class="hr-qualification__symbol"
                      ><Icon name="lucide:ship" size="18"
                    /></span>
                    <div class="hr-qualification__copy">
                      <h4>Licence bateau</h4>
                      <small>{{
                        employeeForm.boat_license
                          ? "Licence détenue"
                          : "Aucune licence renseignée"
                      }}</small>
                    </div>
                    <label class="hr-switch">
                      <input
                        v-model="employeeForm.boat_license"
                        type="checkbox"
                        aria-label="Licence bateau détenue"
                      />
                      <span class="hr-switch__track" aria-hidden="true"></span>
                    </label>
                  </header>
                  <label
                    v-if="employeeForm.boat_license"
                    class="hr-license__date"
                  >
                    <span>Date d’obtention</span>
                    <input
                      v-model="employeeForm.boat_license_date"
                      type="date"
                    />
                  </label>
                  <p v-else class="hr-license__hint">
                    Active la licence pour ajouter sa date.
                  </p>
                </article>

                <article
                  class="hr-license"
                  :class="{ 'is-checked': employeeForm.helicopter_license }"
                >
                  <header class="hr-license__header">
                    <span class="hr-qualification__symbol"
                      ><Icon name="lucide:helicopter" size="18"
                    /></span>
                    <div class="hr-qualification__copy">
                      <h4>Licence hélicoptère</h4>
                      <small>{{
                        employeeForm.helicopter_license
                          ? "Licence détenue"
                          : "Aucune licence renseignée"
                      }}</small>
                    </div>
                    <label class="hr-switch">
                      <input
                        v-model="employeeForm.helicopter_license"
                        type="checkbox"
                        aria-label="Licence hélicoptère détenue"
                      />
                      <span class="hr-switch__track" aria-hidden="true"></span>
                    </label>
                  </header>
                  <label
                    v-if="employeeForm.helicopter_license"
                    class="hr-license__date"
                  >
                    <span>Date d’obtention</span>
                    <input
                      v-model="employeeForm.helicopter_license_date"
                      type="date"
                    />
                  </label>
                  <p v-else class="hr-license__hint">
                    Active la licence pour ajouter sa date.
                  </p>
                </article>
              </div>
            </section>

            <section class="hr-form-block">
              <header class="hr-form-block__heading">
                <span class="hr-form-block__icon"
                  ><Icon name="lucide:landmark" size="16"
                /></span>
                <div>
                  <h3>Ancienneté et affectation</h3>
                  <p>Date d’arrivée, grade et compte associé.</p>
                </div>
              </header>
              <div class="hr-form-grid">
                <label>
                  <span>Date d’arrivée</span>
                  <input v-model="employeeForm.arrival_date" type="date" />
                </label>
                <label>
                  <span>Grade</span>
                  <select v-model="employeeForm.grade_id">
                    <option value="">Aucun grade</option>
                    <option
                      v-for="grade in grades"
                      :key="grade.id"
                      :value="String(grade.id)"
                    >
                      {{ grade.name }} · niveau {{ grade.level }}
                    </option>
                  </select>
                </label>
                <label
                  v-if="canLinkAccounts && editingEmployeeId"
                  class="hr-form-grid__wide"
                >
                  <span>Compte associé</span>
                  <select v-model="employeeForm.account_id">
                    <option value="">Aucun compte lié</option>
                    <option
                      v-for="account in accountOptions"
                      :key="account.id"
                      :value="String(account.id)"
                    >
                      {{ account.name }} · {{ account.discord_username }}
                    </option>
                  </select>
                </label>
              </div>
            </section>
          </div>
        </template>
      </ShareDialog>

      <div class="hr-list__toolbar">
        <span
          >{{ visibleEmployees.length }} résultat{{
            visibleEmployees.length > 1 ? "s" : ""
          }}
          sur {{ employees.length }}</span
        >
        <label
          ><input v-model="showInactive" type="checkbox" /> Afficher les
          inactifs</label
        >
      </div>
      <div v-if="visibleEmployees.length" class="hr-list">
        <article
          v-for="employee in visibleEmployees"
          :key="employee.id"
          class="hr-employee"
          :class="{ 'is-inactive': !employee.is_active }"
          :style="
            employee.grade_color
              ? { '--hr-grade-color': employee.grade_color }
              : undefined
          "
        >
          <div class="hr-employee__avatar">
            <Icon name="lucide:user-round" size="19" />
          </div>
          <div class="hr-employee__main">
            <div class="hr-employee__name">
              <h3>{{ employee.first_name }} {{ employee.last_name }}</h3>
              <span
                class="hr-status"
                :class="{ 'is-inactive': !employee.is_active }"
                >{{ employee.is_active ? "Actif" : "Inactif" }}</span
              >
            </div>
            <div class="hr-employee__meta">
              <span class="hr-meta-item">
                <Icon name="lucide:phone" size="11" />
                {{ employee.phone || "Pas de téléphone" }}
              </span>
              <span
                v-if="employee.email"
                class="hr-meta-item hr-meta-item--email"
              >
                <Icon name="lucide:mail" size="11" />
                <span
                  class="hr-email-blur"
                  :class="{
                    'hr-email-revealed': revealedEmails.includes(employee.id),
                  }"
                  @mouseenter="
                    revealedEmails.value = (
                      revealedEmails.value || []
                    ).includes(employee.id)
                      ? revealedEmails.value || []
                      : [...(revealedEmails.value || []), employee.id]
                  "
                  @mouseleave="
                    revealedEmails.value = (revealedEmails.value || []).filter(
                      (id) => id !== employee.id,
                    )
                  "
                  @click="copyEmail(employee.email)"
                  style="cursor: pointer"
                >
                  {{ employee.email }}
                </span>
              </span>
              <span v-else class="hr-meta-item">
                <Icon name="lucide:mail" size="11" />
                Aucun e-mail
              </span>
              <span
                v-if="employee.grade_name"
                class="hr-meta-item hr-meta-item--grade"
              >
                <Icon name="lucide:award" size="11" />
                {{ employee.grade_name }}
              </span>
              <span class="hr-meta-item">
                <Icon name="lucide:calendar" size="11" />
                {{ formatArrivalDate(employee.arrival_date) }}
              </span>
              <span v-if="employee.gender" class="hr-meta-item">
                <Icon
                  :name="
                    employee.gender === 'homme'
                      ? 'lucide:mars'
                      : employee.gender === 'femme'
                        ? 'lucide:venus'
                        : 'lucide:users-round'
                  "
                  size="11"
                />
                {{
                  employee.gender === "homme"
                    ? "Homme"
                    : employee.gender === "femme"
                      ? "Femme"
                      : "Autre"
                }}
              </span>
              <span v-if="employee.birth_date" class="hr-meta-item">
                <Icon name="lucide:cake" size="11" />
                {{ formatDateFr(employee.birth_date)
                }}<template
                  v-if="ageFromBirthDate(employee.birth_date) !== null"
                >
                  · {{ ageFromBirthDate(employee.birth_date) }} ans</template
                >
              </span>
              <span v-if="employee.diploma" class="hr-meta-item"
                ><Icon name="lucide:graduation-cap" size="11" /> Diplôme</span
              >
              <span v-if="employee.boat_license" class="hr-meta-item">
                <Icon name="lucide:ship" size="11" /> Bateau<template
                  v-if="employee.boat_license_date"
                >
                  · {{ formatDateFr(employee.boat_license_date) }}</template
                >
              </span>
              <span v-if="employee.helicopter_license" class="hr-meta-item">
                <Icon name="lucide:helicopter" size="11" /> Hélicoptère<template
                  v-if="employee.helicopter_license_date"
                >
                  ·
                  {{ formatDateFr(employee.helicopter_license_date) }}</template
                >
              </span>
              <span class="hr-meta-item">
                <Icon name="lucide:user-check" size="11" />
                {{
                  employee.account_username
                    ? `Compte : ${employee.account_username}`
                    : "Sans compte lié"
                }}
              </span>
            </div>
          </div>
          <div v-if="canManageEmployees" class="hr-employee__actions">
            <button
              type="button"
              :aria-label="`Modifier ${employee.first_name}`"
              title="Modifier"
              :disabled="workingEmployeeIds.includes(employee.id)"
              @click="openEmployeeDialog(employee)"
            >
              <Icon name="lucide:pencil" size="16" />
            </button>
            <button
              type="button"
              :aria-label="employee.is_active ? 'Désactiver' : 'Réactiver'"
              :title="employee.is_active ? 'Désactiver' : 'Réactiver'"
              :disabled="workingEmployeeIds.includes(employee.id)"
              @click="setEmployeeActive(employee)"
            >
              <Icon
                :name="
                  employee.is_active
                    ? 'lucide:user-round-x'
                    : 'lucide:user-round-check'
                "
                size="16"
              />
            </button>
            <button
              v-if="!employee.account_user_id"
              type="button"
              class="is-danger"
              :aria-label="`Supprimer ${employee.first_name}`"
              title="Supprimer"
              :disabled="workingEmployeeIds.includes(employee.id)"
              @click="deleteEmployee(employee)"
            >
              <Icon name="lucide:trash-2" size="16" />
            </button>
          </div>
        </article>
      </div>
      <div v-else class="hr-empty">
        <Icon
          :name="search ? 'lucide:search-x' : 'lucide:users-round'"
          size="22"
        />
        <p>
          {{
            search
              ? "Aucun employé ne correspond à votre recherche."
              : showInactive
                ? "Aucun employé à afficher."
                : "Aucun employé actif pour le moment."
          }}
        </p>
        <button
          v-if="search"
          type="button"
          class="hr-quiet"
          @click="search = ''"
        >
          Effacer la recherche
        </button>
      </div>
    </section>

    <ConfirmDialog
      v-model:visible="deleteConfirmVisible"
      title="Supprimer l’employé"
      :message="`Supprimer définitivement ${employeeToDelete?.first_name} ${employeeToDelete?.last_name} ?`"
      confirm-label="Supprimer"
      cancel-label="Annuler"
      danger
      @confirm="confirmDeleteEmployee"
    />
  </main>
</template>

<style scoped>
.hr-page {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: clamp(22px, 4vw, 48px);
  background: var(--dp-bg);
}
.hr-header,
.hr-section {
  width: 100%;
  margin: 0 0 18px;
}
.hr-header {
  display: grid;
  gap: 20px;
  margin-bottom: 22px;
  padding: clamp(24px, 2.5vw, 38px);
  border: 1px solid var(--dp-line);
  border-radius: 24px;
  background:
    radial-gradient(
      ellipse at 100% 0,
      rgba(70, 153, 109, 0.08),
      transparent 46%
    ),
    linear-gradient(145deg, rgba(255, 255, 255, 0.025), transparent 60%),
    var(--dp-panel);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.16);
}
.hr-header__top {
  display: grid;
  grid-template-columns: minmax(300px, 0.85fr) minmax(0, 1.6fr);
  align-items: center;
  gap: clamp(24px, 3vw, 46px);
}
.hr-header__intro {
  min-width: 0;
}
.hr-eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px !important;
  color: var(--dp-accent) !important;
  font-size: 9px !important;
  font-weight: 800;
  letter-spacing: 0.16em;
}
.hr-eyebrow span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--dp-accent);
  box-shadow: 0 0 0 4px var(--dp-accent-soft);
}
.hr-eyebrow b {
  color: var(--dp-text-dim);
  font-weight: 500;
}
.hr-header h1 {
  margin: 0;
  font-size: clamp(30px, 3vw, 42px);
  letter-spacing: -0.045em;
}
.hr-header__intro > p:last-child {
  max-width: 480px;
  margin-top: 10px;
  color: var(--dp-text-2);
  font-size: 13px;
  line-height: 1.6;
}
.hr-header p,
.hr-section__heading p,
.hr-users__heading p {
  margin: 9px 0 0;
  color: var(--dp-text-2);
  font-size: 13px;
  line-height: 1.6;
}
.hr-overview {
  display: grid;
  grid-template-columns: repeat(5, auto);
  gap: 9px;
  justify-content: end;
}
.hr-stat {
  display: flex;
  min-width: 250px;
  min-height: 82px;
  align-items: center;
  gap: 11px;
  padding: 13px;
  border: 1px solid var(--dp-line);
  border-radius: 15px;
  color: var(--hr-stat-color, var(--dp-accent));
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.035), transparent 70%),
    rgba(12, 16, 19, 0.55);
  transition:
    border-color 0.16s ease,
    transform 0.16s ease,
    background 0.16s ease;
}
.hr-stat:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--hr-stat-color) 40%, var(--dp-line));
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--hr-stat-color) 8%, transparent),
      transparent 78%
    ),
    var(--dp-panel);
}
.hr-stat__icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--hr-stat-color) 28%, transparent);
  border-radius: 12px;
  color: var(--hr-stat-color);
  background: color-mix(in srgb, var(--hr-stat-color) 12%, transparent);
}
.hr-stat__value {
  display: grid;
  min-width: 0;
  gap: 3px;
}
.hr-stat__value strong {
  overflow: hidden;
  color: var(--dp-text);
  font-size: clamp(17px, 1.3vw, 22px);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.03em;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hr-stat__value small {
  color: var(--dp-text-dim);
  font-size: 9px;
  line-height: 1.2;
}
.hr-stat--total {
  --hr-stat-color: #83bdf0;
}
.hr-stat--male {
  --hr-stat-color: #71c4d1;
}
.hr-stat--female {
  --hr-stat-color: #d99dbb;
}
.hr-stat--other {
  --hr-stat-color: #b4a2f7;
}
.hr-stat--age {
  --hr-stat-color: #e0b661;
}
.hr-grade-summary {
  padding: 16px 18px 15px;
  border: 1px solid var(--dp-line);
  border-radius: 17px;
  background:
    linear-gradient(120deg, rgba(70, 153, 109, 0.045), transparent 55%),
    rgba(9, 12, 15, 0.34);
}
.hr-grade-summary__heading {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 13px;
}
.hr-grade-summary__icon {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  place-items: center;
  border: 1px solid var(--dp-accent-line);
  border-radius: 10px;
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
}
.hr-grade-summary__title {
  display: grid;
  min-width: 0;
  gap: 3px;
}
.hr-grade-summary__title > span {
  color: var(--dp-accent);
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.14em;
}
.hr-grade-summary__heading h2 {
  margin: 0;
  color: var(--dp-text);
  font-size: 13px;
  font-weight: 750;
}
.hr-grade-summary__total {
  flex: 0 0 auto;
  margin-left: auto;
  padding: 6px 10px;
  border: 1px solid var(--dp-line);
  border-radius: 999px;
  color: var(--dp-text-2);
  background: var(--dp-panel-2);
  font-size: 9px;
  font-variant-numeric: tabular-nums;
}
.hr-grade-summary__stack {
  display: flex;
  width: 100%;
  height: 13px;
  margin-bottom: 13px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 999px;
  background: var(--dp-panel-3);
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.3);
}
.hr-grade-summary__stack span {
  flex: 0 0 auto;
  min-width: 0;
  border-right: 2px solid var(--dp-panel);
  transition: width 0.25s ease;
}
.hr-grade-summary__list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 8px;
}
.hr-grade-stat {
  display: grid;
  min-width: 0;
  gap: 6px;
  padding: 10px 11px;
  border: 1px solid var(--dp-line);
  border-left: 2px solid var(--hr-stat-color);
  border-radius: 11px;
  background: rgba(12, 16, 19, 0.55);
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}
.hr-grade-stat:hover {
  border-color: color-mix(in srgb, var(--hr-stat-color) 38%, var(--dp-line));
  background: color-mix(in srgb, var(--hr-stat-color) 6%, var(--dp-panel));
}
.hr-grade-stat__label {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--dp-text-2);
  font-size: 10px;
}
.hr-grade-stat__label strong {
  flex: 0 0 auto;
  color: var(--dp-text);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.hr-grade-stat__name {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hr-grade-stat__name i {
  width: 7px;
  height: 7px;
  flex: 0 0 7px;
  border-radius: 50%;
  background: var(--hr-stat-color);
  box-shadow: 0 0 0 3px
    color-mix(in srgb, var(--hr-stat-color) 14%, transparent);
}
.hr-grade-stat small {
  color: var(--dp-text-dim);
  font-size: 9px;
}
.hr-grade-summary__empty {
  margin: 0;
  color: var(--dp-text-dim);
  font-size: 11px;
}
.hr-section {
  padding: clamp(18px, 2.5vw, 28px);
  border: 1px solid var(--dp-line);
  border-radius: 18px;
  background: var(--dp-panel);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.14);
}
.hr-section__heading,
.hr-form__title,
.hr-list__toolbar,
.hr-employee__name,
.hr-employee__actions,
.hr-role__top,
.hr-role__actions,
.hr-users__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.hr-section__heading {
  align-items: flex-end;
  margin-bottom: 22px;
}
.hr-section h2 {
  margin: 0;
  font-size: 20px;
  letter-spacing: -0.02em;
}
.hr-section h3 {
  margin: 0;
  font-size: 14px;
}
.hr-filter {
  display: flex;
  min-height: 42px;
  align-items: center;
  gap: 9px;
  width: min(300px, 100%);
  padding: 0 12px;
  border: 1px solid var(--dp-line);
  border-radius: 10px;
  color: var(--dp-text-dim);
  background: var(--dp-bg);
}
.hr-filter input,
.hr-fields input,
.hr-fields select,
.hr-role-create input:not([type="checkbox"]),
.hr-role input,
.hr-user select {
  width: 100%;
  min-width: 0;
  min-height: 40px;
  border: 1px solid var(--dp-line);
  border-radius: 9px;
  outline: none;
  padding: 0 11px;
  color: var(--dp-text);
  background: var(--dp-bg);
  font: inherit;
  font-size: 12px;
}
.hr-filter input {
  min-height: 38px;
  border: 0;
  padding: 0;
}
.hr-fields input:focus,
.hr-fields select:focus,
.hr-filter:focus-within,
.hr-role input:focus,
.hr-user select:focus {
  border-color: var(--dp-accent);
}
.hr-form {
  margin-bottom: 16px;
  padding: 16px;
  border: 1px solid var(--dp-line);
  background: var(--dp-panel-2);
}
.hr-form__title {
  margin-bottom: 12px;
}
.hr-fields {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  align-items: end;
  gap: 12px;
}
.hr-fields > label,
.hr-role-create__name,
.hr-role__top > label {
  display: grid;
  gap: 6px;
  color: var(--dp-text-2);
  font-size: 10px;
  font-weight: 650;
}
.hr-fields label i {
  color: var(--dp-danger);
  font-style: normal;
}
.hr-fields small {
  color: var(--dp-text-dim);
  font-weight: 400;
}
.hr-employee-form {
  display: grid;
  gap: 14px;
}
.hr-form-block {
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--dp-line);
  border-radius: 14px;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.025), transparent 65%),
    var(--dp-panel-2);
}
.hr-form-block__heading {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 15px;
}
.hr-form-block__icon {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  place-items: center;
  border: 1px solid var(--dp-accent-line);
  border-radius: 10px;
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
}
.hr-form-block__heading h3 {
  margin: 0;
  font-size: 12px;
  font-weight: 750;
}
.hr-form-block__heading p {
  margin: 4px 0 0;
  color: var(--dp-text-dim);
  font-size: 10px;
  line-height: 1.4;
}
.hr-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: 13px 16px;
}
.hr-form-grid > label {
  display: grid;
  min-width: 0;
  gap: 6px;
  color: var(--dp-text-2);
  font-size: 10px;
  font-weight: 650;
}
.hr-form-grid > label > span {
  color: var(--dp-text-2);
}
.hr-form-grid > label i {
  color: var(--dp-danger);
  font-style: normal;
}
.hr-form-grid input:not([type="checkbox"]),
.hr-form-grid select {
  width: 100%;
  min-width: 0;
  min-height: 39px;
  padding: 0 10px;
  border: 1px solid var(--dp-line);
  border-radius: 9px;
  outline: none;
  color: var(--dp-text);
  background: var(--dp-bg);
  font: inherit;
  font-size: 11px;
}
.hr-form-grid input:focus,
.hr-form-grid select:focus {
  border-color: var(--dp-accent);
  box-shadow: 0 0 0 3px rgba(70, 153, 109, 0.12);
}
.hr-form-grid__wide {
  grid-column: 1 / -1;
}
.hr-field-note {
  margin-top: -2px;
  color: var(--dp-accent);
  font-size: 10px;
  font-weight: 600;
}
.hr-qualification-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.hr-qualification,
.hr-license {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--dp-line);
  border-radius: 13px;
  background: rgba(10, 13, 16, 0.34);
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}
.hr-qualification--diploma {
  display: flex;
  min-height: 76px;
  grid-column: 1 / -1;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}
.hr-qualification.is-checked,
.hr-license.is-checked {
  border-color: var(--dp-accent-line);
  background: linear-gradient(
    110deg,
    var(--dp-accent-soft),
    rgba(70, 153, 109, 0.025)
  );
}
.hr-qualification__symbol {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border: 1px solid var(--dp-line);
  border-radius: 11px;
  color: var(--dp-text-dim);
  background: var(--dp-panel-3);
  transition:
    color 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease;
}
.hr-qualification.is-checked .hr-qualification__symbol,
.hr-license.is-checked .hr-qualification__symbol {
  border-color: var(--dp-accent-line);
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
}
.hr-qualification__copy {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 4px;
}
.hr-qualification__copy strong,
.hr-qualification__copy h4 {
  margin: 0;
  overflow: hidden;
  color: var(--dp-text);
  font-size: 11px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hr-qualification__copy small {
  color: var(--dp-text-dim);
  font-size: 9px;
  line-height: 1.35;
}
.hr-license {
  display: grid;
  align-content: start;
  gap: 13px;
  min-height: 122px;
}
.hr-license__header {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}
.hr-license__date {
  display: grid;
  gap: 6px;
  padding-top: 11px;
  border-top: 1px solid var(--dp-line);
  color: var(--dp-text-2);
  font-size: 9px;
  font-weight: 650;
}
.hr-license__date input {
  width: 100%;
  min-width: 0;
  min-height: 36px;
  padding: 0 9px;
  border: 1px solid var(--dp-line);
  border-radius: 9px;
  outline: none;
  color: var(--dp-text);
  background: var(--dp-bg);
  font: inherit;
  font-size: 10px;
}
.hr-license__date input:focus-visible {
  border-color: var(--dp-accent);
  outline: 2px solid rgba(70, 153, 109, 0.18);
  outline-offset: 1px;
}
.hr-license__hint {
  margin: 0 0 0 48px;
  color: var(--dp-text-dim);
  font-size: 9px;
  line-height: 1.4;
}
.hr-switch {
  position: relative;
  display: inline-flex;
  width: 38px;
  height: 22px;
  flex: 0 0 38px;
  cursor: pointer;
}
.hr-switch input {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 100%;
  height: 100%;
  margin: 0;
  opacity: 0;
  cursor: pointer;
}
.hr-switch__track {
  position: relative;
  display: block;
  width: 38px;
  height: 22px;
  border: 1px solid var(--dp-line-strong);
  border-radius: 999px;
  background: var(--dp-panel-3);
  transition:
    background 0.16s ease,
    border-color 0.16s ease;
}
.hr-switch__track::after {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--dp-text-dim);
  content: "";
  transition:
    transform 0.16s ease,
    background 0.16s ease;
}
.hr-switch input:checked + .hr-switch__track {
  border-color: var(--dp-accent);
  background: var(--dp-accent-soft);
}
.hr-switch input:checked + .hr-switch__track::after {
  transform: translateX(16px);
  background: var(--dp-accent);
}
.hr-switch input:focus-visible + .hr-switch__track {
  outline: 2px solid var(--dp-accent);
  outline-offset: 3px;
}

.hr-primary,
.hr-quiet,
.hr-danger {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 14px;
  border: 1px solid transparent;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    transform 0.16s ease;
}
.hr-primary {
  color: #0c1710;
  background: var(--dp-accent);
}
.hr-primary:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
.hr-quiet {
  border-color: var(--dp-line);
  color: var(--dp-text-2);
  background: transparent;
}
.hr-danger {
  color: var(--dp-danger);
  background: var(--dp-danger-soft);
}
.hr-list__toolbar {
  margin: 22px 0 12px;
  color: var(--dp-text-dim);
  font-size: 11px;
}
.hr-list__toolbar label,
.hr-role-create fieldset label,
.hr-role fieldset label,
.hr-user__admin {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--dp-text-2);
  font-size: 10px;
  font-weight: 500;
}
.hr-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.hr-employee {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid var(--dp-line);
  border-radius: 12px;
  background: var(--dp-panel-2);
  border-left: 4px solid var(--hr-grade-color, transparent);
}
.hr-employee.is-inactive {
  opacity: 0.68;
}
.hr-employee__avatar {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  place-items: center;
  border: 1px solid var(--dp-accent-line);
  border-radius: 13px;
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
}
.hr-employee__main {
  flex: 1;
  min-width: 0;
}
.hr-employee__name {
  justify-content: flex-start;
}
.hr-employee__name h3 {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hr-status {
  padding: 3px 7px;
  border-radius: 10px;
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
  font-size: 9px;
}
.hr-status.is-inactive {
  color: var(--dp-text-2);
  background: var(--dp-panel-3);
}
.hr-employee__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  margin: 8px 0 0;
  color: var(--dp-text-2);
  font-size: 11px;
  line-height: 1.4;
}
.hr-employee__meta > span {
  display: flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hr-employee__meta > span:not(:last-child)::after {
  content: "•";
  color: var(--dp-line);
  margin-left: 4px;
  font-size: 9px;
}
.hr-employee__grade-name {
  color: var(--dp-text);
  font-weight: 700;
}
.hr-email-blur {
  color: var(--dp-text-2);
  filter: blur(3px);
  transition: filter 0.15s ease;
  cursor: pointer;
  user-select: none;
}
.hr-email-blur:hover {
  filter: none;
}
.hr-email-blur.hr-email-revealed {
  filter: none;
}
.hr-email {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.hr-email button {
  display: inline-grid;
  width: 20px;
  height: 20px;
  place-items: center;
  color: var(--dp-text-2);
}
.hr-email button:hover {
  color: var(--dp-accent);
}
.hr-grade {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
}
.hr-employee__actions {
  flex: 0 0 auto;
  justify-content: flex-end;
  gap: 5px;
}
.hr-employee__actions button {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 9px;
  color: var(--dp-text-dim);
}
.hr-employee__actions button:hover {
  color: var(--dp-accent);
  background: var(--dp-accent-soft);
}
.hr-employee__actions button:disabled {
  cursor: wait;
  opacity: 0.45;
}
.hr-employee__actions button.is-danger:hover {
  color: var(--dp-danger);
  background: var(--dp-danger-soft);
}
.hr-empty {
  display: grid;
  min-height: 180px;
  place-content: center;
  justify-items: center;
  gap: 10px;
  border: 1px dashed var(--dp-line-strong);
  border-radius: 14px;
  color: var(--dp-text-dim);
  font-size: 12px;
}
.hr-empty p {
  margin: 0;
}
.hr-error {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  margin: 0 0 14px;
  padding: 12px 14px;
  border: 1px solid var(--dp-danger-line);
  border-radius: 12px;
  color: #f0a29d;
  background: var(--dp-danger-soft);
  font-size: 12px;
}
.hr-error span {
  flex: 1;
}
.hr-error button {
  color: inherit;
}
.hr-super-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--dp-accent);
  font-size: 10px;
}
.hr-role-create,
.hr-role {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--dp-line);
  background: var(--dp-panel-2);
}
.hr-role-create {
  grid-template-columns: minmax(150px, 0.7fr) minmax(0, 2fr) auto;
  align-items: end;
  margin-bottom: 10px;
}
.hr-role-create fieldset,
.hr-role fieldset {
  display: flex;
  flex-wrap: wrap;
  gap: 9px 14px;
  min-width: 0;
  margin: 0;
  padding: 8px;
  border: 1px solid var(--dp-line);
}
.hr-role-create legend,
.hr-role legend {
  padding: 0 5px;
  color: var(--dp-text-dim);
  font-size: 9px;
}
.hr-role-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr));
  gap: 10px;
}
.hr-role__top {
  align-items: end;
}
.hr-role__top > label {
  flex: 1;
}
.hr-role__count {
  color: var(--dp-text-dim);
  font-size: 10px;
}
.hr-role__actions {
  justify-content: flex-start;
}
.hr-users {
  margin-top: 20px;
  border-top: 1px solid var(--dp-line);
}
.hr-users__heading {
  justify-content: flex-start;
  padding: 16px 0 10px;
}
.hr-users__heading > div {
  display: grid;
  gap: 4px;
}
.hr-user {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(150px, 240px) 140px;
  align-items: center;
  gap: 12px;
  padding: 9px 0;
  border-top: 1px solid var(--dp-line);
}
.hr-user > div {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.hr-user strong {
  overflow: hidden;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hr-user small {
  color: var(--dp-text-dim);
  font-size: 9px;
}
.hr-user__admin {
  white-space: nowrap;
}
.hr-loading {
  color: var(--dp-text-dim);
  font-size: 11px;
}
.hr-spin {
  animation: hr-spin 1s linear infinite;
}
.hr-page {
  background:
    radial-gradient(
      ellipse at 86% 0,
      rgba(70, 153, 109, 0.11),
      transparent 40%
    ),
    var(--dp-bg);
}
.hr-section {
  border-color: var(--dp-line);
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.025), transparent 55%),
    var(--dp-panel);
}
.hr-form {
  border-color: var(--dp-accent-line);
}
.hr-employee {
  transition:
    border-color 0.16s ease,
    background 0.16s ease;
}
.hr-employee:hover {
  border-color: var(--dp-line-strong);
  background: #1b2228;
  border-left-color: var(--hr-grade-color, transparent);
}
.hr-fields input:focus-visible,
.hr-fields select:focus-visible,
.hr-account-link select:focus-visible,
.hr-role input:focus-visible,
.hr-user select:focus-visible,
.hr-filter:focus-within {
  outline: 2px solid rgba(70, 153, 109, 0.24);
  outline-offset: 1px;
}
.hr-primary:hover:not(:disabled) {
  filter: brightness(1.08);
}
.hr-quiet:hover:not(:disabled) {
  color: var(--dp-text);
  border-color: var(--dp-line-strong);
  background: var(--dp-panel-3);
}
.hr-primary:focus-visible,
.hr-quiet:focus-visible,
.hr-employee__actions button:focus-visible {
  outline: 2px solid var(--dp-accent);
  outline-offset: 2px;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
@keyframes hr-spin {
  to {
    transform: rotate(360deg);
  }
}
.hr-section__title {
  min-width: 180px;
}
.hr-section__tools {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 9px;
}
.hr-add {
  min-height: 42px;
  padding: 0 16px;
}
@media (max-width: 760px) {
  .hr-section__heading {
    align-items: stretch;
    flex-direction: column;
  }
  .hr-section__tools {
    flex: 1;
    min-width: 0;
    flex-wrap: wrap;
  }
  .hr-section__tools .hr-filter {
    flex: 1;
  }
  .hr-add {
    white-space: nowrap;
  }
}
@media (max-width: 900px) {
  .hr-fields {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .hr-role-create {
    grid-template-columns: 1fr;
  }
  .hr-role-create .hr-primary {
    justify-self: start;
  }
}
@media (max-width: 1100px) {
  .hr-header__top {
    grid-template-columns: minmax(0, 1fr);
    gap: 18px;
  }
}
@media (max-width: 760px) {
  .hr-overview {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .hr-page {
    padding: 14px;
  }
  .hr-form-block {
    padding: 13px;
  }
  .hr-form-grid,
  .hr-qualification-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .hr-qualification--diploma {
    grid-column: auto;
  }
  .hr-form-grid__wide {
    grid-column: auto;
  }
  .hr-header__top {
    grid-template-columns: minmax(0, 1fr);
  }
  .hr-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .hr-section {
    padding: 13px;
  }
  .hr-section__heading {
    align-items: stretch;
    flex-direction: column;
  }
  .hr-section__tools {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
  }
  .hr-filter {
    width: 100%;
  }
  .hr-fields {
    grid-template-columns: 1fr 1fr;
    gap: 9px;
  }
  .hr-fields > .hr-primary {
    grid-column: span 2;
  }
  .hr-employee {
    gap: 10px;
    padding: 13px;
  }
  .hr-employee__avatar {
    width: 36px;
    height: 36px;
    flex-basis: 36px;
  }
  .hr-employee__actions {
    flex-direction: row;
  }
  .hr-user {
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
  }
  .hr-user__role {
    grid-column: 1 / -1;
    grid-row: 2;
  }
}
</style>
