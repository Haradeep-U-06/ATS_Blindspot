import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { DashboardPage } from './pages/DashboardPage';
import { CreateJobPage } from './pages/CreateJobPage';
import { JobDetailPage } from './pages/JobDetailPage';
import { ResumeUploadPage } from './pages/ResumeUploadPage';
import { CandidateRankingPage } from './pages/CandidateRankingPage';
import { CandidateDashboardPage } from './pages/CandidateDashboardPage';

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/jobs" element={<Navigate to="/" replace />} />
        <Route path="/jobs/new" element={<CreateJobPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        <Route path="/jobs/:jobId/upload" element={<ResumeUploadPage />} />
        <Route path="/jobs/:jobId/candidates" element={<CandidateRankingPage />} />
        <Route path="/jobs/:jobId/candidates/:candidateId" element={<CandidateDashboardPage />} />
      </Routes>
    </Layout>
  );
}

export default App;
