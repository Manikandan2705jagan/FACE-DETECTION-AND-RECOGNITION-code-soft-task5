"use client";

import * as React from "react";
import { Download, Film, Loader2, RefreshCw } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { VideoJob, VideoReport } from "@/lib/types";
import { PageHeader, SectionCard } from "@/components/jarvas/page-header";
import { Dropzone, FileChip } from "@/components/jarvas/dropzone";
import { PrivacyBanner } from "@/components/jarvas/privacy-banner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";

export default function VideoPage() {
  const { toast } = useToast();
  const [file, setFile] = React.useState<File | null>(null);
  const [sampleFps, setSampleFps] = React.useState(1);
  const [job, setJob] = React.useState<VideoJob | null>(null);
  const [report, setReport] = React.useState<VideoReport | null>(null);
  const [loading, setLoading] = React.useState(false);

  const poll = React.useCallback(async (id: string) => {
    try {
      const j = await api.getVideoJob(id);
      setJob(j);
      if (j.status === "completed") {
        const r = await api.getVideoReport(id).catch(() => null);
        setReport(r);
        toast({ title: "Video analysis complete", description: `${j.faces_detected} faces across ${j.frames_processed} frames`, variant: "success" });
        return true;
      }
      if (j.status === "failed") {
        toast({ title: "Video job failed", description: j.error ?? "Unknown error", variant: "destructive" });
        return true;
      }
      return false;
    } catch {
      return true;
    }
  }, [toast]);

  React.useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const interval = setInterval(async () => {
      const done = await poll(job.id);
      if (done) clearInterval(interval);
    }, 1500);
    return () => clearInterval(interval);
  }, [job, poll]);

  const upload = async () => {
    if (!file) return;
    setLoading(true);
    setReport(null);
    setJob(null);
    try {
      const j = await api.uploadVideo(file, sampleFps);
      setJob(j);
      toast({ title: "Upload received", description: "Background processing started.", variant: "default" });
      await poll(j.id);
    } catch (err) {
      toast({
        title: "Upload failed",
        description: err instanceof ApiError ? err.message : "Unexpected error",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Video Detection"
        description="Upload a video for background face-count analysis with a per-frame timeline. Detection-only — no identities, no tracking."
        icon={<Film className="h-5 w-5" />}
      />

      <PrivacyBanner className="mb-6" tone="info">
        Video processing counts anonymous faces per sampled frame. It performs no identity recognition, no
        tracking across time, and no demographic or emotion analysis.
      </PrivacyBanner>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-2">
          <SectionCard title="Upload video">
            <Dropzone
              accept="video/mp4,video/quicktime,video/webm"
              onFile={(f) => { setFile(f); setJob(null); setReport(null); }}
              disabled={loading}
              hint="MP4 · MOV · WebM — up to 512 MB"
            />
            {file && <div className="mt-3"><FileChip file={file} onClear={() => setFile(null)} /></div>}
            <div className="mt-4 space-y-2">
              <Label htmlFor="fps">Frame sampling (fps)</Label>
              <Input
                id="fps"
                type="number"
                min={0.1}
                max={10}
                step={0.1}
                value={sampleFps}
                onChange={(e) => setSampleFps(Number(e.target.value))}
              />
              <p className="text-xs text-muted-foreground">Lower = faster & lighter. 1 fps samples one frame per second.</p>
            </div>
            <Button className="mt-4 w-full" onClick={upload} disabled={!file || loading || (!!job && job.status !== "completed" && job.status !== "failed")}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Film className="h-4 w-4" />}
              {loading ? "Uploading…" : "Start analysis"}
            </Button>
          </SectionCard>

          {job && (
            <SectionCard title="Job status">
              <div className="mb-3 flex items-center justify-between">
                <Badge variant={job.status === "completed" ? "success" : job.status === "failed" ? "destructive" : "cyan"}>
                  {job.status}
                </Badge>
                <span className="text-xs text-muted-foreground">{job.progress.toFixed(0)}%</span>
              </div>
              <Progress value={job.progress} />
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <Stat label="Frames" value={`${job.frames_processed}/${job.frames_total}`} />
                <Stat label="Faces" value={job.faces_detected} />
                <Stat label="Max/frame" value={job.max_faces_in_frame} />
                <Stat label="Duration" value={`${job.duration_seconds.toFixed(0)}s`} />
              </div>
              {job.error && <p className="mt-3 text-xs text-rose-300">{job.error}</p>}
              {job.status === "completed" && (
                <Button variant="secondary" className="mt-4 w-full" asChild>
                  <a href={api.videoReportUrl(job.id)} target="_blank" rel="noreferrer">
                    <Download className="h-4 w-4" /> Download JSON report
                  </a>
                </Button>
              )}
            </SectionCard>
          )}
        </div>

        <div className="lg:col-span-3">
          <SectionCard
            title="Face-count timeline"
            description={report ? `${report.timeline.length} sampled points` : "Appears when processing completes"}
            actions={job && job.status !== "completed" && (
              <Button size="sm" variant="ghost" onClick={() => poll(job.id)}>
                <RefreshCw className="h-4 w-4" /> Refresh
              </Button>
            )}
          >
            {report && report.timeline.length > 0 ? (
              <TimelineChart data={report.timeline} maxFaces={report.job.max_faces_in_frame} />
            ) : (
              <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-white/10 text-sm text-muted-foreground">
                No timeline yet.
              </div>
            )}
            {report?.notes.map((n, i) => (
              <p key={i} className="mt-3 text-xs text-muted-foreground">{n}</p>
            ))}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}

function TimelineChart({ data, maxFaces }: { data: { timestamp_ms: number; face_count: number }[]; maxFaces: number }) {
  const max = Math.max(1, maxFaces);
  const sampled = data.length > 120 ? data.filter((_, i) => i % Math.ceil(data.length / 120) === 0) : data;
  return (
    <div className="flex h-64 items-end gap-[3px] overflow-hidden rounded-xl border border-white/10 bg-white/[0.02] p-3">
      {sampled.map((p, i) => {
        const h = p.face_count === 0 ? 3 : Math.max(6, (p.face_count / max) * 100);
        return (
          <div
            key={i}
            title={`${(p.timestamp_ms / 1000).toFixed(1)}s · ${p.face_count} faces`}
            className="min-w-[4px] flex-1 rounded-sm bg-gradient-to-t from-indigo-500/70 to-cyan-400/90 transition-all hover:from-teal-400 hover:to-teal-300"
            style={{ height: `${h}%` }}
          />
        );
      })}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-medium">{value}</p>
    </div>
  );
}
