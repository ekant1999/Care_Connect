/**
 * WelcomeMessage — Initial greeting with topic pills
 * @see UI Design & Implementation §6.1
 */
import TopicPill from './TopicPill';

const DEFAULT_TOPICS = [
  'Depression',
  'Anxiety',
  'Sleep',
  'Eating Disorders',
  'Substance Use',
];

export default function WelcomeMessage({ topics = DEFAULT_TOPICS, onTopicClick }) {
  return (
    <div className="text-center py-12 px-4 max-w-2xl mx-auto">
      <h2 className="text-3xl font-semibold text-warm-900 mb-4">
        Welcome to Care Connect{' '}
        <span aria-hidden="true">🌿</span>
      </h2>
      <p className="text-base text-warm-700 leading-[1.75] mb-6">
        I'm here to help you explore mental health topics with information from
        trusted sources like the CDC, NIH, and MedlinePlus.
      </p>
      <p className="text-sm text-warm-600 mb-4">You can ask me about:</p>
      <div className="flex flex-wrap justify-center gap-2">
        {topics.map((topic) => (
          <TopicPill
            key={topic}
            label={topic}
            onClick={() => onTopicClick?.(topic)}
          />
        ))}
      </div>
    </div>
  );
}
