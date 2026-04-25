import React, { useState, useRef } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { UploadCloud, FileText, Link as LinkIcon, X } from 'lucide-react';
import { useToast } from '../../hooks/useToast';

export function ResumeUploadForm({ onSubmit, isUploading }) {
  const [file, setFile] = useState(null);
  const [links, setLinks] = useState({ github: '', leetcode: '', codeforces: '', codechef: '' });
  const fileInputRef = useRef(null);
  const toast = useToast();

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0];
    if (selected) {
      if (selected.size > 10 * 1024 * 1024) {
        toast('File exceeds 10MB limit', 'error');
        return;
      }
      setFile(selected);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) {
      if (dropped.type === 'application/pdf' || dropped.name.endsWith('.docx')) {
        setFile(dropped);
      } else {
        toast('Only PDF or DOCX allowed', 'error');
      }
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!file) {
      toast('Please select a resume file', 'error');
      return;
    }
    onSubmit(file, links);
  };

  return (
    <Card className="max-w-4xl mx-auto">
      <form onSubmit={handleSubmit} className="grid md:grid-cols-2 gap-8">
        {/* Left: File Drop */}
        <div>
          <h3 className="font-heading font-semibold text-lg mb-4">Upload Resume</h3>
          <div 
            className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${file ? 'border-primary bg-primary/5' : 'border-mid/30 hover:bg-light'}`}
            onDragOver={e => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => !file && fileInputRef.current?.click()}
          >
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              accept=".pdf,.docx" 
              onChange={handleFileChange}
            />
            {file ? (
              <div className="flex flex-col items-center">
                <FileText className="w-12 h-12 text-primary mb-3" />
                <p className="font-medium text-dark truncate w-full">{file.name}</p>
                <p className="text-sm text-mid mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                <Button type="button" variant="outline" className="mt-4" onClick={(e) => { e.stopPropagation(); setFile(null); }}>
                  <X className="w-4 h-4 mr-1" /> Remove
                </Button>
              </div>
            ) : (
              <div className="flex flex-col items-center py-6">
                <UploadCloud className="w-12 h-12 text-mid/50 mb-3" />
                <p className="font-medium text-dark">Click or drag file to upload</p>
                <p className="text-sm text-mid mt-1">PDF or DOCX up to 10MB</p>
              </div>
            )}
          </div>
        </div>

        {/* Right: Links */}
        <div>
          <h3 className="font-heading font-semibold text-lg mb-4">External Profiles (Optional)</h3>
          <div className="space-y-4">
            {Object.keys(links).map(platform => (
              <div key={platform}>
                <label className="block text-sm font-medium text-dark capitalize mb-1">
                  {platform} URL
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <LinkIcon className="h-4 w-4 text-mid/50" />
                  </div>
                  <input
                    type="url"
                    className="block w-full pl-10 pr-3 py-2 border border-mid/20 rounded-lg focus:ring-primary focus:border-primary bg-white/50 text-sm"
                    placeholder={`https://${platform === 'github' ? 'github.com' : platform === 'leetcode' ? 'leetcode.com/u' : platform + '.com'}/username`}
                    value={links[platform]}
                    onChange={e => setLinks({...links, [platform]: e.target.value})}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 pt-6 border-t border-mid/10">
            <Button type="submit" className="w-full py-3" isLoading={isUploading} disabled={!file}>
              Upload & Process Resume
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
}
