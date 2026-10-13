"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  BrainCircuit,
  Film,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  ScanFace,
  ShieldCheck,
  UserPlus,
  Users,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Role } from "@/lib/types";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  minRole?: Role;
  description: string;
}

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" />, description: "Overview & privacy posture" },
  { href: "/detect", label: "Detect", icon: <ScanFace className="h-4 w-4" />, description: "Image face detection" },
  { href: "/video", label: "Video", icon: <Film className="h-4 w-4" />, description: "Video face-count timeline" },
  { href: "/recognize", label: "Recognize", icon: <BrainCircuit className="h-4 w-4" />, minRole: "operator", description: "Consent-gated candidates" },
  { href: "/enroll", label: "Enroll", icon: <UserPlus className="h-4 w-4" />, minRole: "operator", description: "Consented enrollment" },
  { href: "/gallery", label: "Gallery", icon: <Users className="h-4 w-4" />, description: "Consented identities" },
  { href: "/admin", label: "Admin", icon: <Gauge className="h-4 w-4" />, minRole: "auditor", description: "Users, audit, health" },
];

const RANK: Record<Role, number> = { viewer: 0, auditor: 1, operator: 2, admin: 3 };

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const visible = NAV.filter((item) => !item.minRole || (user && RANK[user.role] >= RANK[item.minRole]));

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-white/10 bg-white/[0.02] backdrop-blur-xl lg:flex">
        <SidebarContent visible={visible} pathname={pathname} user={user} onNavigate={() => {}} />
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
              className="fixed inset-0 z-40 bg-navy-900/70 backdrop-blur-sm lg:hidden"
            />
            <motion.aside
              initial={{ x: -300 }}
              animate={{ x: 0 }}
              exit={{ x: -300 }}
              transition={{ type: "spring", stiffness: 320, damping: 32 }}
              className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-white/10 bg-navy-800/95 backdrop-blur-xl lg:hidden"
            >
              <SidebarContent visible={visible} pathname={pathname} user={user} onNavigate={() => setMobileOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-white/10 bg-background/60 px-4 backdrop-blur-xl sm:px-6">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </Button>
          <div className="flex items-center gap-2 lg:hidden">
            <ShieldCheck className="h-5 w-5 text-cyan-300" />
            <span className="font-semibold">JARVAS</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <Badge variant="cyan" className="hidden sm:inline-flex">
              <Activity className="h-3 w-3" /> Privacy-first
            </Badge>
            {user && (
              <div className="hidden text-right sm:block">
                <p className="text-sm font-medium leading-tight">{user.full_name || user.email}</p>
                <p className="text-xs capitalize text-muted-foreground">{user.role}</p>
              </div>
            )}
            <Button variant="ghost" size="icon" onClick={logout} aria-label="Sign out">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </header>
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}

function SidebarContent({
  visible,
  pathname,
  user,
  onNavigate,
}: {
  visible: NavItem[];
  pathname: string;
  user: ReturnType<typeof useAuth>["user"];
  onNavigate: () => void;
}) {
  const router = useRouter();
  const { logout } = useAuth();
  return (
    <>
      <div className="flex h-16 items-center gap-2 border-b border-white/10 px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-cyan-500 shadow-lg shadow-indigo-500/30">
          <ShieldCheck className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold tracking-wide">JARVAS</p>
          <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Face Suite</p>
        </div>
        <button className="ml-auto lg:hidden" onClick={onNavigate} aria-label="Close menu">
          <X className="h-4 w-4" />
        </button>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {visible.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                active ? "text-foreground" : "text-muted-foreground hover:bg-white/[0.05] hover:text-foreground",
              )}
            >
              {active && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-lg border border-white/10 bg-gradient-to-r from-indigo-500/20 to-cyan-500/10"
                  transition={{ type: "spring", stiffness: 380, damping: 32 }}
                />
              )}
              <span className="relative">{item.icon}</span>
              <span className="relative flex-1">{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-white/10 p-3">
        {user && (
          <div className="mb-2 rounded-lg bg-white/[0.03] px-3 py-2">
            <p className="truncate text-xs font-medium">{user.email}</p>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{user.role}</p>
          </div>
        )}
        <Button variant="secondary" className="w-full justify-start" size="sm" onClick={() => { logout(); router.push("/login"); }}>
          <LogOut className="h-4 w-4" /> Sign out
        </Button>
      </div>
    </>
  );
}
