import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { CandidateRow } from '../components/candidates/CandidateRow';
import { EmptyState } from '../components/ui/EmptyState';
import { Loader } from '../components/ui/Loader';
import { Button } from '../components/ui/Button';
import { ArrowLeft } from 'lucide-react';
import { Card } from '../components/ui/Card';

export function CandidateRankingPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['candidates', jobId],
    queryFn: () => api.getRankedCandidates(jobId),
  });

  if (isLoading) return <Loader variant="spinner" text="Loading candidates..." className="h-64" />;
  
  if (data?._status === 409 || isError) {
    return (
      <div className="max-w-5xl mx-auto animate-fade-slide-up">
        <Button variant="outline" onClick={() => navigate(`/jobs/${jobId}`)} className="mb-6">
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Job
        </Button>
        <EmptyState 
          title="Evaluation Not Ready" 
          message="The evaluation has not completed yet, or there was an error loading the candidates." 
        />
      </div>
    );
  }

  const candidates = data?.candidates || [];
  
  const sortedCandidates = [...candidates].sort((a, b) => {
    const scoreA = a.final_score || a.score || 0;
    const scoreB = b.final_score || b.score || 0;
    return scoreB - scoreA;
  });

  return (
    <div className="max-w-screen-xl mx-auto animate-fade-slide-up">
      <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-heading font-bold text-dark mb-2">Candidate Rankings</h1>
          <p className="text-mid">Review and compare candidates based on AI evaluation.</p>
        </div>
        <Button variant="outline" onClick={() => navigate(`/jobs/${jobId}`)}>
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Job
        </Button>
      </div>

      <Card className="!p-0 overflow-hidden">
        {sortedCandidates.length === 0 ? (
          <EmptyState 
            title="No Candidates Found" 
            message="No resumes have been evaluated for this job yet." 
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-light border-b border-mid/10 text-xs uppercase tracking-wider text-mid font-semibold">
                  <th className="px-6 py-4">Rank</th>
                  <th className="px-6 py-4">Candidate</th>
                  <th className="px-6 py-4">Score</th>
                  <th className="px-6 py-4">Top Skills</th>
                  <th className="px-6 py-4">Recommendation</th>
                  <th className="px-6 py-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {sortedCandidates.map((candidate, index) => (
                  <CandidateRow 
                    key={candidate.candidate_id || candidate.id || index} 
                    candidate={candidate} 
                    index={index} 
                    jobId={jobId} 
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
