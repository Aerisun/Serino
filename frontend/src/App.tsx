import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@/contexts/ThemeContext";
import Index from "./pages/Index.tsx";
import Posts from "./pages/Posts.tsx";
import Friends from "./pages/Friends.tsx";
import Thoughts from "./pages/Thoughts.tsx";
import Diary from "./pages/Diary.tsx";
import Excerpts from "./pages/Excerpts.tsx";
import Resume from "./pages/Resume.tsx";
import Guestbook from "./pages/Guestbook.tsx";
import CalendarPage from "./pages/CalendarPage.tsx";
import PostDetail from "./pages/PostDetail.tsx";
import DiaryDetail from "./pages/DiaryDetail.tsx";
import NotFound from "./pages/NotFound.tsx";

const App = () => (
  <ThemeProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Index />} />
        <Route path="/posts" element={<Posts />} />
        <Route path="/posts/:id" element={<PostDetail />} />
        <Route path="/friends" element={<Friends />} />
        <Route path="/thoughts" element={<Thoughts />} />
        <Route path="/diary" element={<Diary />} />
        <Route path="/diary/:id" element={<DiaryDetail />} />
        <Route path="/excerpts" element={<Excerpts />} />
        <Route path="/resume" element={<Resume />} />
        <Route path="/guestbook" element={<Guestbook />} />
        <Route path="/calendar" element={<CalendarPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  </ThemeProvider>
);

export default App;
