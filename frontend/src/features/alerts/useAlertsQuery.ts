import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchJson, fetchOptionalJson } from "@/api/client";
import {
  AcknowledgeAlertRequest,
  AlertsResponse,
  AlertRecord,
  AlertKind,
  AlertListMeta,
  AlertSeverity,
  AlertStatus
} from "@/api/models";

const emptyAlerts: AlertsResponse = {
  items: [],
  meta: {
    filtered_total: 0,
    returned: 0,
    open_badge_count: 0,
    open_by_kind: { production: 0, consumption: 0 },
    open_by_severity: { info: 0, warning: 0, critical: 0 }
  }
};

interface UseAlertsOptions {
  status?: "open" | "acknowledged" | "resolved" | "suppressed" | null;
  kind?: "production" | "consumption" | null;
  severity?: "info" | "warning" | "critical" | null;
}

function buildMeta(items: AlertRecord[]): AlertListMeta {
  const openItems = items.filter((item) => item.status === "open");

  return {
    filtered_total: items.length,
    returned: items.length,
    open_badge_count: openItems.length,
    open_by_kind: {
      production: openItems.filter((item) => item.kind === "production").length,
      consumption: openItems.filter((item) => item.kind === "consumption").length
    } satisfies Record<AlertKind, number>,
    open_by_severity: {
      info: openItems.filter((item) => item.severity === "info").length,
      warning: openItems.filter((item) => item.severity === "warning").length,
      critical: openItems.filter((item) => item.severity === "critical").length
    } satisfies Record<AlertSeverity, number>
  };
}

function applyAlertMutation(old: AlertsResponse | undefined, alertId: number, updater: (item: AlertRecord) => AlertRecord): AlertsResponse | undefined {
  if (!old) {
    return old;
  }

  const items = old.items.map((item) => (item.alert_id === alertId ? updater(item) : item));

  return {
    ...old,
    items,
    meta: buildMeta(items)
  };
}

export function useAlertsQuery(options: UseAlertsOptions = {}) {
  const { status, kind, severity } = options;

  return useQuery({
    queryKey: ["alerts", { status, kind, severity }],
    queryFn: () =>
      fetchOptionalJson<AlertsResponse>("/api/alerts", emptyAlerts, {
        query: {
          ...(status != null ? { status } : {}),
          ...(kind != null ? { kind } : {}),
          ...(severity != null ? { severity } : {})
        }
      })
  });
}

export function useAlertsAllQuery() {
  return useAlertsQuery({});
}

export function useOpenAlertsQuery() {
  return useAlertsQuery({ status: "open" });
}

export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ alertId, body }: { alertId: number; body: AcknowledgeAlertRequest }) =>
      fetchJson<AlertRecord>(`/api/alerts/${alertId}/acknowledge`, {
        method: "POST",
        body: JSON.stringify(body),
        headers: { "Content-Type": "application/json" }
      }),

    onMutate: async ({ alertId, body }) => {
      await queryClient.cancelQueries({ queryKey: ["alerts"] });
      const previousQueries = queryClient.getQueriesData<AlertsResponse>({ queryKey: ["alerts"] });
      const nextStatus = (body.new_status ?? "acknowledged") as AlertStatus;
      const acknowledgedAt = new Date().toISOString();

      queryClient.setQueriesData<AlertsResponse>(
        { queryKey: ["alerts"] },
        (old) =>
          applyAlertMutation(old, alertId, (item) => ({
            ...item,
            status: nextStatus,
            acknowledged_at: acknowledgedAt,
            acknowledged_by: body.acknowledged_by ?? "local-operator",
            acknowledged_note: body.note ?? null
          }))
      );

      return { previousQueries };
    },

    onError: (_err, _variables, context) => {
      if (context?.previousQueries) {
        for (const [queryKey, data] of context.previousQueries) {
          queryClient.setQueryData(queryKey, data);
        }
      }
    },

    onSuccess: (updatedAlert) => {
      queryClient.setQueriesData<AlertsResponse>(
        { queryKey: ["alerts"] },
        (old) => applyAlertMutation(old, updatedAlert.alert_id, () => updatedAlert)
      );
    },

    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
    }
  });
}
