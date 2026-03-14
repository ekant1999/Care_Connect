import { useState, useRef, useEffect } from "react";
import Header from "../components/Header";
import DisclaimerBanner from "../components/DisclaimerBanner";
import CrisisBanner from "../components/CrisisBanner";
import WelcomeMessage from "../components/WelcomeMessage";
import UserBubble from "../components/UserBubble";
import BotBubble from "../components/BotBubble";
import TypingIndicator from "../components/TypingIndicator";
import ChatInputBar from "../components/ChatInputBar";

// Mock topics from design doc
const TOPICS = [
  "Depression",
  "Anxiety",
  "Sleep",
  "Eating Disorders",
  "Substance Use",
];

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";

  const handleSendMessage = async (text) => {
    if (!text.trim()) return;

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: formatTime(new Date()),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);

    try {
      const res = await fetch(`${apiBase}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Request failed (${res.status})`);
      }
      const botMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.answer || "No response.",
        citations: data.citations || [],
        timestamp: formatTime(new Date()),
        feedback: null,
      };
      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      const botMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Sorry, something went wrong: ${err.message}. Make sure the backend is running (uvicorn api.main:app --port 8000) and Ollama is available.`,
        citations: [],
        timestamp: formatTime(new Date()),
        feedback: null,
      };
      setMessages((prev) => [...prev, botMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleTopicClick = (topic) => {
    handleSendMessage(`I'd like to learn more about ${topic}.`);
  };

  const handleFeedback = (messageId, type) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId ? { ...m, feedback: type } : m
      )
    );
  };

  const handleCopy = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      console.error("Copy failed:", err);
    }
  };

  const showWelcome = messages.length === 0;

  return (
    <div className="flex flex-col min-h-screen">
      <Header
        onMenuClick={() => {}}
        onTopicsClick={() => {}}
      />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[800px] mx-auto px-4 py-6">
          <DisclaimerBanner />

          {showWelcome && (
            <WelcomeMessage
              topics={TOPICS}
              onTopicClick={handleTopicClick}
            />
          )}

          <div
            className="space-y-4"
            role="log"
            aria-live="polite"
            aria-label="Chat messages"
          >
            {messages.map((msg) =>
              msg.role === "user" ? (
                <UserBubble
                  key={msg.id}
                  message={msg.content}
                  timestamp={msg.timestamp}
                />
              ) : (
                <BotBubble
                  key={msg.id}
                  message={msg.content}
                  citations={msg.citations}
                  timestamp={msg.timestamp}
                  feedback={msg.feedback}
                  onFeedback={(type) => handleFeedback(msg.id, type)}
                  onCopy={() => handleCopy(msg.content)}
                />
              )
            )}
            {isTyping && <TypingIndicator />}
          </div>

          <CrisisBanner />
          <div ref={messagesEndRef} />
        </div>
      </main>

      <div className="sticky bottom-0 bg-white border-t border-warm-200">
        <div className="max-w-[800px] mx-auto px-4 py-4">
          <ChatInputBar
            onSend={handleSendMessage}
            placeholder="Ask me anything about mental health..."
            disabled={isTyping}
          />
        </div>
      </div>
    </div>
  );
}

function formatTime(date) {
  return date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
}
