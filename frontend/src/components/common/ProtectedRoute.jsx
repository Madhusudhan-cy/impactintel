import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Loader2 } from 'lucide-react';

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#F5FAFA] flex flex-col items-center justify-center text-[#172B35]">
        <Loader2 className="w-7 h-7 text-[#16B89A] animate-spin mb-3" />
        <div className="text-xs font-semibold text-[#172B35]">Verifying GitHub session...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    // Redirect unauthenticated visitors to login
    return <Navigate to="/" state={{ from: location, message: 'Please sign in with GitHub to access repository intelligence.' }} replace />;
  }

  return children;
}
