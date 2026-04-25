import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';

function formatCrumb(segment) {
  if (segment === 'jobs')       return 'Jobs';
  if (segment === 'new')        return 'New Job';
  if (segment === 'upload')     return 'Upload Resume';
  if (segment === 'candidates') return 'Candidates';
  if (segment.startsWith('job_'))       return 'Job Details';
  if (segment.startsWith('candidate_')) return 'Candidate';
  return segment.charAt(0).toUpperCase() + segment.slice(1);
}

export function Topbar() {
  const location = useLocation();
  const segments = location.pathname.split('/').filter(Boolean);

  const breadcrumbs = segments.map((seg, idx) => ({
    label: formatCrumb(seg),
    url:   `/${segments.slice(0, idx + 1).join('/')}`,
    isLast: idx === segments.length - 1,
  }));

  return (
    <header className="h-[64px] bg-cream sticky top-0 z-30 flex items-center px-6 border-b border-mid/10 shrink-0">
      <nav className="flex items-center gap-1 text-sm" aria-label="Breadcrumb">
        <Link
          to="/"
          className="flex items-center gap-1.5 text-mid hover:text-dark transition-colors px-2 py-1 rounded-lg hover:bg-mid/8"
        >
          <Home className="w-3.5 h-3.5" />
          <span className="font-medium">Home</span>
        </Link>

        {breadcrumbs.map((crumb) => (
          <React.Fragment key={crumb.url}>
            <ChevronRight className="w-3.5 h-3.5 text-mid/40 flex-shrink-0" />
            {crumb.isLast ? (
              <span className="px-2 py-1 text-dark font-semibold rounded-lg">
                {crumb.label}
              </span>
            ) : (
              <Link
                to={crumb.url}
                className="px-2 py-1 text-mid hover:text-dark transition-colors rounded-lg hover:bg-mid/8 font-medium"
              >
                {crumb.label}
              </Link>
            )}
          </React.Fragment>
        ))}
      </nav>
    </header>
  );
}
