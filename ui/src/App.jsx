import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import ChatPage from './pages/ChatPage';
import ComparisonPage from './pages/ComparisonPage';

function AppContent() {
  const navigate = useNavigate();

  return (
    <Routes>
      <Route
        path="/"
        element={
          <ChatPage />
        }
      />
      <Route
        path="/evaluation"
        element={
          <ComparisonPage
            onExit={() => navigate('/')}
          />
        }
      />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}
