/**
 * TypingIndicator — Animated dots for bot "typing" state
 * @see UI Design & Implementation §5.9
 */
export default function TypingIndicator() {
  return (
    <div className="flex justify-start mb-4 animate-message-in">
      <div
        className="inline-flex items-center gap-1 px-4 py-3 bg-gradient-to-br from-lavender-100 to-sage-100 rounded-[1.25rem] rounded-bl-[0.375rem]"
        role="status"
        aria-live="polite"
        aria-label="Care Connect is typing"
      >
        <span
          className="w-2 h-2 bg-lavender-400 rounded-full animate-typing"
          style={{
            animation: 'typing-bounce 1.4s infinite ease-in-out',
          }}
        />
        <span
          className="w-2 h-2 bg-lavender-400 rounded-full animate-typing"
          style={{
            animation: 'typing-bounce 1.4s infinite ease-in-out',
            animationDelay: '0.2s',
          }}
        />
        <span
          className="w-2 h-2 bg-lavender-400 rounded-full animate-typing"
          style={{
            animation: 'typing-bounce 1.4s infinite ease-in-out',
            animationDelay: '0.4s',
          }}
        />
      </div>
    </div>
  );
}
