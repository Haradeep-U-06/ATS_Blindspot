import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function usePollEvaluation(jobId, enabled) {
  return useQuery({
    queryKey: ["evaluation-status", jobId],
    queryFn: () => api.getEvaluationStatus(jobId),
    enabled: !!jobId && enabled,
    refetchInterval: (data) => {
      return data?.evaluation_status === "completed" || data?.evaluation_status === "completed_with_errors" ? false : 5000;
    },
  });
}
