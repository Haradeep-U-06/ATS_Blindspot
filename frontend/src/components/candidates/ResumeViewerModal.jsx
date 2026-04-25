import React, { useEffect, useRef, useState } from 'react';
import { X, FileText, Download, ExternalLink, Loader2, AlertTriangle } from 'lucide-react';

/* ── Raw-text viewer (fallback) ─────────────────────────────────── */

function RawTextViewer({ text, filename }) {
  if (!text) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-mid/50 gap-3 py-16">
        <FileText className="w-12 h-12 opacity-30" />
        <p className="text-sm">No extracted text available for this resume.</p>
      </div>
    );
  }

  const lines = text.split('\n');
  return (
    <div className="flex-1 overflow-y-auto px-8 py-6 font-mono text-sm text-dark/85 leading-relaxed whitespace-pre-wrap bg-white">
      {text}
      <div className="pt-8 text-xs text-mid/40 border-t border-mid/10 mt-6">
        {lines.length} lines · {text.length.toLocaleString()} characters · {filename}
      </div>
    </div>
  );
}

/* ── PDF viewer ─────────────────────────────────────────────────── */

function PdfViewer({ url, filename }) {
  const [loading, setLoading] = useState(true);

  // We use the Google Docs viewer as a fallback wrapper to ensure maximum compatibility
  // though direct iframe for image/upload usually works fine.
  const viewerUrl = `https://docs.google.com/viewer?url=${encodeURIComponent(url)}&embedded=true`;

  return (
    <div className="flex-1 flex flex-col overflow-hidden relative">
      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center gap-3 bg-white text-mid">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          <span className="text-sm">Loading Preview...</span>
        </div>
      )}
      <iframe
        src={viewerUrl}
        title={filename}
        className="flex-1 w-full border-0"
        onLoad={() => setLoading(false)}
      />
    </div>
  );
}

/* ── Main Modal ─────────────────────────────────────────────────── */

export function ResumeViewerModal({ resumeId, candidateName, onClose, resumeData }) {
  const overlayRef = useRef(null);
  const [activeView, setActiveView] = useState('pdf'); // 'pdf' | 'text'

  const { filename, cloudinary_url: pdfUrl, raw_text: rawText } = resumeData || {};
  const hasPdf  = Boolean(pdfUrl);
  const hasText = Boolean(rawText);

  // The pdfUrl is now always http://localhost:8000/resume/{id}/pdf — no proxy needed
  const proxyUrl = pdfUrl || null;

  // Default to text view if no PDF
  useEffect(() => {
    if (!hasPdf && hasText) setActiveView('text');
  }, [hasPdf, hasText]);

  // Close on overlay click
  const handleOverlayClick = (e) => {
    if (e.target === overlayRef.current) onClose();
  };

  // Close on Escape key
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  // Prevent body scroll when modal open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-dark/60 backdrop-blur-sm p-4 animate-fade-in"
    >
      <div className="w-full max-w-4xl h-[90vh] flex flex-col bg-white rounded-2xl shadow-2xl overflow-hidden animate-slide-up border border-white/20">

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-mid/10 bg-light/50 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
              <FileText className="w-4 h-4 text-primary" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase tracking-[0.12em] text-primary mb-0.5">Resume</p>
              <h2 className="font-heading font-semibold text-dark text-base truncate">{candidateName}</h2>
            </div>
          </div>

          {/* View toggle */}
          <div className="flex items-center gap-3 shrink-0">
            {hasPdf && hasText && (
              <div className="flex rounded-xl border border-mid/15 overflow-hidden text-xs font-semibold bg-white">
                <button
                  onClick={() => setActiveView('pdf')}
                  className={`px-4 py-1.5 transition-all ${activeView === 'pdf' ? 'bg-primary text-white shadow-sm' : 'text-mid hover:text-dark'}`}
                >
                  PDF View
                </button>
                <button
                  onClick={() => setActiveView('text')}
                  className={`px-4 py-1.5 transition-all ${activeView === 'text' ? 'bg-primary text-white shadow-sm' : 'text-mid hover:text-dark'}`}
                >
                  Text View
                </button>
              </div>
            )}

            {/* Actions */}
            {proxyUrl && (
              <div className="flex items-center gap-2">
                <a
                  href={proxyUrl}
                  target="_blank"
                  rel="noreferrer"
                  download={filename}
                  className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-xl bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" /> Download
                </a>
                <a
                  href={proxyUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-xl bg-mid/8 text-mid hover:bg-mid/15 hover:text-dark transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" /> Open PDF
                </a>
              </div>
            )}

            <button
              onClick={onClose}
              className="w-8 h-8 rounded-xl flex items-center justify-center text-mid hover:text-dark hover:bg-mid/10 transition-colors"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ── Body ── */}
        <div className="flex-1 flex flex-col overflow-hidden bg-mid/5">
          {!hasPdf && !hasText && (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-mid py-16">
              <AlertTriangle className="w-10 h-10 text-warning opacity-50" />
              <p className="text-sm font-medium">Resume content unavailable</p>
              <p className="text-xs text-mid/60">This resume may still be processing.</p>
            </div>
          )}

          {activeView === 'pdf' && hasPdf && <PdfViewer url={pdfUrl} filename={filename} />}
          {activeView === 'text' && <RawTextViewer text={rawText} filename={filename} />}
        </div>

        {/* ── Footer ── */}
        <div className="shrink-0 px-6 py-3 border-t border-mid/10 bg-light/30 flex items-center justify-between">
          <span className="text-xs text-mid/60 font-mono">{filename || 'resume.pdf'}</span>
          <button
            onClick={onClose}
            className="text-xs font-semibold text-mid hover:text-dark transition-colors px-3 py-1.5 rounded-lg hover:bg-mid/8"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
