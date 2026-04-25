import React from 'react';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { ChevronRight, Upload, CheckCircle, XCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

export function JobCard({ job }) {
  const uploaded  = job.resume_counts?.uploaded  ?? job.total_resumes    ?? 0;
  const evaluated = job.resume_counts?.completed ?? job.evaluated_resumes ?? 0;
  const failed    = job.resume_counts?.failed    ?? job.failed_resumes    ?? 0;

  return (
    <Link to={`/jobs/${job.job_id || job.id}`} className="block group h-full">
      <Card className="!p-0 overflow-hidden h-full flex flex-col hover:shadow-md hover:-translate-y-0.5 hover:border-primary/30 transition-all duration-200 group-hover:border-primary/30">
        {/* Card header */}
        <div className="px-6 pt-6 pb-4 flex-1">
          <div className="flex justify-between items-start gap-3 mb-3">
            <h3 className="text-base font-heading font-semibold text-dark group-hover:text-primary transition-colors leading-snug">
              {job.title || 'Untitled Job'}
            </h3>
            <Badge status={job.evaluation_status || 'not_started'} />
          </div>
          <p className="text-xs text-mid/60 font-mono truncate">
            {job.job_id || job.id}
          </p>
        </div>

        {/* Pipeline metrics */}
        <div className="mx-6 mb-4 grid grid-cols-3 divide-x divide-mid/10 bg-light/60 rounded-xl border border-mid/10 overflow-hidden">
          {[
            { Icon: Upload,      label: 'Uploaded',  value: uploaded,  color: 'text-dark' },
            { Icon: CheckCircle, label: 'Evaluated', value: evaluated, color: 'text-primary' },
            { Icon: XCircle,     label: 'Failed',    value: failed,    color: 'text-error' },
          ].map(({ Icon, label, value, color }) => (
            <div key={label} className="flex flex-col items-center py-3 px-2">
              <Icon className={`w-3.5 h-3.5 ${color} mb-1 opacity-70`} />
              <span className={`text-base font-bold ${color}`}>{value}</span>
              <span className="text-[9px] uppercase tracking-widest text-mid/60 mt-0.5">{label}</span>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-6 pb-5 flex items-center justify-between border-t border-mid/8 pt-4">
          <span className="text-xs text-mid/60">
            {job.created_at ? new Date(job.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : 'Recent'}
          </span>
          <span className="flex items-center text-xs font-semibold text-primary gap-1 group-hover:gap-2 transition-all">
            View Details <ChevronRight className="w-3.5 h-3.5" />
          </span>
        </div>
      </Card>
    </Link>
  );
}
