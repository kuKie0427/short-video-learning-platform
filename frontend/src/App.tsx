import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from './layouts/MainLayout';
import { Home } from './pages/Home';
import { Courses } from './pages/Courses';
import { Upload } from './pages/Upload';
import { Inbox } from './pages/Inbox';
import { Profile } from './pages/Profile';
import { Login } from './pages/Login';
import { VideoDetail } from './pages/VideoDetail';
import { Search } from './pages/Search';
import { VideoSplit } from './pages/VideoSplit';
import VideoSplitResult from './pages/VideoSplitResult';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/video/:id" element={<VideoDetail />} />
          <Route path="/search" element={<Search />} />
          <Route path="/split" element={
            <ProtectedRoute>
              <VideoSplit />
            </ProtectedRoute>
          } />
          <Route path="/video-split-result/:taskId" element={
            <ProtectedRoute>
              <VideoSplitResult />
            </ProtectedRoute>
          } />
          
          <Route element={<MainLayout />}>
            <Route path="/" element={<Home />} />
            <Route path="/courses" element={<Courses />} />
            
            {/* Protected Routes */}
            <Route path="/upload" element={
              <ProtectedRoute>
                <Upload />
              </ProtectedRoute>
            } />
            <Route path="/inbox" element={
              <ProtectedRoute>
                <Inbox />
              </ProtectedRoute>
            } />
            <Route path="/profile" element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            } />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
