export default function TopicPill({ label, active, onClick }) {
  return (
    <button
      type="button"
      onClick={() => onClick?.(label)}
      className={`
        inline-flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-full cursor-pointer
        transition-all duration-150
        ${active
          ? 'bg-lavender-500 text-white border border-lavender-500'
          : 'bg-lavender-50 text-lavender-700 border border-lavender-200 hover:bg-lavender-100 hover:border-lavender-300'
        }
      `}
    >
      {label}
    </button>
  );
}
