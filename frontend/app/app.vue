<script setup lang="ts">
const config = useRuntimeConfig();
const route = useRoute();
const toast = useAppToast();
const revision = useState("realtime-data-revision", () => 0);
const { agendaEvents, agendaLoaded } = useRealtimeData();
let socket: WebSocket | null = null;
let reconnect: ReturnType<typeof setTimeout> | undefined;
let ping: ReturnType<typeof setInterval> | undefined;
let attempt = 0;
let alive = true;
let connecting = false;

function clearSocket() {
  if (reconnect) clearTimeout(reconnect);
  if (ping) clearInterval(ping);
  reconnect = undefined;
  ping = undefined;
  if (socket) {
    socket.onclose = null;
    socket.close();
    socket = null;
  }
}

async function connect() {
  if (!import.meta.client || !alive || socket || connecting) return;
  connecting = true;
  // Avoid connecting on the login screen; the WS authenticates from the session cookie.
  try {
    await $fetch("/api/me", { credentials: "include" });
  } catch {
    connecting = false;
    return;
  }
  const apiUrl = new URL(
    String(config.public.apiBase || window.location.origin),
    window.location.origin,
  );
  apiUrl.protocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";
  apiUrl.pathname = "/ws/dispatch";
  apiUrl.search = "";
  const routeToken =
    typeof route.query.token === "string" ? route.query.token : "";
  if (routeToken) apiUrl.searchParams.set("token", routeToken);
  try {
    socket = new WebSocket(apiUrl.toString());
  } catch {
    connecting = false;
    return;
  }
  socket.onopen = () => {
    connecting = false;
    attempt = 0;
    ping = setInterval(
      () => socket?.readyState === WebSocket.OPEN && socket.send("ping"),
      25_000,
    );
  };
  socket.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data) as {
        type?: string;
        data?: unknown;
      };
      if (message.type === "account_revoked") {
        void handleAccountRevoked();
        return;
      }
      if (message.type === "data_changed") revision.value += 1;
      if (message.type === "agenda_events" && Array.isArray(message.data)) {
        agendaEvents.value = message.data;
        agendaLoaded.value = true;
      }
    } catch {
      /* Ignore malformed messages. */
    }
  };
  socket.onclose = () => {
    connecting = false;
    socket = null;
    if (ping) clearInterval(ping);
    ping = undefined;
    if (alive) {
      const delay = Math.min(1000 * 2 ** attempt++, 30_000);
      reconnect = setTimeout(() => void connect(), delay);
    }
  };
}

async function handleAccountRevoked() {
  alive = false;
  clearSocket();
  toast.warning(
    "Ton compte a été désactivé ou supprimé. Tu as été déconnecté.",
  );
  try {
    await $fetch("/api/auth/logout", {
      method: "POST",
      credentials: "include",
    });
  } catch {
    // La session est déjà refusée côté serveur, même si le cookie ne peut pas être effacé.
  }
  await navigateTo("/", { replace: true });
}

onMounted(() => void connect());
watch(
  () => route.fullPath,
  () => {
    if (!socket) void connect();
  },
);
onBeforeUnmount(() => {
  alive = false;
  clearSocket();
});
</script>

<template>
  <div>
    <NuxtRouteAnnouncer />
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <ToastStack />
  </div>
</template>
