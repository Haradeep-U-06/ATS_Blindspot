import React from 'react';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { useNavigate } from 'react-router-dom';

export function CandidateRow({ candidate, index, jobId }) {
  const navigate = useNavigate();
  
  const getScoreColor = (score) => {
    if (score >= 80) return 'border-primary text-primary';
    if (score >= 60) return 'border-secondary text-secondary';
    if (score >= 40) return 'border-warning text-warning';
    return 'border-error text-error';
  };

  const getRecommendationBadge = (rec) => {
    const val = rec?.toLowerCase() || '';
    if (val.includes('strong')) return <Badge status="completed" text={rec} />; // dark green
    if (val.includes('not recommended')) return <Badge status="failed" text={rec} />; // red
    if (val.includes('maybe')) return <Badge status="processing" text={rec} />; // amber
    return <Badge status="ready" text={rec} />; // sage green
  };

  return (
    <tr className="border-b border-mid/10 hover:bg-light/30 transition-colors">
      <td className="px-6 py-4 whitespace-nowrap text-sm text-mid font-mono">{index + 1}</td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm font-medium text-dark">{candidate?.name || 'Unknown'}</div>
        <div className="text-xs text-mid">{candidate?.email}</div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className={`inline-flex items-center justify-center w-10 h-10 rounded-full border-2 font-mono font-bold text-sm ${getScoreColor(candidate?.final_score || candidate?.score)}`}>
          {Math.round(candidate?.final_score || candidate?.score || 0)}
        </div>
      </td>
      <td className="px-6 py-4">
        <div className="flex flex-wrap gap-1">
          {candidate?.skills?.slice(0, 3).map((skillObj, i) => {
            const skillName = typeof skillObj === 'string' ? skillObj : (skillObj.skill || skillObj.name || '');
            return (
              <span key={i} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-mid/10 text-mid border border-mid/10 shadow-sm">
                {skillName}
              </span>
            );
          })}
          {candidate?.skills?.length > 3 && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-mid/5 text-mid">
              +{candidate.skills.length - 3}
            </span>
          )}
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        {getRecommendationBadge(candidate?.recommendation)}
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
        <Button 
          variant="outline" 
          onClick={() => navigate(`/jobs/${jobId}/candidates/${candidate?.candidate_id || candidate?.id}`)}
        >
          View Dashboard
        </Button>
      </td>
    </tr>
  );
}
