"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, ClipboardList, Loader2, ShieldCheck, UserPlus } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { PageHeader, SectionCard } from "@/components/jarvas/page-header";
import { Dropzone, FileChip } from "@/components/jarvas/dropzone";
import { PrivacyBanner } from "@/components/jarvas/privacy-banner";
import { RoleGuard } from "@/components/jarvas/role-guard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/components/ui/toast";

const CONSENT_TEXT_VERSION = "2026-01";

function toIso(date: string): string {
  return new Date(`${date}T12:00:00Z`).toISOString();
}

function defaultDate(daysFromNow: number): string {
  const d = new Date(Date.now() + daysFromNow * 86400000);
  return d.toISOString().slice(0, 10);
}

export default function EnrollPage() {
  return (
    <RoleGuard roles={["operator"]}>
      <EnrollInner />
    </RoleGuard>
  );
}

function EnrollInner() {
  const { toast } = useToast();
  const router = useRouter();
  const [fullName, setFullName] = React.useState("");
  const [notes, setNotes] = React.useState("");
  const [consent, setConsent] = React.useState(false);
  const [purpose, setPurpose] = React.useState("Voluntary access-control enrollment");
  const [expiresAt, setExpiresAt] = React.useState(defaultDate(365));
  const [retentionUntil, setRetentionUntil] = React.useState(defaultDate(180));
  const [file, setFile] = React.useState<File | null>(null);
  const [identityId, setIdentityId] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [qualityReasons, setQualityReasons] = React.useState<string[]>([]);

  const canSubmit = fullName.trim().length >= 2 && consent && purpose.trim().length >= 5 && !!file && !submitting;

  const submit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setQualityReasons([]);
    try {
      let id = identityId;
      if (!id) {
        const identity = await api.createIdentity({
          full_name: fullName.trim(),
          notes,
          consent: {
            consent_granted: true,
            purpose: purpose.trim(),
            expires_at: toIso(expiresAt),
            retention_until: toIso(retentionUntil),
            consent_text_version: CONSENT_TEXT_VERSION,
          },
        });
        id = identity.id;
        setIdentityId(id);
      }
      const enrollment = await api.enroll(id, file as File);
      toast({
        title: "Enrollment complete",
        description: `Consented template stored and encrypted at rest (quality ${(enrollment.quality_score * 100).toFixed(0)}%).`,
        variant: "success",
      });
      router.push("/gallery");
    } catch (err) {
      if (err instanceof ApiError) {
        const reasons = extractReasons(err.message);
        setQualityReasons(reasons.length ? reasons : [err.message]);
        toast({ title: "Enrollment not completed", description: err.message.slice(0, 160), variant: "destructive" });
      } else {
        toast({ title: "Enrollment failed", description: "Unexpected error", variant: "destructive" });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Enroll a Consented Face"
        description="Enrollment requires explicit consent and exactly one clear face. Templates are encrypted at rest and deletable at any time."
        icon={<UserPlus className="h-5 w-5" />}
      />

      <PrivacyBanner className="mb-6" tone="warning" icon={<ShieldCheck className="h-4 w-4" />}>
        <strong>Consent is mandatory.</strong> By enrolling you confirm the person gave explicit, informed consent
        for the stated purpose and retention period, and that they understand they can withdraw consent and request
        permanent deletion at any time. Do not enroll anyone without their consent.
      </PrivacyBanner>

      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard title="1 · Person details" className="lg:col-span-1">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Full name</Label>
              <Input id="name" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="e.g. Alex Rivera" disabled={!!identityId} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="notes">Notes (optional)</Label>
              <Textarea id="notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Internal context for this enrollment" disabled={!!identityId} />
            </div>
            {identityId && (
              <Badge variant="success" className="w-full justify-center py-1.5">
                Identity created — add the enrollment photo
              </Badge>
            )}
          </div>
        </SectionCard>

        <SectionCard title="2 · Consent record" description="Purpose-bound and expiring" className="lg:col-span-1">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="purpose">Consent purpose</Label>
              <Input id="purpose" value={purpose} onChange={(e) => setPurpose(e.target.value)} disabled={!!identityId} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="expires">Consent expiry</Label>
                <Input id="expires" type="date" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} disabled={!!identityId} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="retention">Retention until</Label>
                <Input id="retention" type="date" value={retentionUntil} onChange={(e) => setRetentionUntil(e.target.value)} disabled={!!identityId} />
              </div>
            </div>
            <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-white/10 bg-white/[0.03] p-3">
              <Checkbox checked={consent} onCheckedChange={(v) => setConsent(Boolean(v))} className="mt-0.5" disabled={!!identityId} />
              <span className="text-sm leading-relaxed">
                I confirm the person has given <strong>explicit consent</strong> to enroll their face for the
                purpose above, and understands they can withdraw consent and request deletion.
              </span>
            </label>
            <p className="text-xs text-muted-foreground">Consent text version {CONSENT_TEXT_VERSION} · an evidence hash is stored with every consent record.</p>
          </div>
        </SectionCard>

        <SectionCard title="3 · Enrollment image" description="Exactly one clear face" className="lg:col-span-1">
          <Dropzone accept="image/jpeg,image/png,image/webp" onFile={setFile} disabled={submitting} hint="One face · clear lighting · frontal" />
          {file && <div className="mt-3"><FileChip file={file} onClear={() => setFile(null)} /></div>}
          <ul className="mt-4 space-y-1 text-xs text-muted-foreground">
            <li>· Exactly one face in frame</li>
            <li>· Sharp (not blurry)</li>
            <li>· Even lighting</li>
            <li>· Frontal head pose</li>
            <li>· Face at least 80px</li>
          </ul>
          <Button className="mt-4 w-full" onClick={submit} disabled={!canSubmit}>
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            {submitting ? "Enrolling…" : identityId ? "Enroll photo" : "Create & enroll"}
          </Button>
        </SectionCard>
      </div>

      {qualityReasons.length > 0 && (
        <Alert variant="destructive" className="mt-6">
          <ClipboardList className="h-4 w-4" />
          <AlertTitle>Enrollment rejected</AlertTitle>
          <AlertDescription>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {qualityReasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}

function extractReasons(message: string): string[] {
  try {
    const parsed = JSON.parse(message);
    if (Array.isArray(parsed?.reasons)) return parsed.reasons;
  } catch {
    /* not JSON */
  }
  return [];
}
