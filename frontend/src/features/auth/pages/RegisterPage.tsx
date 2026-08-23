import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { authApi } from "@/lib/api/auth";
import { useMutation } from "@tanstack/react-query";
import { APIError } from "@/lib/api/client";
import type { RegisterRequest } from "@/types/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Loader2 } from "lucide-react";

export function RegisterPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const signupMutation = useMutation({
    // /auth/register returns the created user, not a token. Chain an immediate
    // login so a successful sign-up drops the user straight into the workspace
    // (PublicRoute redirects to "/" once AuthContext sees the token).
    mutationFn: async (data: RegisterRequest) => {
      await authApi.register(data);
      return authApi.login(data);
    },
    onSuccess: (data) => {
      login(data.access_token);
    },
    onError: (err: Error) => {
      if (err instanceof APIError) {
        if (err.status === 409) {
          setErrorMsg("An account with this email already exists.");
        } else {
          setErrorMsg(err.message || "Could not create your account. Please try again.");
        }
      } else {
        setErrorMsg("Network error. Please ensure the API is reachable.");
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!email || !password) {
      setErrorMsg("Please enter both email and password.");
      return;
    }
    if (password.length < 8) {
      setErrorMsg("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMsg("Passwords do not match.");
      return;
    }

    signupMutation.mutate({ email, password });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4 sm:p-8">
      <div className="w-full max-w-[400px]">
        {/* Brand Header */}
        <div className="mb-8 flex flex-col items-center justify-center text-center">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded bg-ai flex items-center justify-center">
              <div className="w-2 h-2 rounded-full bg-background" />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              QuantPilot AI
            </h1>
          </div>
          <p className="text-sm text-muted-foreground font-medium">
            Agentic Financial Research Assistant
          </p>
        </div>

        <Card className="border-border/50 shadow-none bg-card/50">
          <CardHeader className="space-y-1 pb-6">
            <CardTitle className="text-xl">Create Account</CardTitle>
            <CardDescription className="text-sm">
              Set up your workspace to start researching.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider" htmlFor="email">
                  Email
                </label>
                <Input
                  id="email"
                  type="email"
                  placeholder="name@example.com"
                  className="bg-background/50 focus-visible:ring-ai/50"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={signupMutation.isPending}
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider" htmlFor="password">
                  Password
                </label>
                <Input
                  id="password"
                  type="password"
                  className="bg-background/50 focus-visible:ring-ai/50"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={signupMutation.isPending}
                  minLength={8}
                  required
                />
                <p className="text-xs text-muted-foreground">Minimum 8 characters.</p>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider" htmlFor="confirmPassword">
                  Confirm Password
                </label>
                <Input
                  id="confirmPassword"
                  type="password"
                  className="bg-background/50 focus-visible:ring-ai/50"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={signupMutation.isPending}
                  minLength={8}
                  required
                />
              </div>

              {errorMsg && (
                <div className="rounded-md border border-destructive/20 bg-destructive/10 p-3">
                  <p className="text-xs font-medium text-destructive">{errorMsg}</p>
                </div>
              )}

              <Button
                type="submit"
                className="w-full bg-foreground text-background hover:bg-foreground/90 font-medium h-10"
                disabled={signupMutation.isPending}
              >
                {signupMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating account...
                  </>
                ) : (
                  "Create Account"
                )}
              </Button>
            </form>
          </CardContent>
          <CardFooter className="flex flex-col border-t border-border/50 pt-6">
            <p className="text-center text-xs text-muted-foreground">
              Already have an account?{" "}
              <Link to="/login" className="font-medium text-ai hover:underline">
                Sign in
              </Link>
            </p>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
