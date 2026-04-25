import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function usePollResumeStatus(resumeId, enabled) {
  return useQuery({
    queryKey: ["resume-status", resumeId],
    queryFn: () => api.getResumeStatus(resumeId),
    enabled: !!resumeId && enabled,
    refetchInterval: (data) => {
      // Stop polling when terminal state reached
      const done = ["completed", "failed", "ready_for_evaluation"];
      return done.includes(data?.status) ? false : 4000;
    },
  });
}
