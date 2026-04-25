import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { ResumeUploadForm } from '../components/resume/ResumeUploadForm';
import { ResumeStatusTracker } from '../components/resume/ResumeStatusTracker';
import { usePollResumeStatus } from '../hooks/usePollResumeStatus';
import { Button } from '../components/ui/Button';
import { useToast } from '../hooks/useToast';
import { ArrowLeft, RefreshCw } from 'lucide-react';

export function ResumeUploadPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  
  const [isUploading, setIsUploading] = useState(false);
  const [resumeId, setResumeId] = useState(null);
  
  const { data: statusData } = usePollResumeStatus(resumeId, !!resumeId);

  const handleUpload = async (file, links) => {
    setIsUploading(true);
    setResumeId(null);
    
    try {
      const formData = new FormData();
      formData.append('job_id', jobId);
      formData.append('file', file);
      
      if (links.github) formData.append('github_url', links.github);
      if (links.leetcode) formData.append('leetcode_url', links.leetcode);
      if (links.codeforces) formData.append('codeforces_url', links.codeforces);
      if (links.codechef) formData.append('codechef_url', links.codechef);
      
      const res = await api.uploadResume(formData);
      setResumeId(res.resume_id);
      toast('Resume uploaded! Processing started.', 'success');
    } catch (err) {
      toast(err.message || 'Failed to upload resume', 'error');
    } finally {
      setIsUploading(false);
    }
  };

  const handleReset = () => {
    setResumeId(null);
  };

  return (
    <div className="max-w-screen-xl mx-auto animate-fade-slide-up">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-dark mb-2">Upload Resume</h1>
          <p className="text-mid">Add a candidate's resume for evaluation.</p>
        </div>
        <Button variant="outline" onClick={() => navigate(`/jobs/${jobId}`)}>
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Job
        </Button>
      </div>

      {!resumeId ? (
        <ResumeUploadForm onSubmit={handleUpload} isUploading={isUploading} />
      ) : (
        <div className="space-y-6">
          <ResumeStatusTracker 
            status={statusData?.status || 'uploaded'} 
            error={statusData?.error_message} 
          />
          
          <div className="flex justify-center pt-8">
            <Button variant="secondary" onClick={handleReset}>
              <RefreshCw className="w-4 h-4 mr-2" /> Upload Another Resume
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
