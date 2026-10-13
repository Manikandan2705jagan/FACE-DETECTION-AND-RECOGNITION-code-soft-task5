"use client";

import * as React from "react";
import { BrainCircuit, Loader2, ShieldAlert } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { DetectionResponse } from "@/lib/types";
import { formatMs, pct } from "@/lib/utils";
import { PageHeader, SectionCard } from "@/components/jarvas/page-header";
import { Dropzone, FileChip } from "@/components/jarvas/dropzone";
import { FaceCanvas } from "@/components/jarvas/face-canvas";
import { PrivacyBanner } from "@/components/jarvas/privacy-banner";
import { RoleGuard } from "@/components/jarvas/role-guard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/components/ui/toast";

export default function RecognizePage() {
  return (
    <RoleGuard roles={["operator"]}>
      <RecognizeInner />
    </RoleGuard>
  );
}

function RecognizeInner() {
  const { toast } = useToast();
  const [file, setFile] = React.useState<File | null>(null);
  const [preview, setPreview] = React.useState<string | null>(null);
  const [threshold, setThreshold] = React.useState(0.38);
  const [result, setResult] = React.useState<DetectionResponse | null>(null);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (!file) { setPreview(null); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const run = async () => {
    if (!file) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await api.recognize(file, threshold, 3);
      setResult(res);
      toast({ title: "Recognition complete", description: "Results are advisory candidates.", variant: "default" });
    } catch (err) {
      toast({
        title: "Recognition failed",
        description: err instanceof ApiError ? err.message : "Unexpected error",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const top = result?.recognition?.[0];
  const labels = top?.status === "candidate" && top.candidate_name
    ? [ `Candidate: ${top.candidate_name} — review required` ]
    : result?.recognition
      ? ["No confirmed match"]
      : undefined;

  return (
    <div>
      <PageHeader
        title="Recognition"
        description="Search only the local, consented identity gallery. Results are similarity-based candidates that require manual human review — never a certain identity."
        icon={<BrainCircuit className="h-5 w-5" />}
      />

      <Alert variant="warning" className="mb-6">
        <ShieldAlert className="h-4 w-4" />
        <AlertTitle>Advisory only — human review required</AlertTitle>
        <AlertDescription>
          A high similarity score is <strong>not proof of identity</strong>. Never take consequential action based
          on an unverified candidate. JARVAS searches only identities that gave explicit, unexpired consent.
        </AlertDescription>
      </Alert>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-2">
          <SectionCard title="Upload">
            <Dropzone accept="image/jpeg,image/png,image/webp" onFile={(f) => { setFile(f); setResult(null); }} disabled={loading} hint="JPEG · PNG · WebP" />
            {file && <div className="mt-3"><FileChip file={file} onClear={() => setFile(null)} /></div>}
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="threshold">Similarity threshold</Label>
                <span className="font-mono text-xs text-cyan-300">{threshold.toFixed(2)}</span>
              </div>
              <input
                id="threshold"
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-full accent-cyan-400"
              />
              <p className="text-xs text-muted-foreground">Candidates scoring below this are reported as no-match. Calibrate per use case (docs/CALIBRATION.md).</p>
            </div>
            <Button className="mt-4 w-full" onClick={run} disabled={!file || loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <BrainCircuit className="h-4 w-4" />}
              {loading ? "Searching gallery…" : "Recognize"}
            </Button>
          </SectionCard>

          {result && top && (
            <SectionCard title="Best candidate">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-lg font-semibold">{top.candidate_name || "No candidate above threshold"}</p>
                    <p className="text-xs text-muted-foreground">Best match from consented gallery</p>
                  </div>
                  <Badge variant={top.status === "candidate" ? "success" : "secondary"}>{top.status}</Badge>
                </div>
                <div>
                  <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                    <span>Cosine similarity</span>
                    <span>{pct(top.cosine_similarity)} (threshold {top.threshold.toFixed(2)})</span>
                  </div>
                  <Progress value={top.cosine_similarity * 100} />
                </div>
                {top.manual_review_required && (
                  <Badge variant="warning" className="w-full justify-center py-1.5">
                    Manual review required
                  </Badge>
                )}
              </div>
            </SectionCard>
          )}
        </div>

        <div className="lg:col-span-3">
          <SectionCard title="Annotated result" description={result ? `Processed in ${formatMs(result.processing_ms)}` : "Your analysis appears here"}>
            {preview ? (
              <FaceCanvas src={preview} width={result?.width ?? 1} height={result?.height ?? 1} detections={result?.detections ?? []} labels={labels} />
            ) : (
              <div className="flex h-80 items-center justify-center rounded-xl border border-dashed border-white/10 text-sm text-muted-foreground">
                Upload an image to search the consented gallery.
              </div>
            )}

            {result?.recognition && result.recognition.length > 0 && (
              <div className="mt-4 space-y-2">
                {result.recognition.map((r, i) => (
                  <div key={i} className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm">
                    <div>
                      <p className="font-medium">{r.candidate_name || "—"}</p>
                      <p className="text-xs text-muted-foreground">{r.status === "no_match" ? "Below threshold" : "Candidate"}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-mono text-sm text-cyan-300">{r.cosine_similarity.toFixed(3)}</p>
                      <p className="text-[10px] text-muted-foreground">threshold {r.threshold.toFixed(2)}</p>
                    </div>
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
