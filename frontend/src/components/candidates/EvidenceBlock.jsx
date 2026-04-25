import React from 'react';
import { Card } from '../ui/Card';
import { FileText } from 'lucide-react';

export function EvidenceBlock({ text, source: defaultSource, title }) {
  if (!text) return null;

  let chunks = [];
  try {
    const parsed = typeof text === 'string' ? JSON.parse(text) : text;
    if (Array.isArray(parsed)) {
      chunks = parsed;
    } else {
      chunks = [{ text: parsed }];
    }
  } catch (e) {
    chunks = [{ text }];
  }
  
  return (
    <Card className="!p-0 mb-4 bg-white border border-mid/10 overflow-hidden flex flex-col">
      {title && (
        <div className="bg-mid/5 px-6 py-3 border-b border-mid/10">
          <h4 className="font-heading font-semibold text-dark text-sm tracking-widest uppercase">{title}</h4>
        </div>
      )}
      <div className="divide-y divide-mid/5">
        {chunks.map((chunk, idx) => (
          <div key={idx} className="p-6 flex items-start gap-4 hover:bg-light/30 transition-colors">
            <FileText className="w-5 h-5 text-primary/60 mt-1 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-[15px] text-dark leading-relaxed whitespace-pre-wrap break-words">
                {chunk.text || JSON.stringify(chunk)}
              </p>
              
              <div className="mt-3 flex flex-wrap gap-2">
                {(chunk.source || defaultSource) && (
                  <span className="text-[11px] font-mono text-mid/80 bg-light px-2.5 py-1 rounded-md border border-mid/10 uppercase tracking-wider">
                    Source: {chunk.source || defaultSource}
                  </span>
                )}
                {chunk.confidence && (
                  <span className="text-[11px] font-mono text-primary/80 bg-primary/10 px-2.5 py-1 rounded-md border border-primary/20 uppercase tracking-wider">
                    Confidence: {Math.round(chunk.confidence * 100)}%
                  </span>
                )}
                {chunk.similarity && (
                  <span className="text-[11px] font-mono text-secondary/80 bg-secondary/10 px-2.5 py-1 rounded-md border border-secondary/20 uppercase tracking-wider">
                    Match: {Math.round(chunk.similarity * 100)}%
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
