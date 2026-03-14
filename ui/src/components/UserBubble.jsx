/**
 * UserBubble — User message bubble (right-aligned, peach)
 * @see UI Design & Implementation §5.1
 */
export default function UserBubble({ message, timestamp }) {
  return (
    <div className="flex justify-end mb-4 animate-message-in" role="article" aria-label="Your message">
      <div className="max-w-[85%]">
        <div
          className="bg-peach-200 text-warm-800 rounded-[1.25rem] rounded-br-[0.375rem] px-4 py-3 shadow-soft leading-[1.75]"
          style={{ boxShadow: '0 1px 2px rgba(45, 43, 40, 0.05)' }}
        >
          {message}
        </div>
        {timestamp && (
          <p className="text-xs text-warm-400 text-right mt-1">{timestamp}</p>
        )}
      </div>
    </div>
  );
}
