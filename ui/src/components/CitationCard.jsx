import { FileText } from 'lucide-react';

export default function CitationCard({ title, source, url }) {
  return (
    <div
      className="bg-sage-50 border border-sage-200 border-l-[3px] border-l-sage-500 rounded-lg p-2 mt-3 text-sm text-warm-600"
      role="group"
    >
      <div className="flex gap-2">
        <FileText className="w-4 h-4 text-sage-500 shrink-0 mt-0.5" aria-hidden />
        <span>
          Source:{' '}
          {url ? (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sage-600 underline decoration-sage-200 underline-offset-2 hover:text-sage-700"
            >
              {title}
            </a>
          ) : (
            <span>{title}</span>
          )}
          {source && <span> ({source})</span>}
        </span>
      </div>
    </div>
  );
}
