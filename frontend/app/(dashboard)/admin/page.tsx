"use client";

import * as React from "react";
import {
  Activity,
  Cpu,
  Database,
  FileClock,
  Loader2,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type {
  AuditLog,
  HealthStatus,
  ModelStatus,
  RetentionPolicy,
  Role,
  SystemMetrics,
  User,
} from "@/lib/types";
import { formatDate, pct } from "@/lib/utils";
import { PageHeader, SectionCard } from "@/components/jarvas/page-header";
import { RoleGuard } from "@/components/jarvas/role-guard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/components/providers/auth-provider";

const ROLES: Role[] = ["viewer", "operator", "auditor", "admin"];

export default function AdminPage() {
  return (
    <RoleGuard roles={["auditor"]}>
      <AdminInner />
    </RoleGuard>
  );
}

function AdminInner() {
  const { hasRole } = useAuth();
  const isAdmin = hasRole("admin");

  return (
    <div>
      <PageHeader
        title="Administration"
        description="Manage users and roles, review the immutable audit trail, configure retention, and monitor model health."
        icon={<ShieldCheck className="h-5 w-5" />}
      />
      <Tabs defaultValue={isAdmin ? "users" : "audit"}>
        <TabsList className="flex-wrap">
          {isAdmin && <TabsTrigger value="users"><Users className="mr-1.5 h-3.5 w-3.5" /> Users</TabsTrigger>}
          <TabsTrigger value="audit"><FileClock className="mr-1.5 h-3.5 w-3.5" /> Audit log</TabsTrigger>
          {isAdmin && <TabsTrigger value="retention"><Database className="mr-1.5 h-3.5 w-3.5" /> Retention</TabsTrigger>}
          <TabsTrigger value="system"><Cpu className="mr-1.5 h-3.5 w-3.5" /> System</TabsTrigger>
        </TabsList>
        {isAdmin && <TabsContent value="users"><UsersPanel /></TabsContent>}
        <TabsContent value="audit"><AuditPanel /></TabsContent>
        {isAdmin && <TabsContent value="retention"><RetentionPanel /></TabsContent>}
        <TabsContent value="system"><SystemPanel /></TabsContent>
      </Tabs>
    </div>
  );
}

/* ------------------------------- Users ---------------------------------- */
function UsersPanel() {
  const { user: me } = useAuth();
  const { toast } = useToast();
  const [users, setUsers] = React.useState<User[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [form, setForm] = React.useState({ email: "", full_name: "", password: "", role: "viewer" as Role });

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      setUsers(await api.listUsers());
    } catch (err) {
      toast({ title: "Could not load users", description: err instanceof ApiError ? err.message : "Unexpected error", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  React.useEffect(() => { load(); }, [load]);

  const create = async () => {
    setBusy(true);
    try {
      await api.createUser(form);
      toast({ title: "User created", description: `${form.email} has been added.`, variant: "success" });
      setOpen(false);
      setForm({ email: "", full_name: "", password: "", role: "viewer" });
      await load();
    } catch (err) {
      toast({ title: "Create failed", description: err instanceof ApiError ? err.message : "Unexpected error", variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  const patch = async (id: string, payload: { role?: string; is_active?: boolean }) => {
    try {
      await api.updateUser(id, payload);
      toast({ title: "User updated", variant: "success" });
      await load();
    } catch (err) {
      toast({ title: "Update failed", description: err instanceof ApiError ? err.message : "Unexpected error", variant: "destructive" });
    }
  };

  return (
    <SectionCard
      title="Users & roles"
      description="Role-based access control — every change is audited."
      actions={<Button onClick={() => setOpen(true)}><UserPlus className="h-4 w-4" /> New user</Button>}
    >
      {loading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="hidden md:table-cell">Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.id}>
                <TableCell>
                  <p className="font-medium">{u.full_name || "—"}</p>
                  <p className="text-xs text-muted-foreground">{u.email}{u.id === me?.id && " · you"}</p>
                </TableCell>
                <TableCell>
                  <Select value={u.role} onValueChange={(v) => patch(u.id, { role: v })}>
                    <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={u.is_active}
                      onCheckedChange={(v) => patch(u.id, { is_active: v })}
                      disabled={u.id === me?.id}
                    />
                    <Badge variant={u.is_active ? "success" : "secondary"}>{u.is_active ? "active" : "disabled"}</Badge>
                  </div>
                </TableCell>
                <TableCell className="hidden md:table-cell text-sm text-muted-foreground">{formatDate(u.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create user</DialogTitle>
            <DialogDescription>New users receive a role that determines which actions they may perform.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="u-name">Full name</Label>
              <Input id="u-name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="u-email">Email</Label>
              <Input id="u-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="u-pass">Password</Label>
                <Input id="u-pass" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>Role</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v as Role })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setOpen(false)} disabled={busy}>Cancel</Button>
            <Button onClick={create} disabled={busy || !form.email || form.password.length < 8}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" />} Create user
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SectionCard>
  );
}

/* ------------------------------- Audit ---------------------------------- */
function AuditPanel() {
  const { toast } = useToast();
  const [logs, setLogs] = React.useState<AuditLog[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [action, setAction] = React.useState("");
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.audit({ action: action || undefined, page, size: 15 });
      setLogs(res.items);
      setTotal(res.total);
    } catch (err) {
      toast({ title: "Could not load audit log", description: err instanceof ApiError ? err.message : "Unexpected error", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [action, page, toast]);

  React.useEffect(() => { load(); }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / 15));

  return (
    <SectionCard
      title="Audit trail"
      description={`${total} entries · append-only, immutable`}
      actions={
        <div className="flex items-center gap-2">
          <Input placeholder="Filter by action…" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} className="w-48" />
          <Button variant="ghost" size="icon" onClick={load}><RefreshCw className="h-4 w-4" /></Button>
        </div>
      }
    >
      {loading ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
      ) : logs.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">No audit entries.</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead>Action</TableHead>
                <TableHead className="hidden md:table-cell">Resource</TableHead>
                <TableHead>Outcome</TableHead>
                <TableHead className="hidden lg:table-cell">IP</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((l) => (
                <TableRow key={l.id}>
                  <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDate(l.created_at)}</TableCell>
                  <TableCell className="text-sm">{l.actor_email || "—"}</TableCell>
                  <TableCell><span className="font-mono text-xs">{l.action}</span></TableCell>
                  <TableCell className="hidden md:table-cell text-xs text-muted-foreground">
                    {l.resource_type}{l.resource_id ? ` · ${l.resource_id.slice(0, 8)}` : ""}
                  </TableCell>
                  <TableCell>
                    <Badge variant={l.outcome === "success" ? "success" : l.outcome === "denied" ? "warning" : "destructive"}>{l.outcome}</Badge>
                  </TableCell>
                  <TableCell className="hidden lg:table-cell font-mono text-xs text-muted-foreground">{l.ip_address || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
              <span>Page {page} of {totalPages}</span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</Button>
                <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button>
              </div>
            </div>
          )}
        </>
      )}
    </SectionCard>
  );
}

/* ----------------------------- Retention -------------------------------- */
function RetentionPanel() {
  const { toast } = useToast();
  const [policies, setPolicies] = React.useState<RetentionPolicy[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  const [form, setForm] = React.useState({ name: "", resource_type: "media", retention_days: 180, action: "delete", is_default: false });

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      setPolicies(await api.listRetention());
    } catch (err) {
      toast({ title: "Could not load retention policies", description: err instanceof ApiError ? err.message : "Unexpected error", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  React.useEffect(() => { load(); }, [load]);

  const create = async () => {
    setBusy(true);
    try {
      await api.createRetention(form);
      toast({ title: "Policy created", variant: "success" });
      setOpen(false);
      await load();
    } catch (err) {
      toast({ title: "Create failed", description: err instanceof ApiError ? err.message : "Unexpected error", variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    try {
      await api.deleteRetention(id);
      toast({ title: "Policy deleted", variant: "success" });
      await load();
    } catch (err) {
      toast({ title: "Delete failed", description: err instanceof ApiError ? err.message : "Unexpected error", variant: "destructive" });
    }
  };

  const run = async () => {
    setBusy(true);
    try {
      await api.runRetention();
      toast({ title: "Retention sweep run", description: "Expired consents purged and media evaluated.", variant: "success" });
      await load();
    } catch (err) {
      toast({ title: "Sweep failed", description: err instanceof ApiError ? err.message : "Unexpected error", variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <SectionCard
      title="Retention policies"
      description="Encrypt-at-rest templates are purged once consent expires or retention elapses."
      actions={
        <div className="flex gap-2">
          <Button variant="secondary" onClick={run} disabled={busy}><RefreshCw className="h-4 w-4" /> Run sweep</Button>
          <Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> New policy</Button>
        </div>
      }
    >
      {loading ? (
        <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
      ) : policies.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">No retention policies.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Resource</TableHead>
              <TableHead>Retention</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Default</TableHead>
              <TableHead className="text-right">—</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {policies.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="font-medium">{p.name}</TableCell>
                <TableCell><Badge variant="secondary">{p.resource_type}</Badge></TableCell>
                <TableCell className="text-sm">{p.retention_days} days</TableCell>
                <TableCell><Badge variant="cyan">{p.action}</Badge></TableCell>
                <TableCell>{p.is_default ? <Badge variant="success">default</Badge> : "—"}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="icon" className="text-rose-300" onClick={() => remove(p.id)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New retention policy</DialogTitle>
            <DialogDescription>Define how long data of a given type may be kept.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="r-name">Name</Label>
              <Input id="r-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Biometric template retention" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Resource type</Label>
                <Select value={form.resource_type} onValueChange={(v) => setForm({ ...form, resource_type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="media">media</SelectItem>
                    <SelectItem value="identity">identity</SelectItem>
                    <SelectItem value="audit">audit</SelectItem>
                    <SelectItem value="video">video</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Action</Label>
                <Select value={form.action} onValueChange={(v) => setForm({ ...form, action: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="delete">delete</SelectItem>
                    <SelectItem value="anonymize">anonymize</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="r-days">Retention (days)</Label>
              <Input id="r-days" type="number" min={1} value={form.retention_days} onChange={(e) => setForm({ ...form, retention_days: Number(e.target.value) })} />
            </div>
            <label className="flex items-center gap-3">
              <Switch checked={form.is_default} onCheckedChange={(v) => setForm({ ...form, is_default: v })} />
              <span className="text-sm">Use as default policy</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setOpen(false)} disabled={busy}>Cancel</Button>
            <Button onClick={create} disabled={busy || !form.name || form.retention_days < 1}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" />} Create policy
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SectionCard>
  );
}

/* ------------------------------ System ---------------------------------- */
function SystemPanel() {
  const { toast } = useToast();
  const [health, setHealth] = React.useState<HealthStatus | null>(null);
  const [models, setModels] = React.useState<ModelStatus[]>([]);
  const [metrics, setMetrics] = React.useState<SystemMetrics | null>(null);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [h, m, s] = await Promise.all([
        api.health(),
        api.models().catch(() => []),
        api.metrics().catch(() => null),
      ]);
      setHealth(h);
      setModels(m);
      setMetrics(s);
    } catch (err) {
      toast({ title: "Could not load system status", description: err instanceof ApiError ? err.message : "Unexpected error", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  React.useEffect(() => { load(); }, [load]);

  if (loading) return <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <SectionCard title="Components" description="Readiness of backend dependencies">
        <div className="space-y-3">
          {health?.components.map((c) => (
            <div key={c.name} className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.03] px-4 py-3">
              <div className="flex items-center gap-3">
                <Activity className="h-4 w-4 text-cyan-300" />
                <div>
                  <p className="text-sm font-medium capitalize">{c.name}</p>
                  <p className="text-xs text-muted-foreground">{c.detail}</p>
                </div>
              </div>
              <Badge variant={c.status === "ok" ? "success" : c.status === "degraded" ? "warning" : "destructive"}>{c.status}</Badge>
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Models" description="Inference providers & embedding dimensions">
        <div className="space-y-3">
          {models.map((m) => (
            <div key={`${m.task}-${m.name}`} className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.03] px-4 py-3">
              <div className="flex items-center gap-3">
                <Cpu className="h-4 w-4 text-indigo-300" />
                <div>
                  <p className="text-sm font-medium">{m.name}</p>
                  <p className="text-xs capitalize text-muted-foreground">{m.task} · {m.provider} · {m.embedding_dim}-d</p>
                </div>
              </div>
              <div className="flex gap-2">
                {m.is_mock && <Badge variant="warning">mock</Badge>}
                <Badge variant={m.loaded ? "success" : "secondary"}>{m.loaded ? "loaded" : "idle"}</Badge>
              </div>
            </div>
          ))}
        </div>
      </SectionCard>

      {metrics && (
        <SectionCard title="Metrics" description="Aggregate, tenant-scoped" className="lg:col-span-2">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Metric label="Identities" value={metrics.total_identities} />
            <Metric label="Active consents" value={metrics.active_consents} />
            <Metric label="Expired" value={metrics.expired_consents} />
            <Metric label="Media" value={metrics.total_media} />
            <Metric label="Video jobs" value={metrics.total_video_jobs} />
            <Metric label="Pending" value={metrics.pending_video_jobs} />
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Consent coverage: {metrics.total_identities > 0 ? pct(metrics.active_consents / metrics.total_identities) : "—"} of identities have active consent.
          </p>
        </SectionCard>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}
