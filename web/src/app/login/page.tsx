"use client";

import React, { useState } from "react";
import Navbar from "@/components/Navbar";
import { LogIn, Loader2, AlertCircle } from "lucide-react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const formData = new FormData(e.currentTarget);
    const email = formData.get("email");
    const password = formData.get("password");

    try {
      const response = await fetch("http://localhost:8000/internal/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Giriş bilgileri hatalı.");
      }

      // Token'ı sakla ve yönlendir
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("user", JSON.stringify(data));
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background pt-32 px-6">
      <Navbar />
      <div className="max-w-md mx-auto glass p-8 rounded-3xl text-center">
        <div className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
          <LogIn className="text-primary w-8 h-8" />
        </div>
        <h1 className="text-3xl font-bold mb-4">Giriş Yap</h1>
        <p className="text-muted-foreground mb-8">Seyahat planlarını yönetmek için hesabına giriş yap.</p>
        
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-500 p-4 rounded-xl mb-6 text-sm flex items-center gap-2 outline-none">
            <AlertCircle className="w-4 h-4" /> {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <input name="email" type="email" placeholder="E-posta" className="w-full bg-white/5 border border-white/10 rounded-xl p-4 focus:outline-none focus:border-primary/50" required disabled={loading} />
          <input name="password" type="password" placeholder="Şifre" className="w-full bg-white/5 border border-white/10 rounded-xl p-4 focus:outline-none focus:border-primary/50" required disabled={loading} />
          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-primary text-white py-4 rounded-xl font-bold hover:opacity-90 transition-opacity uppercase tracking-wider text-sm flex items-center justify-center gap-2"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Giriş Yap"}
          </button>
        </form>

        <p className="mt-8 text-sm text-muted-foreground">
          Henüz hesabın yok mu? <a href="/signup" className="text-primary hover:underline">Kaydol</a>
        </p>
      </div>
    </div>
  );
}
