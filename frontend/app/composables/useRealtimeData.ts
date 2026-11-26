export interface RealtimeAgendaEvent {
  id: number;
  title: string;
  starts_at: string;
  ends_at: string | null;
  description: string | null;
  color: string;
  is_automatic?: boolean;
}

export function useRealtimeData() {
  const agendaEvents = useState<RealtimeAgendaEvent[]>(
    "realtime-agenda-events",
    () => [],
  );
  const agendaLoaded = useState("realtime-agenda-loaded", () => false);
  return { agendaEvents, agendaLoaded };
}
