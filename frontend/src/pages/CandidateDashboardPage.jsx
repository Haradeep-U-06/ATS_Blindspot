import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { ScoreGauge } from '../components/candidates/ScoreGauge';
import { SkillScoreBar } from '../components/candidates/SkillScoreBar';
import { ExternalProfilesSection } from '../components/candidates/ExternalProfilesSection';
import { ResumeViewerModal } from '../components/candidates/ResumeViewerModal';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Loader } from '../components/ui/Loader';
import { EmptyState } from '../components/ui/EmptyState';
import { useToast } from '../hooks/useToast';
import {
  ArrowLeft, ExternalLink, Check, AlertTriangle, User, Mail,
  Copy, FileText, GitBranch, Code, Star, GitFork, Terminal, Award
} from 'lucide-react';

/* ─── Helpers ─── */

function formatExternalUrl(platform, url) {
  if (url == null || url === false) return '#';
  const str = String(url).trim();
  if (!str || str === 'null' || str === 'undefined' || str === 'false') return '#';
  if (str.startsWith('http')) return str;
  const username = str.replace(/^@/, '');
  switch ((platform || '').toLowerCase()) {
    case 'github':     return `https://github.com/${username}`;
    case 'leetcode':   return `https://leetcode.com/u/${username}`;
    case 'codeforces': return `https://codeforces.com/profile/${username}`;
    case 'codechef':   return `https://www.codechef.com/users/${username}`;
    default:           return str.startsWith('http') ? str : `https://${str}`;
  }
}


function getPlatformIcon(platform) {
  switch (platform.toLowerCase()) {
    case 'github':    return <GitBranch className="w-4 h-4" />;
    case 'leetcode':   return <Code className="w-4 h-4" />;
    case 'codeforces': return <Terminal className="w-4 h-4" />;
    case 'codechef':   return <Award className="w-4 h-4" />;
    default:           return <ExternalLink className="w-4 h-4" />;
  }
}

/** Parse a raw evidence value (string or array) into structured chunk objects */
function parseEvidenceChunks(raw) {
  if (!raw) return [];
  let parsed = raw;
  if (typeof raw === 'string') {
    try { parsed = JSON.parse(raw); } catch { return [{ text: raw, source: null }]; }
  }
  if (Array.isArray(parsed)) return parsed;
  if (typeof parsed === 'object') return [parsed];
  return [{ text: String(parsed), source: null }];
}

/** Extract GitHub repo data embedded in evidence chunks */
function extractGitHubData(evidenceData) {
  const repos = [];
  const seen = new Set();
  Object.values(evidenceData).forEach(rawChunks => {
    const chunks = parseEvidenceChunks(rawChunks);
    chunks.forEach(chunk => {
      const src = (chunk.source || '').toLowerCase();
      if (src !== 'github' && src !== 'github_profile') return;
      const repoName = chunk.repo || chunk.name || null;
      if (repoName && !seen.has(repoName)) {
        seen.add(repoName);
        repos.push({
          repo: repoName,
          description: chunk.description || null,
          stars: chunk.stars ?? null,
          forks: chunk.forks ?? null,
          language: chunk.language || null,
          readme_preview: chunk.readme_preview || null,
          url: chunk.url || (repoName.startsWith('http') ? repoName : `https://github.com/${repoName}`),
        });
      } else if (!repoName) {
        // plain text chunk from github
        repos.push({ text: chunk.text, url: null });
      }
    });
  });
  return repos;
}

/* ─── Sub-components ─── */

function SectionHeader({ title, subtitle }) {
  return (
    <div className="mb-6">
      <h3 className="text-xl font-heading font-bold text-dark">{title}</h3>
      {subtitle && <p className="text-sm text-mid mt-1">{subtitle}</p>}
    </div>
  );
}

function GitHubRepoCard({ repo }) {
  if (repo.text) {
    return (
      <div className="p-5 rounded-xl border border-mid/10 bg-white/60 hover:bg-white hover:shadow-sm transition-all">
        <p className="text-[15px] text-dark leading-relaxed whitespace-pre-wrap">{repo.text}</p>
      </div>
    );
  }
  return (
    <a
      href={repo.url || '#'}
      target="_blank"
      rel="noreferrer"
      className="block p-5 rounded-xl border border-mid/10 bg-white/60 hover:bg-white hover:shadow-md hover:border-primary/30 transition-all group"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-dark/60 flex-shrink-0" />
          <span className="font-semibold text-dark text-sm group-hover:text-primary transition-colors truncate">
            {repo.repo}
          </span>
        </div>
        <ExternalLink className="w-4 h-4 text-mid/50 group-hover:text-primary flex-shrink-0 transition-colors" />
      </div>
      {repo.description && (
        <p className="text-sm text-mid leading-relaxed mb-3">{repo.description}</p>
      )}
      {repo.readme_preview && (
        <p className="text-xs text-mid/70 leading-relaxed mb-3 line-clamp-3 italic">
          {repo.readme_preview.replace(/#+\s*/g, '').replace(/\n+/g, ' ')}
        </p>
      )}
      <div className="flex flex-wrap gap-3 mt-2">
        {repo.language && (
          <span className="inline-flex items-center gap-1 text-xs bg-primary/10 text-primary px-2.5 py-1 rounded-full font-medium">
            <Code className="w-3 h-3" /> {repo.language}
          </span>
        )}
        {repo.stars !== null && (
          <span className="inline-flex items-center gap-1 text-xs bg-soft/60 text-dark/70 px-2.5 py-1 rounded-full">
            <Star className="w-3 h-3 text-warning" /> {repo.stars}
          </span>
        )}
        {repo.forks !== null && (
          <span className="inline-flex items-center gap-1 text-xs bg-soft/60 text-dark/70 px-2.5 py-1 rounded-full">
            <GitFork className="w-3 h-3" /> {repo.forks}
          </span>
        )}
      </div>
    </a>
  );
}

function EvidenceChunkCard({ chunk, idx }) {
  const text = chunk.text || (typeof chunk === 'string' ? chunk : JSON.stringify(chunk));
  if (!text) return null;
  return (
    <div className="flex gap-4 p-5 rounded-xl border border-mid/10 bg-white/60 hover:bg-white/90 transition-all">
      <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
        <span className="text-xs font-bold text-primary">{idx + 1}</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[15px] text-dark leading-relaxed whitespace-pre-wrap break-words">{text}</p>
        <div className="flex flex-wrap gap-2 mt-3">
          {chunk.source && (
            <span className="text-[11px] font-mono text-mid/80 bg-light px-2.5 py-1 rounded border border-mid/10 uppercase tracking-wider">
              {chunk.source}
            </span>
          )}
          {chunk.confidence != null && (
            <span className="text-[11px] font-mono text-primary/90 bg-primary/10 px-2.5 py-1 rounded border border-primary/20 uppercase tracking-wider">
              Confidence: {Math.round((chunk.confidence || 0) * 100)}%
            </span>
          )}
          {chunk.similarity != null && (
            <span className="text-[11px] font-mono text-secondary/90 bg-secondary/10 px-2.5 py-1 rounded border border-secondary/20 uppercase tracking-wider">
              Match: {Math.round((chunk.similarity || 0) * 100)}%
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Main Page ─── */

export function CandidateDashboardPage() {
  const { jobId, candidateId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [activeTab, setActiveTab] = useState('overview');
  const [showResume, setShowResume] = useState(false);
  const [resumeData, setResumeData] = useState(null);
  const [resumeLoading, setResumeLoading] = useState(false);

  const handleViewResume = async () => {
    if (resumeData) { setShowResume(true); return; }
    const resumeId = data?.resume_id;
    if (!resumeId) { setShowResume(true); return; }
    setResumeLoading(true);
    try {
      const result = await api.getResumeContent(resumeId);
      setResumeData(result);
    } catch (err) {
      // Fallback: use parsed text from dashboard payload
      setResumeData({ raw_text: data?.resume_text || data?.parsed_text || '', filename: 'resume.pdf' });
    } finally {
      setResumeLoading(false);
      setShowResume(true);
    }
  };

  const { data, isLoading, isError } = useQuery({
    queryKey: ['candidate', jobId, candidateId],
    queryFn: () => api.getCandidateDashboard(jobId, candidateId),
  });

  if (isLoading) return <Loader variant="spinner" text="Loading candidate profile..." className="h-64" />;
  if (isError || !data) return (
    <EmptyState
      title="Candidate Not Found"
      message="Could not load the candidate details."
      action={<Button onClick={() => navigate(`/jobs/${jobId}/candidates`)}>Back to Rankings</Button>}
    />
  );

  /* ── Data extraction ── */
  const summary       = data?.summary || {};
  const name          = summary?.name || data?.name || 'Unknown Candidate';
  const email         = summary?.email || data?.email || '';
  const score         = data?.final_score ?? data?.score ?? 0;
  const recommendation = data?.recommendation || 'Not Evaluated';
  const links         = summary?.external_profiles || data?.external_profiles || {};
  const resumeSummary = summary?.resume_summary || (typeof data?.summary === 'string' ? data.summary : '') || '';
  const resumeText    = data?.resume_text || data?.parsed_text || data?.text || summary?.resume_text || '';
  const skillScores   = Array.isArray(data?.skill_scores)  ? data.skill_scores  : [];
  const strengths     = Array.isArray(data?.strengths)     ? data.strengths     : [];
  const weaknesses    = Array.isArray(data?.weaknesses)    ? data.weaknesses    : [];
  const evidenceData  = data?.evidence_chunks || data?.evidence || {};
  const externalProfiles = data?.external_profiles || null;
  const hasProfiles   = externalProfiles && (externalProfiles.github || externalProfiles.leetcode || externalProfiles.codeforces || externalProfiles.codechef);

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'skills',   label: 'Skills' },
    ...(hasProfiles ? [{ id: 'profiles', label: '🌐 Platform Profiles' }] : []),
    { id: 'evidence', label: 'Evidence' },
    { id: 'raw',      label: 'Raw JSON' },
  ];

  const getRecommendationStyle = (rec) => {
    const v = (rec || '').toLowerCase();
    if (v.includes('strong'))          return { bg: 'bg-primary/15', text: 'text-primary', border: 'border-primary/30' };
    if (v.includes('not recommended')) return { bg: 'bg-error/15',   text: 'text-error',   border: 'border-error/30' };
    if (v.includes('maybe'))           return { bg: 'bg-warning/15', text: 'text-warning', border: 'border-warning/30' };
    return { bg: 'bg-mid/10', text: 'text-mid', border: 'border-mid/20' };
  };

  const recStyle = getRecommendationStyle(recommendation);

  return (
    <div className="w-full animate-fade-slide-up pb-16">
      {/* Resume Viewer Modal */}
      {showResume && (
        <ResumeViewerModal
          resumeId={data?.resume_id}
          candidateName={name}
          resumeData={resumeData}
          onClose={() => setShowResume(false)}
        />
      )}
      {/* Back button */}
      <div className="mb-6">
        <Button variant="outline" onClick={() => navigate(`/jobs/${jobId}/candidates`)}>
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Rankings
        </Button>
      </div>

      <div className="flex flex-col xl:flex-row gap-8 items-start">

        {/* ── LEFT SIDEBAR CARD ── */}
        <div className="w-full xl:w-[340px] flex-shrink-0 xl:sticky xl:top-28 space-y-4">
          {/* Identity & Score */}
          <Card className="!p-0 overflow-hidden">
            {/* Avatar header */}
            <div className="bg-gradient-to-br from-primary/10 to-secondary/10 px-8 pt-8 pb-6 text-center border-b border-mid/10">
              <div className="w-20 h-20 rounded-full bg-white shadow-md border-4 border-white flex items-center justify-center mx-auto mb-4">
                <User className="w-9 h-9 text-primary" />
              </div>
              <h2 className="text-xl font-heading font-bold text-dark leading-tight">{name}</h2>
              {email && (
                <div className="flex items-center justify-center text-mid text-sm mt-2 gap-1.5">
                  <Mail className="w-3.5 h-3.5 flex-shrink-0" />
                  <span className="truncate max-w-[200px]">{email}</span>
                </div>
              )}
            </div>

            {/* Score */}
            <div className="flex flex-col items-center py-8 border-b border-mid/10 bg-white/30">
              <ScoreGauge score={score} size={160} />
            </div>

            {/* Recommendation */}
            <div className="px-8 py-5 border-b border-mid/10 bg-white/20">
              <p className="text-xs font-semibold uppercase tracking-widest text-mid/70 mb-3 text-center">AI Recommendation</p>
              <div className={`text-center rounded-xl px-4 py-2.5 border font-semibold text-sm ${recStyle.bg} ${recStyle.text} ${recStyle.border}`}>
                {recommendation}
              </div>
            </div>

            {/* External profiles */}
            {Object.keys(links).length > 0 && (
              <div className="px-6 py-5 border-b border-mid/10">
                <p className="text-xs font-semibold uppercase tracking-widest text-mid/70 mb-3">External Profiles</p>
                <div className="space-y-2">
                  {Object.entries(links).filter(([, v]) => v).map(([platform, url]) => (
                    <a
                      key={platform}
                      href={formatExternalUrl(platform, url)}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-light/60 border border-mid/10 text-sm font-medium text-dark hover:text-primary hover:border-primary/40 hover:bg-white hover:shadow-sm transition-all group"
                    >
                      <span className="text-mid group-hover:text-primary transition-colors">{getPlatformIcon(platform)}</span>
                      <span className="capitalize flex-1">{platform}</span>
                      <ExternalLink className="w-3.5 h-3.5 text-mid/50 group-hover:text-primary flex-shrink-0 transition-colors" />
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Resume viewer button */}
            <div className="px-6 py-5">
              <button
                onClick={handleViewResume}
                disabled={resumeLoading}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-primary text-white font-semibold text-sm hover:bg-mid transition-colors shadow-sm hover:shadow-md active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {resumeLoading ? (
                  <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Loading…</>
                ) : (
                  <><FileText className="w-4 h-4" /> View Resume</>
                )}
              </button>
            </div>
          </Card>
        </div>

        {/* ── RIGHT CONTENT AREA ── */}
        <div className="flex-1 min-w-0 w-full">

          {/* Tab bar */}
          <div className="bg-white/60 backdrop-blur-sm rounded-2xl border border-mid/10 shadow-sm mb-6 overflow-x-auto">
            <div className="flex px-2">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-6 py-4 text-sm font-semibold whitespace-nowrap transition-all border-b-2 ${
                    activeTab === tab.id
                      ? 'border-primary text-primary'
                      : 'border-transparent text-mid hover:text-dark'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* ── OVERVIEW TAB ── */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              <Card className="!p-8">
                <SectionHeader title="Resume Summary" subtitle="AI-generated summary of the candidate's profile" />
                <p className="text-[15px] text-dark/80 leading-8 whitespace-pre-wrap">
                  {resumeSummary || 'No summary available.'}
                </p>
              </Card>

              <div className="grid md:grid-cols-2 gap-5">
                <Card className="!p-0 overflow-hidden">
                  <div className="px-6 py-4 bg-primary/8 border-b border-primary/15 flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                      <Check className="w-4 h-4 text-primary" />
                    </div>
                    <h3 className="font-heading font-semibold text-dark">Strengths</h3>
                    <span className="ml-auto text-xs font-mono bg-primary/15 text-primary px-2 py-0.5 rounded-full">
                      {strengths.length}
                    </span>
                  </div>
                  <div className="p-6 space-y-3">
                    {strengths.length > 0 ? strengths.map((s, i) => (
                      <div key={i} className="flex items-start gap-3">
                        <div className="w-5 h-5 rounded-full bg-primary/15 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <Check className="w-3 h-3 text-primary" />
                        </div>
                        <span className="text-[15px] text-dark/85 leading-relaxed">{s}</span>
                      </div>
                    )) : (
                      <p className="text-sm text-mid/60 italic">No specific strengths listed.</p>
                    )}
                  </div>
                </Card>

                <Card className="!p-0 overflow-hidden">
                  <div className="px-6 py-4 bg-warning/8 border-b border-warning/15 flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-warning/20 flex items-center justify-center">
                      <AlertTriangle className="w-4 h-4 text-warning" />
                    </div>
                    <h3 className="font-heading font-semibold text-dark">Areas for Improvement</h3>
                    <span className="ml-auto text-xs font-mono bg-warning/15 text-warning px-2 py-0.5 rounded-full">
                      {weaknesses.length}
                    </span>
                  </div>
                  <div className="p-6 space-y-3">
                    {weaknesses.length > 0 ? weaknesses.map((w, i) => (
                      <div key={i} className="flex items-start gap-3">
                        <div className="w-5 h-5 rounded-full bg-warning/15 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <AlertTriangle className="w-3 h-3 text-warning" />
                        </div>
                        <span className="text-[15px] text-dark/85 leading-relaxed">{w}</span>
                      </div>
                    )) : (
                      <p className="text-sm text-mid/60 italic">No specific areas listed.</p>
                    )}
                  </div>
                </Card>
              </div>
            </div>
          )}

          {/* ── SKILLS TAB ── */}
          {activeTab === 'skills' && (
            <Card className="!p-8">
              <SectionHeader title="Skill Evaluation" subtitle={`${skillScores.length} skills evaluated by the AI pipeline`} />
              {skillScores.length > 0 ? (
                <div className="grid md:grid-cols-2 gap-x-14 gap-y-1">
                  {[...skillScores]
                    .sort((a, b) => (b.score || 0) - (a.score || 0))
                    .map((skill, i) => (
                      <SkillScoreBar
                        key={i}
                        label={skill.skill || skill.name || `Skill ${i + 1}`}
                        score={skill.score}
                      />
                    ))}
                </div>
              ) : (
                <p className="text-mid italic">No skill scores available.</p>
              )}
            </Card>
          )}

          {/* ── PLATFORM PROFILES TAB ── */}
          {activeTab === 'profiles' && (
            <ExternalProfilesSection profiles={externalProfiles} />
          )}

          {/* ── EVIDENCE TAB ── */}
          {activeTab === 'evidence' && (
            <div className="space-y-6">
              {data?.explanation && (
                <Card className="!p-8">
                  <SectionHeader title="Evaluation Explanation" />
                  <p className="text-[15px] text-dark/80 leading-8">{data.explanation}</p>
                </Card>
              )}

              {Object.keys(evidenceData).length > 0 ? (
                Object.entries(evidenceData).map(([section, rawChunks]) => {
                  const chunks = parseEvidenceChunks(rawChunks);
                  if (!chunks.length) return null;
                  return (
                    <div key={section}>
                      <h4 className="text-sm font-semibold uppercase tracking-widest text-mid/70 mb-3 px-1">
                        {section.replace(/_/g, ' ')}
                      </h4>
                      <div className="space-y-3">
                        {chunks.map((chunk, i) => (
                          <EvidenceChunkCard key={i} chunk={chunk} idx={i} />
                        ))}
                      </div>
                    </div>
                  );
                })
              ) : (
                <Card className="bg-light/50 border-dashed">
                  <p className="text-mid italic text-center py-4">No evidence chunks extracted.</p>
                </Card>
              )}
            </div>
          )}

          {/* ── RAW JSON TAB ── */}
          {activeTab === 'raw' && (
            <Card className="!p-0 overflow-hidden relative group">
              <div className="flex items-center justify-between px-6 py-4 border-b border-mid/10 bg-dark/5">
                <span className="text-sm font-mono text-mid/80">Raw API Response</span>
                <Button
                  variant="secondary"
                  onClick={() => {
                    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
                    toast('Copied to clipboard', 'success');
                  }}
                >
                  <Copy className="w-4 h-4 mr-2" /> Copy JSON
                </Button>
              </div>
              <pre className="text-xs font-mono text-dark/80 bg-light/50 p-6 overflow-auto max-h-[600px] leading-relaxed">
                {JSON.stringify(data, null, 2)}
              </pre>
            </Card>
          )}
        </div>
      </div>

      {/* ── RESUME MODAL ── */}
      {showResume && resumeText && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-8"
          onClick={() => setShowResume(false)}
        >
          <div className="absolute inset-0 bg-dark/40 backdrop-blur-sm" />
          <div
            className="relative bg-cream rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden border border-mid/20"
            onClick={e => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="flex items-center justify-between px-8 py-5 border-b border-mid/10 bg-white/60 backdrop-blur-sm">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-primary/15 flex items-center justify-center">
                  <FileText className="w-4 h-4 text-primary" />
                </div>
                <div>
                  <h3 className="font-heading font-semibold text-dark">Parsed Resume Content</h3>
                  <p className="text-xs text-mid">{name}</p>
                </div>
              </div>
              <button
                onClick={() => setShowResume(false)}
                className="w-8 h-8 rounded-full bg-mid/10 hover:bg-mid/20 flex items-center justify-center transition-colors text-dark/60 hover:text-dark"
              >
                ✕
              </button>
            </div>
            {/* Modal body */}
            <div className="flex-1 overflow-y-auto p-8">
              <pre className="whitespace-pre-wrap font-sans text-[15px] leading-8 text-dark/85">
                {resumeText}
              </pre>
            </div>
            {/* Modal footer */}
            <div className="px-8 py-4 border-t border-mid/10 bg-white/40 flex justify-end">
              <Button variant="outline" onClick={() => setShowResume(false)}>Close</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
