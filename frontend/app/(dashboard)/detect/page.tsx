"use client";

import * as React from "react";
import { Download, Loader2, ScanFace, SlidersHorizontal } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { DetectionResponse } from "@/lib/types";
import { formatMs } from "@/lib/utils";
import { PageHeader, SectionCard } from "@/components/jarvas/page-header";
import { Dropzone, FileChip } from "@/components/jarvas/dropzone";
import { FaceCanvas } from "@/components/jarvas/face-canvas";
import { PrivacyBanner } from "@/components/jarvas/privacy-banner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/components/ui/toast";

export default function DetectPage() {
  const { toast } = useToast();
  const [file, setFile] = React.useState<File | null>(null);
  const [preview, setPreview] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<DetectionResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [progress, setProgress] = React.useState(0);

  React.useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const run = async () => {
    if (!file) return;
    setLoading(true);
    setResult(null);
    setProgress(15);
    const tick = setInterval(() => setProgress((p) => Math.min(90, p + 8)), 180);
    try {
      const res = await api.detect(file);
      setProgress(100);
      setResult(res);
      toast({
        title: res.face_count === 0 ? "No faces detected" : `${res.face_count} face${res.face_count > 1 ? "s" : ""} detected`,
        description: `Processed in ${formatMs(res.processing_ms)} (detection-only)`,
        variant: res.face_count === 0 ? "warning" : "success",
      });
    } catch (err) {
      toast({
        title: "Detection failed",
        description: err instanceof ApiError ? err.message : "Unexpected error",
        variant: "destructive",
      });
    } finally {
      clearInterval(tick);
      setLoading(false);
      setTimeout(() => setProgress(0), 600);
    }
  };

  return (
    <div>
      <PageHeader
        title="Face Detection"
        description="Upload an image to detect faces. Detection-only mode returns boxes, confidence, landmarks and processing time — no identity."
        icon={<ScanFace className="h-5 w-5" />}
      />

      <PrivacyBanner className="mb-6" icon={<SlidersHorizontal className="h-4 w-4" />}>
        <strong>Detection-only mode.</strong> No identity is inferred and nothing is written to the gallery. EXIF
        metadata (GPS, device, timestamps) is stripped from your upload before it is stored.
      </PrivacyBanner>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-2">
          <SectionCard title="Upload">
            <Dropzone
              accept="image/jpeg,image/png,image/webp"
              onFile={(f) => {
                setFile(f);
                setResult(null);
              }}
              disabled={loading}
              hint="JPEG · PNG · WebP — up to 25 MB"
            />
            {file && (
              <div className="mt-3">
                <FileChip file={file} onClear={() => { setFile(null); setResult(null); }} />
              </div>
            )}
            {loading && <Progress value={progress} className="mt-4" />}
            <Button className="mt-4 w-full" onClick={run} disabled={!file || loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanFace className="h-4 w-4" />}
              {loading ? "Analyzing…" : "Run detection"}
            </Button>
          </SectionCard>

          {result && (
            <SectionCard title="Summary">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <Metric label="Faces" value={result.face_count} />
                <Metric label="Processing" value={formatMs(result.processing_ms)} />
                <Metric label="Image" value={`${result.width}×${result.height}`} />
                <Metric label="Mode" value={result.mode} />
              </div>
              {result.annotated_url && (
                <Button variant="secondary" className="mt-4 w-full" asChild>
                  <a href={api.annotatedUrl(result.media_id)} target="_blank" rel="noreferrer">
                    <Download className="h-4 w-4" /> Download annotated image
                  </a>
                </Button>
              )}
            </SectionCard>
          )}
        </div>

        <div className="lg:col-span-3">
          <SectionCard title="Result" description={result ? "Bounding boxes, landmarks & confidence" : "Your analysis appears here"}>
            {preview ? (
              <FaceCanvas
                src={preview}
                width={result?.width ?? 1}
                height={result?.height ?? 1}
                detections={result?.detections ?? []}
              />
            ) : (
              <div className="flex h-72 items-center justify-center rounded-xl border border-dashed border-white/10 text-sm text-muted-foreground">
                Upload an image to begin.
              </div>
            )}

            {result && result.detections.length > 0 && (
              <div className="mt-4 space-y-2">
                {result.detections.map((d, i) => (
                  <div key={d.id} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Face #{i + 1}</span>
                      <Badge variant="cyan">{(d.confidence * 100).toFixed(1)}% confidence</Badge>
                    </div>
                    <p className="mt-1 font-mono text-xs text-muted-foreground">
                      box [{d.bbox.x1.toFixed(0)}, {d.bbox.y1.toFixed(0)}, {d.bbox.x2.toFixed(0)}, {d.bbox.y2.toFixed(0)}]
                      {"  ·  "}
                      {d.landmarks?.length ?? 0} landmarks
                    </p>
                    {d.quality && (
                      <div className="mt-2 flex flex-wrap gap-2 text-xs">
                        <Badge variant={d.quality.passed ? "success" : "warning"}>
                          {d.quality.passed ? "quality ok" : "quality check"}
                        </Badge>
                        <span className="text-muted-foreground">
                          blur {d.quality.blur.toFixed(2)} · light {d.quality.lighting.toFixed(2)} · pose {d.quality.pose.toFixed(2)} · {d.quality.face_size_px}px
                        </span>
                      </div>
                    )}
                  </div>
                ))}
                {result.notices.map((n, i) => (
                  <p key={i} className="text-xs text-muted-foreground">{n}</p>
                ))}
              </div>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-medium capitalize">{value}</p>
    </div>
  );
}
