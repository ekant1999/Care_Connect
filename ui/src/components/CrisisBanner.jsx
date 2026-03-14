import { AlertCircle } from 'lucide-react';

export default function CrisisBanner() {
  return (
    <div
      className="bg-[#FDE8E8] border border-crisis rounded-xl p-5 my-4 flex gap-3"
      role="alert"
      aria-label="Crisis resources"
    >
      <AlertCircle className="w-6 h-6 text-crisis shrink-0 mt-0.5" aria-hidden />
      <div>
        <p className="font-semibold text-crisis text-base mb-2">
          If you or someone you know is in crisis:
        </p>
        <ul className="text-sm text-warm-700 space-y-1 list-disc list-inside">
          <li>
            <strong>988 Suicide & Crisis Lifeline</strong> — Call or text{' '}
            <a href="tel:988" className="text-crisis font-semibold underline underline-offset-2">
              988
            </a>
          </li>
          <li>
            <strong>Crisis Text Line</strong> — Text HOME to <span className="font-semibold">741741</span>
          </li>
          <li>
            <strong>Emergency</strong> — Call{' '}
            <a href="tel:911" className="text-crisis font-semibold underline underline-offset-2">
              911
            </a>
          </li>
        </ul>
        <p className="text-sm text-warm-600 mt-3 italic">
          You are not alone. Help is available 24/7.
        </p>
      </div>
    </div>
  );
}
