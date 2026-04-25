import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { StatCard } from '../components/ui/StatCard';
import { JobCard } from '../components/jobs/JobCard';
import { EmptyState } from '../components/ui/EmptyState';
import { Loader } from '../components/ui/Loader';
import { Button } from '../components/ui/Button';
import { Briefcase, Users, FileCheck, FileX, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export function DashboardPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.getDashboard,
  });

  if (isLoading) {
    return (
      <div className="max-w-screen-xl mx-auto space-y-8 animate-fade-slide-up">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {[1,2,3,4].map(i => <Loader key={i} variant="skeleton" className="h-32 rounded-2xl" />)}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1,2,3].map(i => <Loader key={i} variant="skeleton" className="h-52 rounded-2xl" />)}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <EmptyState
        title="Could not load dashboard"
        message="There was an error connecting to the API."
        action={<Button onClick={refetch}>Try Again</Button>}
      />
    );
  }

  return (
    <div className="max-w-screen-xl mx-auto space-y-10 animate-fade-slide-up">

      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-primary mb-2">ATS Intelligence</p>
          <h1 className="text-4xl font-heading font-bold text-dark leading-tight">Overview</h1>
          <p className="text-mid mt-2">Welcome back. Here's a snapshot of your pipeline.</p>
        </div>
        <Button onClick={() => navigate('/jobs/new')} className="shrink-0">
          <Plus className="w-4 h-4 mr-2" /> New Job
        </Button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard icon={Briefcase}  label="Total Jobs"         value={data?.total_jobs         || 0} />
        <StatCard icon={Users}      label="Total Candidates"   value={data?.total_candidates   || 0} />
        <StatCard icon={FileCheck}  label="Completed Resumes"  value={data?.completed_resumes  || 0} />
        <StatCard icon={FileX}      label="Failed Resumes"     value={data?.failed_resumes     || 0} />
      </div>

      {/* Recent jobs */}
      <div>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-xl font-heading font-bold text-dark">Recent Jobs</h2>
          <span className="text-xs text-mid/60 font-mono">{data?.latest_jobs?.length || 0} shown</span>
        </div>

        {!data?.latest_jobs || data.latest_jobs.length === 0 ? (
          <EmptyState
            title="No Jobs Yet"
            message="Create your first job posting to start processing resumes."
            action={<Button onClick={() => navigate('/jobs/new')}><Plus className="w-4 h-4 mr-2" />Create Job</Button>}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {data.latest_jobs.map((job) => (
              <JobCard key={job.job_id || job.id} job={job} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
