import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { Button } from '../components/ui/Button';
import { useToast } from '../hooks/useToast';
import { Briefcase, FileText, Loader2, ArrowLeft } from 'lucide-react';

export function CreateJobPage() {
  const [formData, setFormData]   = useState({ title: '', description: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError]         = useState('');
  const navigate  = useNavigate();
  const toast     = useToast();

  const charCount   = formData.description.length;
  const isDescValid = charCount >= 20;
  const canSubmit   = formData.title.trim() && isDescValid && !isSubmitting;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.title.trim() || !isDescValid) {
      setError('Title and a description of at least 20 characters are required.');
      return;
    }
    setIsSubmitting(true);
    setError('');
    try {
      const res = await api.createJob({
        title:       formData.title,
        jd_text:     formData.description,
        description: formData.description,
      });
      toast('Job created successfully!', 'success');
      navigate(`/jobs/${res.job_id}`);
    } catch (err) {
      setError(err.message || 'Failed to create job. Please try again.');
      toast('Failed to create job', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto animate-fade-slide-up">

      {/* Page header */}
      <div className="mb-8">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-sm text-mid hover:text-dark transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </button>
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
            <Briefcase className="w-6 h-6 text-primary" />
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.15em] text-primary mb-0.5">New Posting</p>
            <h1 className="text-3xl font-heading font-bold text-dark">Create Job</h1>
          </div>
        </div>
        <p className="text-mid mt-3 ml-16">
          Add a new role and paste the full job description to begin AI-powered candidate screening.
        </p>
      </div>

      {/* Form card */}
      <div className="bg-white rounded-2xl border border-mid/10 shadow-sm overflow-hidden">

        {/* Card header */}
        <div className="px-8 py-5 border-b border-mid/10 bg-light/40">
          <h2 className="font-heading font-semibold text-dark text-base">Job Details</h2>
          <p className="text-xs text-mid mt-0.5">All fields are required</p>
        </div>

        <form onSubmit={handleSubmit} className="px-8 py-7 space-y-6">

          {/* Job Title */}
          <div>
            <label htmlFor="title" className="block text-sm font-semibold text-dark mb-2">
              Job Title
            </label>
            <input
              id="title"
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full px-4 py-3 rounded-xl border border-mid/20 bg-white text-dark placeholder-mid/40 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all text-[15px]"
              placeholder="e.g. Senior Frontend Engineer"
              disabled={isSubmitting}
            />
          </div>

          {/* Job Description */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label htmlFor="description" className="block text-sm font-semibold text-dark">
                Job Description
              </label>
              <span className={`text-xs font-mono px-2 py-0.5 rounded-full ${
                isDescValid
                  ? 'bg-primary/10 text-primary'
                  : 'bg-warning/10 text-warning'
              }`}>
                {charCount} / 20+ chars
              </span>
            </div>
            <textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-4 py-3 rounded-xl border border-mid/20 bg-white text-dark placeholder-mid/40 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all min-h-[280px] resize-y text-[15px] leading-relaxed"
              placeholder="Paste the full job description here. Include responsibilities, requirements, and any other relevant details..."
              disabled={isSubmitting}
            />
            <p className="text-xs text-mid/60 mt-2 flex items-center gap-1.5">
              <FileText className="w-3 h-3" />
              Include skills, responsibilities, and experience requirements for best AI matching results.
            </p>
          </div>

          {/* Error message */}
          {error && (
            <div className="flex items-start gap-3 p-4 bg-error/8 border border-error/20 rounded-xl text-error text-sm">
              <span className="mt-0.5 text-lg leading-none">⚠</span>
              <span>{error}</span>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center justify-between pt-4 border-t border-mid/10">
            <button
              type="button"
              onClick={() => navigate('/')}
              disabled={isSubmitting}
              className="text-sm font-medium text-mid hover:text-dark transition-colors disabled:opacity-50"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={!canSubmit}
              className={`inline-flex items-center gap-2 px-6 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200 ${
                canSubmit
                  ? 'bg-primary text-white hover:bg-mid shadow-sm hover:shadow-md active:scale-[0.98]'
                  : 'bg-mid/20 text-mid cursor-not-allowed'
              }`}
            >
              {isSubmitting ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Creating…</>
              ) : (
                <><Briefcase className="w-4 h-4" /> Create Job</>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
