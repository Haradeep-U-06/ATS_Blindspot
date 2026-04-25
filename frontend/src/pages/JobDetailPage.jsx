import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { JobStatBar } from '../components/jobs/JobStatBar';
import { EvaluationStatusBanner } from '../components/jobs/EvaluationStatusBanner';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import { Loader } from '../components/ui/Loader';
import { useToast } from '../hooks/useToast';
import { usePollEvaluation } from '../hooks/usePollEvaluation';
import { Users, Upload, Play } from 'lucide-react';

export function JobDetailPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [isTriggering, setIsTriggering] = useState(false);

  const { data: job, isLoading: isLoadingJob, isError: isErrorJob } = useQuery({
    queryKey: ['jobs', jobId],
    queryFn: () => api.getJob(jobId),
  });

  const isPollingEnabled = job && job.evaluation_status !== 'completed' && job.evaluation_status !== 'completed_with_errors' && job.evaluation_status !== 'not_started';
  const { data: evalStatusData } = usePollEvaluation(jobId, isPollingEnabled);

  const handleTrigger = async () => {
    setIsTriggering(true);
    try {
      await api.triggerEvaluation(jobId);
      toast('Evaluation triggered successfully!', 'success');
      queryClient.invalidateQueries({ queryKey: ['jobs', jobId] });
      queryClient.invalidateQueries({ queryKey: ['evaluation-status', jobId] });
    } catch (err) {
      toast(err.message || 'Failed to trigger evaluation', 'error');
    } finally {
      setIsTriggering(false);
    }
  };

  if (isLoadingJob) return <Loader variant="spinner" text="Loading job details..." className="h-64" />;
  if (isErrorJob) return <EmptyState title="Job Not Found" message="The requested job does not exist or you don't have permission to view it." action={<Button onClick={() => navigate('/')}>Back to Dashboard</Button>} />;

  const currentStatus = evalStatusData?.evaluation_status || job.evaluation_status || 'not_started';
  const stats = evalStatusData?.resume_counts || job.resume_counts || {};
  const readyCount = stats.ready_for_evaluation || stats.ready || 0;
  const isRunning = currentStatus === 'processing' || currentStatus === 'queued' || currentStatus === 'evaluating' || currentStatus === 'running';
  const isCompleted = currentStatus === 'completed' || currentStatus === 'completed_with_errors';
  const isFailed = currentStatus === 'failed';

  return (
    <div className="max-w-screen-xl mx-auto animate-fade-slide-up">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-heading font-bold text-dark">{job.title}</h1>
            <Badge status={currentStatus} />
          </div>
          <p className="text-mid font-mono text-sm">ID: {jobId}</p>
        </div>
        <div className="text-sm text-mid">
          Created: {new Date(job.created_at || Date.now()).toLocaleDateString()}
        </div>
      </div>

      <div className="mb-8">
        <JobStatBar stats={stats} />
      </div>

      {isRunning && (
        <EvaluationStatusBanner status={currentStatus} message="Background evaluation is currently running. This may take a few minutes." />
      )}
      
      {isCompleted && (
        <div className="bg-primary/10 border border-primary/20 rounded-lg p-4 flex items-center justify-between mb-8 animate-fade-slide-up">
          <div>
            <p className="font-medium text-primary">Evaluation Complete</p>
            <p className="text-sm text-mid">Candidates have been ranked and scored.</p>
          </div>
        </div>
      )}

      {isFailed && (
        <div className="bg-error/10 border border-error/20 rounded-lg p-4 flex items-center justify-between mb-8 animate-fade-slide-up">
          <div>
            <p className="font-medium text-error">Evaluation Failed</p>
            <p className="text-sm text-mid">{evalStatusData?.evaluation_error || job.evaluation_error || 'An unknown error occurred.'}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Button 
          variant="secondary" 
          className="h-24 flex flex-col items-center justify-center gap-2"
          onClick={() => navigate(`/jobs/${jobId}/upload`)}
        >
          <Upload className="w-6 h-6" />
          <span>Upload Resume</span>
        </Button>

        <Button 
          variant={isRunning ? "secondary" : "primary"}
          className="h-24 flex flex-col items-center justify-center gap-2"
          disabled={readyCount === 0 || isRunning || isTriggering}
          isLoading={isTriggering}
          onClick={handleTrigger}
        >
          <Play className="w-6 h-6" />
          <span>Trigger Evaluation</span>
        </Button>

        <Button 
          variant={isCompleted ? "primary" : "outline"}
          className="h-24 flex flex-col items-center justify-center gap-2"
          disabled={!isCompleted}
          onClick={() => navigate(`/jobs/${jobId}/candidates`)}
        >
          <Users className="w-6 h-6" />
          <span>View Rankings</span>
        </Button>
      </div>
    </div>
  );
}
