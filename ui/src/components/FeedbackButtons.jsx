import { ThumbsUp, ThumbsDown, ClipboardCopy } from 'lucide-react';

export default function FeedbackButtons({ onPositive, onNegative, onCopy, positiveSelected, negativeSelected }) {
  return (
    <div
      className="flex gap-2 mt-2 pt-2 border-t border-black/5"
      role="group"
      aria-label="Feedback options"
    >
      <button
        type="button"
        onClick={onPositive ?? (() => {})}
        className={`
          p-1.5 rounded-md text-sm transition-all
          ${positiveSelected
            ? 'text-sage-600 border border-sage-500 bg-sage-50'
            : 'text-warm-400 border border-warm-200 hover:text-sage-500 hover:border-sage-300 hover:bg-sage-50'
          }
        `}
        aria-pressed={positiveSelected}
        aria-label="Helpful"
      >
        <ThumbsUp className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={onNegative ?? (() => {})}
        className={`
          p-1.5 rounded-md text-sm transition-all
          ${negativeSelected
            ? 'text-error border border-error bg-[#FDF2F2]'
            : 'text-warm-400 border border-warm-200 hover:text-crisis hover:border-crisis/30 hover:bg-red-50'
          }
        `}
        aria-pressed={negativeSelected}
        aria-label="Not helpful"
      >
        <ThumbsDown className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={onCopy}
        className="p-1.5 rounded-md text-sm text-warm-400 border border-warm-200 hover:text-sage-500 hover:border-sage-300 hover:bg-sage-50 transition-all"
        aria-label="Copy response"
      >
        <ClipboardCopy className="w-4 h-4" />
      </button>
    </div>
  );
}
