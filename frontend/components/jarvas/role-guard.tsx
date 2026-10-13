"use client";

import { ShieldAlert } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import { Card, CardContent } from "@/components/ui/card";
import type { Role } from "@/lib/types";

export function RoleGuard({
  roles,
  children,
}: {
  roles: Role[];
  children: React.ReactNode;
}) {
  const { hasRole, user } = useAuth();
  if (hasRole(...roles)) return <>{children}</>;

  return (
    <Card className="mx-auto max-w-lg">
      <CardContent className="flex flex-col items-center gap-3 p-8 text-center">
        <div className="rounded-2xl bg-amber-500/15 p-4">
          <ShieldAlert className="h-7 w-7 text-amber-300" />
        </div>
        <h2 className="text-lg font-semibold">Insufficient permissions</h2>
        <p className="text-sm text-muted-foreground">
          This area requires one of the following roles:{" "}
          <span className="font-medium text-foreground">{roles.join(", ")}</span>. Your role is{" "}
          <span className="font-medium text-foreground">{user?.role ?? "unknown"}</span>.
        </p>
        <p className="text-xs text-muted-foreground">
          Contact an administrator if you believe you should have access. Role changes are audited.
        </p>
      </CardContent>
    </Card>
  );
}
