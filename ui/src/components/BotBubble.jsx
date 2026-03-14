/**
 * BotBubble — Bot/assistant message with citations and feedback
 * Renders markdown (lists, bold, headings) in a readable format.
 * @see UI Design & Implementation §5.1
 */
import ReactMarkdown from 'react-markdown';
import CitationCard from './CitationCard';
import FeedbackButtons from './FeedbackButtons';

const markdownComponents = {
  p: ({ children }) => <p className="mb-3 last:mb-0 text-warm-800">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-warm-800">{children}</strong>,
  ul: ({ children }) => <ul className="my-3 ml-4 list-disc space-y-1.5 text-warm-800">{children}</ul>,
  ol: ({ children }) => <ol className="my-3 ml-4 list-decimal space-y-1.5 text-warm-800">{children}</ol>,
  li: ({ children }) => <li className="pl-1 leading-[1.75]">{children}</li>,
  h1: ({ children }) => <h1 className="text-lg font-semibold text-warm-800 mt-4 mb-2 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="text-base font-semibold text-warm-800 mt-4 mb-2 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-semibold text-warm-800 mt-3 mb-1.5 first:mt-0">{children}</h3>,
};

export default function BotBubble({
  message,
  citations = [],
  timestamp,
  onFeedback,
  feedback,
  onCopy,
}) {
  return (
    <div className="flex justify-start mb-4 animate-message-in" role="article" aria-label="Care Connect response">
      <div className="max-w-[85%]">
        <div
          className="bg-gradient-to-br from-lavender-100 to-sage-100 text-warm-800 rounded-[1.25rem] rounded-bl-[0.375rem] px-5 py-4 shadow-soft"
          style={{ boxShadow: '0 1px 2px rgba(45, 43, 40, 0.05)' }}
        >
          <p className="text-sm font-semibold text-sage-700 mb-2 flex items-center gap-1.5">
            <span aria-hidden="true">🌿</span>
            Care Connect
          </p>
          <div className="leading-[1.75] text-warm-800">
            <ReactMarkdown components={markdownComponents}>
              {message || ''}
            </ReactMarkdown>
          </div>

          {citations?.length > 0 && (
            <div className="mt-3 space-y-2" role="list" aria-label="Source citations">
              {citations.map((cite, i) => (
                <CitationCard key={i} {...cite} />
              ))}
            </div>
          )}

          {(onFeedback || onCopy) && (
            <FeedbackButtons
              onPositive={onFeedback ? () => onFeedback('positive') : undefined}
              onNegative={onFeedback ? () => onFeedback('negative') : undefined}
              onCopy={onCopy}
              positiveSelected={feedback === 'positive'}
              negativeSelected={feedback === 'negative'}
            />
          )}
        </div>
        {timestamp && (
          <p className="text-xs text-warm-400 mt-1">{timestamp}</p>
        )}
      </div>
    </div>
  );
}
