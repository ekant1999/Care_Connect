import { useState } from "react";
import Header from "../components/Header";
import DisclaimerBanner from "../components/DisclaimerBanner";

const RATING_LABELS = ["Trust", "Empathy", "Clarity"];
const RESPONSES = ["A (Care Connect)", "B (ChatGPT)", "C (Gemini)"];

export default function ComparisonPage({ onExit }) {
  const [question] = useState(
    "What should I do if I'm feeling anxious before an exam?"
  );
  const [ratings, setRatings] = useState({
    A: { trust: 0, empathy: 0, clarity: 0 },
    B: { trust: 0, empathy: 0, clarity: 0 },
    C: { trust: 0, empathy: 0, clarity: 0 },
  });
  const [overallChoice, setOverallChoice] = useState("");
  const [comments, setComments] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleRatingChange = (response, dimension, value) => {
    setRatings((prev) => ({
      ...prev,
      [response]: {
        ...prev[response],
        [dimension]: Number(value),
      },
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setSubmitted(true);
    // In production, send to backend
  };

  const sampleResponses = {
    A: "It's completely understandable to feel anxious about exams. Test anxiety is very common among students — about 35% of college students report it affecting their performance.\n\nHere are some techniques that research shows can help:\n• Deep breathing exercises\n• Progressive muscle relaxation\n• Breaking study sessions into manageable chunks\n\nRemember, if anxiety is significantly impacting your daily life, consider reaching out to campus counseling services.",
    B: "Feeling anxious before exams is normal. Try these strategies: deep breathing, getting enough sleep, and staying organized. If it persists, talk to a professional.",
    C: "Exam anxiety is common. I recommend relaxation techniques, good sleep hygiene, and speaking with a counselor if needed. Here are some resources that might help.",
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Header
        showEvaluation
        onExitEvaluation={onExit}
      />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto px-4 py-6">
          <DisclaimerBanner />

          <h2 className="text-xl font-semibold text-warm-800 mb-2">
            Evaluation Question
          </h2>
          <p className="text-warm-700 mb-6 text-lg">"{question}"</p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            {["A", "B", "C"].map((key) => (
              <div
                key={key}
                className="bg-white rounded-xl border border-warm-200 p-4 shadow-soft"
              >
                <h3 className="text-sm font-semibold text-sage-700 mb-3">
                  Response {key}
                </h3>
                <div className="bg-gradient-to-br from-lavender-100 to-sage-100 rounded-lg p-4 text-sm text-warm-700 leading-relaxed whitespace-pre-wrap mb-4">
                  {sampleResponses[key]}
                </div>

                <div className="space-y-2">
                  {RATING_LABELS.map((label) => (
                    <div key={label} className="flex items-center gap-2">
                      <span className="text-xs text-warm-500 w-16">{label}</span>
                      <div className="flex gap-1">
                        {[1, 2, 3, 4, 5].map((n) => (
                          <button
                            key={n}
                            type="button"
                            onClick={() =>
                              handleRatingChange(
                                key,
                                label.toLowerCase(),
                                n
                              )
                            }
                            className={`w-8 h-8 rounded-md text-xs font-medium transition-colors ${
                              ratings[key]?.[label.toLowerCase()] === n
                                ? "bg-sage-500 text-white"
                                : "bg-warm-100 text-warm-500 hover:bg-warm-200"
                            }`}
                            aria-label={`${label}: ${n} stars`}
                          >
                            {n}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="max-w-2xl">
            <h3 className="text-lg font-semibold text-warm-800 mb-2">
              Overall: Which response would you most rely on?
            </h3>
            <div className="flex gap-3 mb-4">
              {RESPONSES.map((label, i) => {
                const letter = ["A", "B", "C"][i];
                return (
                  <button
                    key={letter}
                    type="button"
                    onClick={() => setOverallChoice(letter)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      overallChoice === letter
                        ? "bg-sage-500 text-white"
                        : "bg-warm-100 text-warm-700 hover:bg-warm-200 border border-warm-200"
                    }`}
                  >
                    {letter}
                  </button>
                );
              })}
            </div>

            <label htmlFor="comments" className="block text-sm font-medium text-warm-800 mb-1">
              Comments (optional)
            </label>
            <textarea
              id="comments"
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              placeholder="What made a response helpful or unhelpful?"
              className="w-full h-24 px-3 py-2 rounded-lg border border-warm-200 bg-warm-50 focus:border-sage-500 focus:ring-2 focus:ring-sage-500/20 outline-none resize-none text-warm-800 placeholder-warm-400"
              rows={4}
            />

            <button
              type="submit"
              disabled={submitted}
              className="mt-4 px-6 py-2 bg-sage-500 text-white rounded-lg text-sm font-medium hover:bg-sage-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {submitted ? "Thank you!" : "Submit Feedback"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
