import React from 'react';
import { ExternalLink, GitBranch, Code, Terminal, Award, Star, GitFork, Zap, Target, TrendingUp, BookOpen } from 'lucide-react';
import { Card } from '../ui/Card';

/* ── Helpers ────────────────────────────────────────────────────── */

function StatPill({ label, value, color = 'primary' }) {
  if (value === null || value === undefined) return null;
  const colorMap = {
    primary: 'bg-primary/10 text-primary border-primary/20',
    warning: 'bg-warning/10 text-warning border-warning/20',
    error: 'bg-error/10 text-error border-error/20',
    mid: 'bg-mid/10 text-mid border-mid/20',
    dark: 'bg-dark/10 text-dark border-dark/20',
  };
  return (
    <div className={`flex flex-col items-center px-4 py-3 rounded-xl border ${colorMap[color]} text-center`}>
      <span className="text-xl font-bold font-mono">{value}</span>
      <span className="text-[10px] uppercase tracking-widest mt-0.5 opacity-80">{label}</span>
    </div>
  );
}

function PlatformHeader({ icon: Icon, title, username, url, badgeText, badgeColor = 'primary' }) {
  const colorMap = {
    primary: 'bg-primary/10 border-primary/20 text-primary',
    warning: 'bg-warning/10 border-warning/20 text-warning',
    dark: 'bg-dark/10 border-dark/20 text-dark',
    mid: 'bg-mid/10 border-mid/20 text-mid',
  };
  return (
    <div className="flex items-center justify-between gap-4 pb-5 mb-5 border-b border-mid/10">
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center border ${colorMap[badgeColor]}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <h4 className="font-heading font-semibold text-dark text-base">{title}</h4>
          {username && (
            <p className="text-xs text-mid font-mono">@{username}</p>
          )}
        </div>
      </div>
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 text-xs font-medium text-mid hover:text-primary transition-colors"
        >
          View Profile <ExternalLink className="w-3.5 h-3.5" />
        </a>
      )}
    </div>
  );
}

/* ── GitHub Section ─────────────────────────────────────────────── */

function GitHubSection({ data }) {
  if (!data) return null;
  const activityColor = data.commit_activity_level === 'high' ? 'bg-primary' : data.commit_activity_level === 'medium' ? 'bg-warning' : 'bg-mid/40';

  return (
    <Card className="!p-7">
      <PlatformHeader
        icon={GitBranch}
        title="GitHub"
        username={data.username}
        url={`https://github.com/${data.username}`}
        badgeColor="dark"
      />

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <StatPill label="Repos" value={data.repo_count} color="dark" />
        <StatPill label="Followers" value={data.followers} color="mid" />
        <div className="flex flex-col items-center px-4 py-3 rounded-xl border border-mid/20 bg-mid/5 text-center">
          <div className="flex items-center gap-1.5 mb-1">
            <div className={`w-2 h-2 rounded-full ${activityColor}`} />
            <span className="text-sm font-bold capitalize text-dark">{data.commit_activity_level}</span>
          </div>
          <span className="text-[10px] uppercase tracking-widest text-mid/70">Activity</span>
        </div>
      </div>

      {/* Languages */}
      {data.languages && data.languages.length > 0 && (
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-mid/70 mb-2">Languages</p>
          <div className="flex flex-wrap gap-2">
            {data.languages.map(lang => (
              <span key={lang} className="text-xs bg-primary/10 text-primary border border-primary/20 px-3 py-1 rounded-full font-medium">
                {lang}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Top Repos */}
      {data.top_repositories && data.top_repositories.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-mid/70 mb-3">Top Repositories</p>
          <div className="space-y-3">
            {data.top_repositories.map((repo, i) => (
              <a
                key={i}
                href={repo.url || `https://github.com/${data.username}/${repo.name}`}
                target="_blank"
                rel="noreferrer"
                className="block p-4 rounded-xl border border-mid/10 bg-light/40 hover:bg-white hover:border-primary/30 hover:shadow-sm transition-all group"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-semibold text-dark text-sm group-hover:text-primary transition-colors">{repo.name}</span>
                  <div className="flex items-center gap-3 text-xs text-mid">
                    {repo.stars > 0 && (
                      <span className="flex items-center gap-1">
                        <Star className="w-3 h-3 text-warning" /> {repo.stars}
                      </span>
                    )}
                    {repo.forks > 0 && (
                      <span className="flex items-center gap-1">
                        <GitFork className="w-3 h-3" /> {repo.forks}
                      </span>
                    )}
                  </div>
                </div>
                {repo.description && (
                  <p className="text-xs text-mid leading-relaxed">{repo.description}</p>
                )}
                {repo.tech_stack && repo.tech_stack.length > 0 && (
                  <div className="mt-2 flex gap-1.5">
                    {repo.tech_stack.map(t => (
                      <span key={t} className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded font-mono">{t}</span>
                    ))}
                  </div>
                )}
              </a>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

/* ── LeetCode Section ───────────────────────────────────────────── */

function LeetCodeSection({ data }) {
  if (!data) return null;
  const solved = data.total_solved || 0;
  const easy = data.easy_solved || 0;
  const med = data.medium_solved || 0;
  const hard = data.hard_solved || 0;
  const maxBar = Math.max(easy, med, hard, 1);

  return (
    <Card className="!p-7">
      <PlatformHeader
        icon={Code}
        title="LeetCode"
        username={data.username}
        url={`https://leetcode.com/u/${data.username}`}
        badgeColor="warning"
      />

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <StatPill label="Total Solved" value={solved} color="warning" />
        <StatPill label="Contest Rating" value={data.contest_rating ? Math.round(data.contest_rating) : 'N/A'} color="primary" />
      </div>

      {/* Difficulty breakdown */}
      <div className="space-y-3 mb-5">
        {[
          { label: 'Easy', value: easy, color: 'bg-primary', textColor: 'text-primary' },
          { label: 'Medium', value: med, color: 'bg-warning', textColor: 'text-warning' },
          { label: 'Hard', value: hard, color: 'bg-error', textColor: 'text-error' },
        ].map(({ label, value, color, textColor }) => (
          <div key={label}>
            <div className="flex justify-between text-xs mb-1">
              <span className={`font-semibold ${textColor}`}>{label}</span>
              <span className="font-mono text-mid">{value}</span>
            </div>
            <div className="h-2 bg-mid/15 rounded-full overflow-hidden">
              <div
                className={`h-full ${color} rounded-full transition-all duration-700`}
                style={{ width: `${(value / maxBar) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Badges */}
      {data.badges && data.badges.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-mid/70 mb-2">Badges</p>
          <div className="flex flex-wrap gap-2">
            {data.badges.slice(0, 6).map((badge, i) => (
              <span key={i} className="text-xs bg-warning/10 text-warning border border-warning/20 px-2.5 py-1 rounded-full">
                {badge}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

/* ── Codeforces Section ─────────────────────────────────────────── */

function CodeforcesSection({ data }) {
  if (!data) return null;
  return (
    <Card className="!p-7">
      <PlatformHeader
        icon={Terminal}
        title="Codeforces"
        username={data.username}
        url={`https://codeforces.com/profile/${data.username}`}
        badgeColor="primary"
      />
      <div className="grid grid-cols-2 gap-3">
        <StatPill label="Current Rating" value={data.rating} color="primary" />
        <StatPill label="Max Rating" value={data.max_rating} color="mid" />
        {data.rank && (
          <div className="col-span-2 flex items-center gap-3 px-4 py-3 bg-primary/5 rounded-xl border border-primary/15">
            <TrendingUp className="w-4 h-4 text-primary" />
            <div>
              <p className="font-semibold text-dark text-sm capitalize">{data.rank}</p>
              <p className="text-xs text-mid">Current Rank</p>
            </div>
            {data.max_rank && data.max_rank !== data.rank && (
              <>
                <div className="mx-2 w-px h-8 bg-mid/20" />
                <div>
                  <p className="font-semibold text-dark text-sm capitalize">{data.max_rank}</p>
                  <p className="text-xs text-mid">Best Rank</p>
                </div>
              </>
            )}
          </div>
        )}
        <StatPill label="Contests" value={data.contest_count} color="dark" />
      </div>
    </Card>
  );
}

/* ── CodeChef Section ───────────────────────────────────────────── */

function CodeChefSection({ data }) {
  if (!data) return null;
  return (
    <Card className="!p-7">
      <PlatformHeader
        icon={Award}
        title="CodeChef"
        username={data.username}
        url={`https://www.codechef.com/users/${data.username}`}
        badgeColor="warning"
      />
      <div className="grid grid-cols-2 gap-3">
        <StatPill label="Rating" value={data.rating} color="warning" />
        <StatPill label="Highest" value={data.highest_rating} color="mid" />
        {data.stars && (
          <div className="col-span-2 flex items-center gap-2 px-4 py-3 bg-warning/5 rounded-xl border border-warning/15">
            <Star className="w-4 h-4 text-warning" />
            <span className="font-semibold text-dark text-sm">{data.stars}</span>
            <span className="text-xs text-mid">Star Rating</span>
          </div>
        )}
        <StatPill label="Problems Solved" value={data.problems_solved} color="primary" />
      </div>
    </Card>
  );
}

/* ── Main Export ────────────────────────────────────────────────── */

export function ExternalProfilesSection({ profiles }) {
  if (!profiles) return null;

  const { github, leetcode, codeforces, codechef, summary } = profiles;
  const hasAny = github || leetcode || codeforces || codechef;

  if (!hasAny) {
    return (
      <Card className="bg-light/50 border-dashed text-center py-10">
        <Zap className="w-8 h-8 text-mid/30 mx-auto mb-3" />
        <p className="text-mid/60 italic text-sm">No external platform profiles found for this candidate.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      {/* Summary banner */}
      {summary && (
        <Card className="!p-6 bg-gradient-to-r from-primary/5 to-secondary/5 border-primary/15">
          <div className="flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl bg-primary/15 flex items-center justify-center flex-shrink-0">
              <BookOpen className="w-4 h-4 text-primary" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-primary mb-1">Platform Summary</p>
              <p className="text-[15px] text-dark/85 leading-relaxed">{summary}</p>
            </div>
          </div>
        </Card>
      )}

      {/* Platform cards grid */}
      <div className="grid md:grid-cols-2 gap-5">
        <GitHubSection data={github} />
        <LeetCodeSection data={leetcode} />
        <CodeforcesSection data={codeforces} />
        <CodeChefSection data={codechef} />
      </div>
    </div>
  );
}
