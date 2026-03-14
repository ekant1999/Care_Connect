import { Info } from 'lucide-react';

export default function DisclaimerBanner() {
  return (
    <div
      className="bg-peach-50 border border-peach-200 rounded-xl p-4 mb-6 text-sm text-warm-600 leading-normal"
      role="region"
      aria-label="Medical disclaimer"
    >
      <div className="flex gap-3">
        <Info className="w-5 h-5 text-sage-500 shrink-0 mt-0.5" aria-hidden />
        <p>
          <strong className="text-warm-800">Care Connect</strong> provides general health information from
          trusted sources like the CDC, NIH, and MedlinePlus. It is not a substitute for professional medical
          advice, diagnosis, or treatment. Always consult a qualified healthcare provider with questions
          about your health.
        </p>
      </div>
    </div>
  );
}
