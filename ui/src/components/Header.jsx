import { Link } from 'react-router-dom';
import { Leaf, Menu, LayoutGrid } from 'lucide-react';

export default function Header({
  onMenuClick,
  onTopicsClick,
  showEvaluation = false,
  onExitEvaluation,
}) {
  return (
    <header
      className="h-16 flex items-center justify-between px-4 md:px-6 bg-gradient-to-br from-sage-500 to-lavender-500 text-white shadow-card"
      role="banner"
    >
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          className="p-2 rounded-lg hover:bg-white/10 focus:bg-white/10 transition-colors md:hidden"
          aria-label="Open menu"
        >
          <Menu className="w-6 h-6" />
        </button>
        <div className="flex items-center gap-2">
          <Leaf className="w-8 h-8 text-white/90" aria-hidden />
          <h1 className="text-xl font-semibold tracking-tight">
            {showEvaluation ? 'Care Connect — Evaluation Mode' : 'Care Connect'}
          </h1>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {showEvaluation ? (
          <button
            type="button"
            onClick={onExitEvaluation}
            className="px-4 py-2 text-sm font-medium bg-white/20 hover:bg-white/30 rounded-xl transition-colors"
          >
            Exit Evaluation
          </button>
        ) : (
          <>
            <Link
              to="/evaluation"
              className="px-3 py-2 text-sm font-medium rounded-xl hover:bg-white/20 transition-colors"
            >
              Evaluation
            </Link>
            <button
              type="button"
              onClick={onTopicsClick}
              className="p-2 rounded-lg hover:bg-white/10 focus:bg-white/10 transition-colors"
              aria-label="Topic selector"
            >
              <LayoutGrid className="w-6 h-6" />
            </button>
          </>
        )}
      </div>
    </header>
  );
}
