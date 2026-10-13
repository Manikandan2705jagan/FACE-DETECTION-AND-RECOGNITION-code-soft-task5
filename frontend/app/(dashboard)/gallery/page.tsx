"use client";

import * as React from "react";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  Loader2,
  Search,
  ShieldOff,
  Trash2,
  UserCog,
  Users,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { Identity } from "@/lib/types";
import { daysUntil, formatDay } from "@/lib/utils";
import { PageHeader, SectionCard } from "@/components/jarvas/page-header";
import { PrivacyBanner } from "@/components/jarvas/privacy-banner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";

const PAGE_SIZE = 10;

export default function GalleryPage() {
  const { toast } = useToast();
  const [items, setItems] = React.useState<Identity[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [query, setQuery] = React.useState("");
  const [debounced, setDebounced] = React.useState("");
  const [consentStatus, setConsentStatus] = React.useState("all");
  const [loading, setLoading] = React.useState(true);
  const [consentTarget, setConsentTarget] = React.useState<Identity | null>(null);
  const [deleteTarget, setDeleteTarget] = React.useState<Identity | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    const t = setTimeout(() => { setDebounced(query); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [query]);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listIdentities({
        q: debounced || undefined,
        consent_status: consentStatus === "all" ? undefined : consentStatus,
        page,
        size: PAGE_SIZE,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      toast({
        title: "Could not load gallery",
        description: err instanceof ApiError ? err.message : "Unexpected error",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [debounced, consentStatus, page, toast]);

  React.useEffect(() => { load(); }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const exportIdentity = async (identity: Identity) => {
    try {
      const data = await api.exportIdentity(identity.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `jarvas-identity-${identity.id}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast({ title: "Export ready", description: "Subject data access export downloaded.", variant: "success" });
    } catch (err) {
      toast({ title: "Export failed", description: err instanceof ApiError ? err.message : "Unexpected error", variant: "destructive" });
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setBusy(true);
    try {
      await api.deleteIdentity(deleteTarget.id);
      toast({ title: "Identity erased", description: "Templates and consent records were permanently deleted.", variant: "success" });
      setDeleteTarget(null);
      await load();
    } catch (err) {
      toast({ title: "Deletion failed", description: err instanceof ApiError ? err.message : "Unexpected error", variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Consented Gallery"
        description="Every identity here gave explicit, purpose-bound consent. You can review consent, export subject data, or erase an identity irreversibly."
        icon={<Users className="h-5 w-5" />}
        actions={
          <Button variant="secondary" asChild>
            <a href="/enroll"><UserCog className="h-4 w-4" /> Enroll new</a>
          </Button>
        }
      />

      <PrivacyBanner className="mb-6">
        Recognition searches only these consented identities. Revoking consent or deleting an identity immediately
        removes its templates from the searchable set — deletion is irreversible and recorded in the audit trail.
      </PrivacyBanner>

      <SectionCard
        title="Identities"
        description={`${total} record${total === 1 ? "" : "s"}`}
        actions={
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full pl-9 sm:w-56"
              />
            </div>
            <Select value={consentStatus} onValueChange={(v) => { setConsentStatus(v); setPage(1); }}>
              <SelectTrigger className="w-full sm:w-40">
                <SelectValue placeholder="Consent" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All consents</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="expired">Expired</SelectItem>
                <SelectItem value="revoked">Revoked</SelectItem>
              </SelectContent>
            </Select>
          </div>
        }
      >
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-14 text-center">
            <Users className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm font-medium">No identities found</p>
            <p className="text-xs text-muted-foreground">
              {debounced || consentStatus !== "all" ? "Try adjusting your filters." : "Enroll a consented face to get started."}
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Consent</TableHead>
                <TableHead className="hidden md:table-cell">Consent expiry</TableHead>
                <TableHead className="hidden lg:table-cell">Templates</TableHead>
                <TableHead className="hidden lg:table-cell">Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((identity) => (
                <TableRow key={identity.id}>
                  <TableCell>
                    <p className="font-medium">{identity.full_name}</p>
                    {identity.notes && <p className="truncate text-xs text-muted-foreground">{identity.notes}</p>}
                  </TableCell>
                  <TableCell><ConsentBadge identity={identity} /></TableCell>
                  <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                    {formatDay(identity.consent_expires_at)}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    <Badge variant={identity.enrollment_count > 0 ? "cyan" : "secondary"}>{identity.enrollment_count}</Badge>
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                    {formatDay(identity.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-1">
                      <Button variant="ghost" size="icon" title="Manage consent" onClick={() => setConsentTarget(identity)}>
                        <ShieldOff className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Export subject data" onClick={() => exportIdentity(identity)}>
                        <Download className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Delete identity" className="text-rose-300 hover:text-rose-200" onClick={() => setDeleteTarget(identity)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {totalPages > 1 && (
          <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
            <span>Page {page} of {totalPages}</span>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                <ChevronLeft className="h-4 w-4" /> Prev
              </Button>
              <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                Next <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </SectionCard>

      <ConsentDialog
        identity={consentTarget}
        onClose={() => setConsentTarget(null)}
        onSaved={() => { setConsentTarget(null); load(); }}
      />

      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-rose-200">
              <Trash2 className="h-4 w-4" /> Erase identity
            </DialogTitle>
            <DialogDescription>
              This permanently deletes <strong>{deleteTarget?.full_name}</strong>, all consent records and all
              enrolled templates. This action cannot be undone and is written to the audit trail.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-rose-500/25 bg-rose-500/[0.06] p-3 text-sm">
            Deleting removes the biometric templates from storage and any searchable index immediately.
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)} disabled={busy}>Cancel</Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              {busy ? "Erasing…" : "Erase permanently"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ConsentBadge({ identity }: { identity: Identity }) {
  if (identity.deleted_at) return <Badge variant="destructive">deleted</Badge>;
  if (!identity.consent_active) return <Badge variant="secondary">revoked</Badge>;
  const days = daysUntil(identity.consent_expires_at);
  if (days !== null && days < 0) return <Badge variant="warning">expired</Badge>;
  if (days !== null && days <= 30) return <Badge variant="warning">expires in {days}d</Badge>;
  return <Badge variant="success">active</Badge>;
}

function ConsentDialog({
  identity,
  onClose,
  onSaved,
}: {
  identity: Identity | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { toast } = useToast();
  const [expiresAt, setExpiresAt] = React.useState("");
  const [retentionUntil, setRetentionUntil] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (identity) {
      setExpiresAt(identity.consent_expires_at?.slice(0, 10) ?? "");
      setRetentionUntil(identity.retention_until?.slice(0, 10) ?? "");
    }
  }, [identity]);

  const save = async (revoked: boolean) => {
    if (!identity) return;
    setBusy(true);
    try {
      await api.updateConsent(identity.id, {
        expires_at: expiresAt ? new Date(`${expiresAt}T12:00:00Z`).toISOString() : undefined,
        retention_until: retentionUntil ? new Date(`${retentionUntil}T12:00:00Z`).toISOString() : undefined,
        revoked: revoked || undefined,
      });
      toast({
        title: revoked ? "Consent revoked" : "Consent updated",
        description: revoked ? "Templates are no longer searchable." : "New consent terms saved.",
        variant: revoked ? "warning" : "success",
      });
      onSaved();
    } catch (err) {
      toast({ title: "Update failed", description: err instanceof ApiError ? err.message : "Unexpected error", variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={!!identity} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Manage consent</DialogTitle>
          <DialogDescription>
            {identity?.full_name} · consent can be extended, shortened, or withdrawn. Withdrawal stops all
            recognition against this identity.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="c-expiry">Consent expiry</Label>
            <Input id="c-expiry" type="date" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="c-retention">Retention until</Label>
            <Input id="c-retention" type="date" value={retentionUntil} onChange={(e) => setRetentionUntil(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
          {identity?.consent_active && (
            <Button variant="secondary" onClick={() => save(true)} disabled={busy}>
              <ShieldOff className="h-4 w-4" /> Revoke consent
            </Button>
          )}
          <Button onClick={() => save(false)} disabled={busy}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Save changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
