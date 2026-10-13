"use client";

import * as React from "react";
import Link from "next/link";
import {
  Activity,
  BrainCircuit,
  Cpu,
  FileWarning,
  Film,
  Gauge,
  Lock,
  ScanFace,
  Users,
} from "lucide-react";

import { api } from "@/lib/api";
import type { HealthStatus, MediaRead, SystemMetrics, VideoJob } from "@/lib/types";
import { PageHeader, SectionCard } from "@/components/jarvas/page-header";
import { PrivacyBanner, StatCard } from "@/components/jarvas/privacy-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/components/providers/auth-provider";

export default function DashboardPage() {
  const { user, hasRole } = useAuth();
  const [health, setHealth] = React.useState<HealthStatus | null>(null);
  const [metrics, setMetrics] = React.useState<SystemMetrics | null>(null);
  const [media, setMedia] = React.useState<MediaRead[]>([]);
  const [jobs, setJobs] = React.useState<VideoJob[]>([]);
  const [identityTotal, setIdentityTotal] = React.useState<number | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    (async () => {
      try {
        const [h, m, v, g] = await Promise.all([
          api.health().catch(() => null),
          hasRole("admin") ? api.metrics().catch(() => null) : Promise.resolve(null),
          api.listMedia().catch(() => []),
          api.listIdentities({ size: 1 }).catch(() => ({ total: 0 })),
        ]);
        setHealth(h);
        setMetrics(m);
        setMedia(v);
        setIdentityTotal((g as { total: number }).total ?? 0);
        if (hasRole("auditor")) {
          api.listVideoJobs().then(setJobs).catch(() => {});
        }
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const detectionModel = health?.models.find((m) => m.task === "detection");

  return (
    <div>
      <PageHeader
        title={`Welcome${user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}`}
        description="Privacy-first face analysis. Detection is the default; recognition is consent-gated and always advisory."
        icon={<Gauge className="h-5 w-5" />}
        actions={
          <>
            <Button asChild>
              <Link href="/detect"><ScanFace className="h-4 w-4" /> Detect a face</Link>
            </Button>
            {hasRole("operator") && (
              <Button variant="secondary" asChild>
                <Link href="/recognize"><BrainCircuit className="h-4 w-4" /> Recognize</Link>
              </Button>
            )}
          </>
        }
      />

      <PrivacyBanner className="mb-6">
        JARVAS does not perform surveillance, live tracking, public-face search, scraping, emotion analysis,
        demographic profiling, or law-enforcement workflows. Every recognition result is a candidate requiring
        human review — never a certain identity.
      </PrivacyBanner>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)
        ) : (
          <>
            <StatCard label="Consented identities" value={metrics?.total_identities ?? identityTotal ?? "—"} hint={`${metrics?.active_consents ?? "—"} active consents`} icon={<Users className="h-5 w-5" />} accent="indigo" index={0} />
            <StatCard label="Media processed" value={metrics?.total_media ?? media.length} hint="Images & videos" icon={<ScanFace className="h-5 w-5" />} accent="cyan" index={1} />
            <StatCard label="Video jobs" value={metrics?.total_video_jobs ?? jobs.length} hint={`${metrics?.pending_video_jobs ?? 0} pending`} icon={<Film className="h-5 w-5" />} accent="teal" index={2} />
            <StatCard label="Expired consents" value={metrics?.expired_consents ?? "—"} hint="Templates purged by retention" icon={<Lock className="h-5 w-5" />} accent="amber" index={3} />
          </>
        )}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <SectionCard title="Model status" description="Inference backend & provider" className="lg:col-span-2">
          {detectionModel ? (
            <div className="space-y-3">
              {health?.models.map((m) => (
                <div key={m.task} className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.03] px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Cpu className="h-4 w-4 text-cyan-300" />
                    <div>
                      <p className="text-sm font-medium">{m.name}</p>
                      <p className="text-xs text-muted-foreground capitalize">{m.task} · {m.provider} · {m.embedding_dim}-d</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {m.is_mock && <Badge variant="warning"><FileWarning className="h-3 w-3" /> mock</Badge>}
                    <Badge variant={m.loaded ? "success" : "secondary"}>{m.loaded ? "loaded" : "idle"}</Badge>
                  </div>
                </div>
              ))}
              <p className="text-xs text-muted-foreground">
                When model weights are absent, a deterministic mock engine is used so the app remains runnable.
                Enable real InsightFace weights in production (see docs/MODEL_LICENSING.md).
              </p>
            </div>
          ) : (
            <Skeleton className="h-24" />
          )}
        </SectionCard>

        <SectionCard title="System health" description="Component readiness">
          {health ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Activity className={health.status === "ok" ? "h-4 w-4 text-teal-300" : "h-4 w-4 text-amber-300"} />
                <span className="text-sm">Overall: <span className="font-medium capitalize">{health.status}</span></span>
              </div>
              {health.components.map((c) => (
                <div key={c.name} className="flex items-center justify-between text-sm">
                  <span className="capitalize text-muted-foreground">{c.name}</span>
                  <Badge variant={c.status === "ok" ? "success" : c.status === "degraded" ? "warning" : "destructive"}>
                    {c.status}
                  </Badge>
                </div>
              ))}
              <p className="pt-1 text-xs text-muted-foreground">Version {health.version} · {health.env}</p>
            </div>
          ) : (
            <Skeleton className="h-24" />
          )}
        </SectionCard>
      </div>

      {media.length > 0 && (
        <SectionCard title="Recent uploads" description="Latest analyzed media" className="mt-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {media.slice(0, 4).map((m) => (
              <div key={m.id} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                <div className="flex items-center justify-between">
                  <Badge variant={m.kind === "video" ? "cyan" : "default"}>{m.kind}</Badge>
                  <span className="text-xs text-muted-foreground">{m.face_count} faces</span>
                </div>
                <p className="mt-2 truncate text-sm">{m.original_filename}</p>
                <p className="text-xs text-muted-foreground">{m.processing_ms.toFixed(0)} ms · {m.width}×{m.height}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}
