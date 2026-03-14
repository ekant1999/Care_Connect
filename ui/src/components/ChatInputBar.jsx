/**
 * ChatInputBar — Input field with send button
 * @see UI Design & Implementation §5.5
 */
import { useState } from 'react';
import { SendHorizontal } from 'lucide-react';

export default function ChatInputBar({
  onSend,
  placeholder = 'Ask me anything about mental health...',
  disabled = false,
}) {
  const [value, setValue] = useState('');

  const handleSubmit = () => {
    const text = value?.trim();
    if (!text || disabled) return;
    onSend?.(text);
    setValue('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div
      className="bg-white p-4 flex items-center gap-3"
      role="form"
      aria-label="Chat input"
    >
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className="flex-1 bg-warm-100 border-[1.5px] border-warm-200 rounded-full px-5 py-3 text-base font-[inherit] text-warm-800 placeholder-warm-400 transition-all outline-none focus:border-sage-500 focus:shadow-[0_0_0_3px_rgba(91,158,122,0.15)] focus:bg-white"
        aria-label="Type your message"
      />
      <button
        type="button"
        onClick={handleSubmit}
        disabled={disabled || !value?.trim()}
        className="bg-sage-500 text-white rounded-full w-11 h-11 flex items-center justify-center cursor-pointer transition-all hover:bg-sage-600 active:bg-sage-700 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100"
        aria-label="Send message"
      >
        <SendHorizontal size={20} aria-hidden="true" />
      </button>
    </div>
  );
}
