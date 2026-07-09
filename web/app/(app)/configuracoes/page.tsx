"use client";

import {
  Bot,
  Building2,
  KeyRound,
  Loader2,
  Lock,
  Pencil,
  Plus,
  RotateCcw,
  Save,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UserCog,
  Users2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import useSWR, { mutate } from "swr";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  api,
  ApiError,
  type CopilotPromptItem,
  type CopilotSettings,
  type PermissionInfo,
  type RoleRecord,
  type TenantResponse,
  type UserResponse,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

// Rótulos amigáveis de fallback p/ os perfis de sistema (o nome real vem da API).
const ROLE_LABEL: Record<string, string> = {
  admin: "Admin",
  analyst: "Analista",
  viewer: "Visualizador",
};

function errMessage(err: unknown, fallback = "Erro"): string {
  if (err instanceof ApiError) {
    if (err.status === 403) return "Você não tem permissão para esta ação.";
    return err.message;
  }
  return fallback;
}

/* ----------------------------- Perfil ----------------------------- */

function PerfilTab() {
  const { user, refreshMe } = useAuth();
  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setNome(user?.name ?? "");
  }, [user?.name]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (senha && senha.length < 8) {
      toast.error("A nova senha deve ter ao menos 8 caracteres.");
      return;
    }
    setSaving(true);
    try {
      await api.updateMe({
        name: nome || undefined,
        password: senha ? senha : undefined,
      });
      await refreshMe();
      setSenha("");
      toast.success("Perfil atualizado.");
    } catch (err) {
      toast.error(errMessage(err, "Falha ao atualizar perfil."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="edge-gold-top shadow-premium max-w-2xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UserCog className="size-5 text-gold" />
          Seu perfil
        </CardTitle>
        <CardDescription>Atualize seu nome e senha de acesso.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="grid gap-5">
          <div className="grid gap-2">
            <Label htmlFor="perfil-nome">Nome</Label>
            <Input
              id="perfil-nome"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              placeholder="Seu nome"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="perfil-email">Email</Label>
            <Input
              id="perfil-email"
              value={user?.email ?? ""}
              disabled
              className="text-muted-foreground"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="perfil-senha">Nova senha</Label>
            <Input
              id="perfil-senha"
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              placeholder="deixe em branco para não alterar"
            />
            <p className="text-xs text-muted-foreground">Mínimo de 8 caracteres.</p>
          </div>

          <Separator />

          <div className="flex justify-end">
            <Button type="submit" disabled={saving}>
              {saving ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Save className="size-4" />
              )}
              Salvar
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

/* ----------------------------- Empresa ----------------------------- */

function EmpresaTab({ isAdmin }: { isAdmin: boolean }) {
  const { data: tenant, isLoading, error } = useSWR<TenantResponse>(
    "tenant",
    () => api.getTenant(),
    {
      onError: (err) => toast.error(errMessage(err, "Falha ao carregar empresa.")),
    },
  );

  const [nome, setNome] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (tenant) setNome(tenant.name);
  }, [tenant]);

  async function handleSave() {
    setSaving(true);
    try {
      await api.updateTenant(nome);
      await mutate("tenant");
      toast.success("Empresa atualizada.");
    } catch (err) {
      toast.error(errMessage(err, "Falha ao atualizar empresa."));
    } finally {
      setSaving(false);
    }
  }

  if (isLoading) {
    return (
      <Card className="edge-gold-top shadow-premium max-w-2xl">
        <CardContent className="grid gap-5 pt-2">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-28 justify-self-end" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="max-w-2xl">
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          Não foi possível carregar os dados da empresa.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="edge-gold-top shadow-premium max-w-2xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building2 className="size-5 text-gold" />
          Empresa
        </CardTitle>
        <CardDescription>Dados da sua organização no Kairon Frete.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-5">
          <div className="grid gap-2">
            <Label htmlFor="empresa-nome">Nome da empresa</Label>
            <Input
              id="empresa-nome"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              disabled={!isAdmin}
              className={cn(!isAdmin && "text-muted-foreground")}
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="empresa-slug">Slug</Label>
            <Input
              id="empresa-slug"
              value={tenant?.slug ?? ""}
              disabled
              className="font-mono text-muted-foreground"
            />
          </div>

          {isAdmin ? (
            <>
              <Separator />
              <div className="flex justify-end">
                <Button
                  onClick={handleSave}
                  disabled={saving || !nome.trim() || nome === tenant?.name}
                >
                  {saving ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Save className="size-4" />
                  )}
                  Salvar
                </Button>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Somente admin pode editar a empresa.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/* ----------------------------- Novo usuário ----------------------------- */

function NovoUsuarioDialog() {
  const [open, setOpen] = useState(false);
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [role, setRole] = useState("viewer");
  const [saving, setSaving] = useState(false);
  const { data: roles } = useSWR("roles", () => api.listRoles());

  function reset() {
    setNome("");
    setEmail("");
    setSenha("");
    setRole("viewer");
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) {
      toast.error("Informe o email.");
      return;
    }
    if (senha.length < 8) {
      toast.error("A senha deve ter ao menos 8 caracteres.");
      return;
    }
    setSaving(true);
    try {
      await api.createUser(email.trim(), senha, role, nome.trim() || undefined);
      await mutate("users");
      toast.success("Usuário criado.");
      reset();
      setOpen(false);
    } catch (err) {
      toast.error(errMessage(err, "Falha ao criar usuário."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus className="size-4" />
          Novo usuário
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Novo usuário</DialogTitle>
          <DialogDescription>
            Adicione um membro à sua empresa e defina o papel de acesso.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleCreate} className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="novo-nome">Nome</Label>
            <Input
              id="novo-nome"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              placeholder="Opcional"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="novo-email">Email</Label>
            <Input
              id="novo-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="pessoa@empresa.com"
              required
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="novo-senha">Senha</Label>
            <Input
              id="novo-senha"
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              placeholder="Mínimo 8 caracteres"
              required
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="novo-papel">Perfil</Label>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger id="novo-papel" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(roles ?? []).map((r) => (
                  <SelectItem key={r.slug} value={r.slug}>
                    {r.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <DialogFooter>
            <Button type="submit" disabled={saving}>
              {saving ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Plus className="size-4" />
              )}
              Criar usuário
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/* ----------------------------- Linha da tabela ----------------------------- */

function UserRow({ u, currentUserId }: { u: UserResponse; currentUserId?: string }) {
  const [busyRole, setBusyRole] = useState(false);
  const [busyActive, setBusyActive] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [novaSenha, setNovaSenha] = useState("");
  const [busyReset, setBusyReset] = useState(false);
  const { data: roles } = useSWR("roles", () => api.listRoles());
  const isSelf = u.id === currentUserId;

  async function resetSenha() {
    if (novaSenha.length < 8) {
      toast.error("A nova senha deve ter ao menos 8 caracteres.");
      return;
    }
    setBusyReset(true);
    try {
      await api.updateUser(u.id, { password: novaSenha });
      toast.success("Senha redefinida. O usuário precisará entrar novamente.");
      setResetOpen(false);
      setNovaSenha("");
    } catch (err) {
      toast.error(errMessage(err, "Falha ao redefinir senha."));
    } finally {
      setBusyReset(false);
    }
  }

  async function changeRole(role: string) {
    if (role === u.role) return;
    setBusyRole(true);
    try {
      await api.updateUser(u.id, { role });
      await mutate("users");
      toast.success("Papel atualizado.");
    } catch (err) {
      toast.error(errMessage(err, "Falha ao atualizar papel."));
    } finally {
      setBusyRole(false);
    }
  }

  async function toggleActive() {
    setBusyActive(true);
    try {
      await api.updateUser(u.id, { is_active: !u.is_active });
      await mutate("users");
      toast.success(u.is_active ? "Usuário desativado." : "Usuário ativado.");
    } catch (err) {
      toast.error(errMessage(err, "Falha ao atualizar status."));
    } finally {
      setBusyActive(false);
    }
  }

  return (
    <TableRow className={cn(!u.is_active && "opacity-60")}>
      <TableCell className="font-medium">{u.name || "—"}</TableCell>
      <TableCell className="text-muted-foreground">{u.email}</TableCell>
      <TableCell>
        <Select value={u.role} onValueChange={changeRole} disabled={busyRole || isSelf}>
          <SelectTrigger className="h-8 w-40">
            <SelectValue placeholder={ROLE_LABEL[u.role] ?? u.role} />
          </SelectTrigger>
          <SelectContent>
            {(roles ?? []).map((r) => (
              <SelectItem key={r.slug} value={r.slug}>
                {r.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TableCell>
      <TableCell>
        {u.is_active ? (
          <Badge variant="outline" className="border-success/30 text-success">
            Ativo
          </Badge>
        ) : (
          <Badge variant="secondary" className="text-muted-foreground">
            Inativo
          </Badge>
        )}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex justify-end gap-2">
          {!isSelf && (
            <Dialog open={resetOpen} onOpenChange={setResetOpen}>
              <DialogTrigger asChild>
                <Button size="sm" variant="ghost">
                  Resetar senha
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Redefinir senha de {u.email}</DialogTitle>
                </DialogHeader>
                <div className="space-y-2">
                  <Label htmlFor={`reset-${u.id}`}>Nova senha (mín. 8)</Label>
                  <Input
                    id={`reset-${u.id}`}
                    type="password"
                    value={novaSenha}
                    onChange={(e) => setNovaSenha(e.target.value)}
                    autoComplete="new-password"
                  />
                  <p className="text-xs text-muted-foreground">
                    As sessões atuais do usuário serão encerradas.
                  </p>
                </div>
                <DialogFooter>
                  <Button onClick={resetSenha} disabled={busyReset}>
                    {busyReset ? <Loader2 className="size-4 animate-spin" /> : "Redefinir"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={toggleActive}
            disabled={busyActive || isSelf}
          >
            {busyActive ? (
              <Loader2 className="size-4 animate-spin" />
            ) : u.is_active ? (
              "Desativar"
            ) : (
              "Ativar"
            )}
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}

/* ----------------------------- Usuários ----------------------------- */

function UsuariosTab({ isAdmin, currentUserId }: { isAdmin: boolean; currentUserId?: string }) {
  const { data: users, isLoading, error } = useSWR<UserResponse[]>(
    isAdmin ? "users" : null,
    () => api.listUsers(),
    {
      onError: (err) => toast.error(errMessage(err, "Falha ao carregar usuários.")),
    },
  );

  if (!isAdmin) {
    return (
      <Card className="shadow-premium mx-auto max-w-lg">
        <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
          <div className="flex size-14 items-center justify-center rounded-full bg-secondary ring-1 ring-border">
            <Lock className="size-7 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-medium">Acesso restrito a administradores.</h3>
          <p className="max-w-sm text-sm text-muted-foreground">
            A gestão de usuários da empresa está disponível apenas para perfis admin.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="edge-gold-top shadow-premium">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1.5">
          <CardTitle className="flex items-center gap-2">
            <Users2 className="size-5 text-gold" />
            Usuários
          </CardTitle>
          <CardDescription>Gerencie os membros e permissões da empresa.</CardDescription>
        </div>
        <NovoUsuarioDialog />
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : error ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Não foi possível carregar os usuários.
          </p>
        ) : (users?.length ?? 0) === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Nenhum usuário cadastrado ainda.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Papel</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users?.map((u) => (
                <UserRow key={u.id} u={u} currentUserId={currentUserId} />
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

/* ----------------------------- Perfis & Permissões ----------------------------- */

function PerfisTab({ isAdmin }: { isAdmin: boolean }) {
  const { data: roles, isLoading } = useSWR("roles", () => api.listRoles());
  const { data: catalog } = useSWR("permissions", () => api.listPermissions());
  const [dialogRole, setDialogRole] = useState<RoleRecord | null>(null);
  const [creating, setCreating] = useState(false);

  if (!isAdmin) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
          <ShieldAlert className="size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Você não tem permissão para gerenciar perfis.
          </p>
        </CardContent>
      </Card>
    );
  }

  async function handleDelete(r: RoleRecord) {
    if (!window.confirm(`Excluir o perfil "${r.name}"?`)) return;
    try {
      await api.deleteRole(r.id);
      await mutate("roles");
      toast.success("Perfil excluído.");
    } catch (err) {
      toast.error(errMessage(err, "Falha ao excluir perfil."));
    }
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-4">
        <div>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-gold" /> Perfis & Permissões
          </CardTitle>
          <CardDescription>Defina o que cada perfil pode fazer.</CardDescription>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="size-4" /> Novo perfil
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Perfil</TableHead>
                <TableHead>Permissões</TableHead>
                <TableHead>Usuários</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(roles ?? []).map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-medium">
                    {r.name}
                    {r.is_system && (
                      <Badge variant="secondary" className="ml-2 text-[10px]">
                        sistema
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {r.permissions.length} de {catalog?.length ?? 14}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{r.user_count}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button size="sm" variant="ghost" onClick={() => setDialogRole(r)}>
                        <Pencil className="size-4" /> Editar
                      </Button>
                      {!r.is_system && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-destructive"
                          onClick={() => handleDelete(r)}
                          aria-label={`Excluir ${r.name}`}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      {(creating || dialogRole) && catalog && (
        <RoleDialog
          role={dialogRole}
          catalog={catalog}
          onClose={() => {
            setCreating(false);
            setDialogRole(null);
          }}
        />
      )}
    </Card>
  );
}

function RoleDialog({
  role,
  catalog,
  onClose,
}: {
  role: RoleRecord | null;
  catalog: PermissionInfo[];
  onClose: () => void;
}) {
  const [name, setName] = useState(role?.name ?? "");
  const [perms, setPerms] = useState<Set<string>>(new Set(role?.permissions ?? []));
  const [saving, setSaving] = useState(false);
  const isSystem = role?.is_system ?? false;

  // agrupa o catálogo por área, mantendo a ordem de aparição
  const groups: { name: string; items: PermissionInfo[] }[] = [];
  for (const p of catalog) {
    let g = groups.find((x) => x.name === p.group);
    if (!g) {
      g = { name: p.group, items: [] };
      groups.push(g);
    }
    g.items.push(p);
  }

  function toggle(key: string) {
    setPerms((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function save() {
    if (name.trim().length < 2) {
      toast.error("Informe um nome para o perfil.");
      return;
    }
    setSaving(true);
    try {
      if (role) {
        await api.updateRole(role.id, { name: name.trim(), permissions: [...perms] });
      } else {
        await api.createRole(name.trim(), [...perms]);
      }
      await mutate("roles");
      toast.success(role ? "Perfil atualizado." : "Perfil criado.");
      onClose();
    } catch (err) {
      toast.error(errMessage(err, "Falha ao salvar perfil."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>{role ? `Editar: ${role.name}` : "Novo perfil"}</DialogTitle>
          <DialogDescription>
            {isSystem
              ? "Perfil de sistema: nome fixo, permissões editáveis."
              : "Defina o nome e marque as permissões."}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="role-name">Nome do perfil</Label>
            <Input
              id="role-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={isSystem}
              placeholder="Ex.: Operador de logística"
            />
          </div>
          <div className="space-y-4">
            {groups.map((g) => (
              <div key={g.name}>
                <div className="mb-1.5 text-[11px] uppercase tracking-[0.14em] text-gold">
                  {g.name}
                </div>
                <div className="grid gap-1.5">
                  {g.items.map((p) => (
                    <label
                      key={p.key}
                      className="flex cursor-pointer items-center gap-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        className="size-4 accent-[var(--gold)]"
                        checked={perms.has(p.key)}
                        onChange={() => toggle(p.key)}
                      />
                      {p.label}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <DialogFooter>
          <Button onClick={save} disabled={saving}>
            {saving ? <Loader2 className="size-4 animate-spin" /> : "Salvar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ----------------------------- Copiloto ----------------------------- */

const PROVIDERS: { value: string; label: string }[] = [
  { value: "auto", label: "Automático (OpenAI → Claude)" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Claude (Anthropic)" },
];

const SCOPE_BADGE: Record<string, { label: string; cls: string }> = {
  tenant: { label: "Personalizado", cls: "border-gold/40 text-gold" },
  global: { label: "Padrão global", cls: "text-muted-foreground" },
  default: { label: "Padrão de fábrica", cls: "text-muted-foreground" },
};

function CopilotoTab({ isAdmin }: { isAdmin: boolean }) {
  const { data: settings, isLoading } = useSWR(isAdmin ? "copilot-settings" : null, () =>
    api.getCopilotSettings(),
  );
  const { data: prompts } = useSWR(isAdmin ? "copilot-prompts" : null, () =>
    api.listCopilotPrompts(),
  );

  if (!isAdmin) {
    return (
      <Card className="max-w-2xl">
        <CardContent className="flex items-center gap-3 py-8 text-sm text-muted-foreground">
          <ShieldAlert className="size-5 text-warning" />
          Apenas administradores podem configurar o copiloto.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-6">
      {isLoading || !settings ? (
        <Skeleton className="h-72 w-full max-w-3xl" />
      ) : (
        <CopilotSettingsForm settings={settings} />
      )}
      {prompts ? (
        <CopilotPromptsCard prompts={prompts} />
      ) : (
        <Skeleton className="h-48 w-full max-w-3xl" />
      )}
    </div>
  );
}

function CopilotSettingsForm({ settings }: { settings: CopilotSettings }) {
  const eff = settings.effective;
  const ov = settings.override;
  const [enabled, setEnabled] = useState<boolean>(eff.enabled);
  const [provider, setProvider] = useState<string>(ov.provider ?? "auto");
  const [model, setModel] = useState(ov.model ?? "");
  const [maxTokens, setMaxTokens] = useState(ov.max_tokens?.toString() ?? "");
  const [temperature, setTemperature] = useState(ov.temperature?.toString() ?? "");
  const [maxWords, setMaxWords] = useState(ov.max_words?.toString() ?? "");
  const [rate, setRate] = useState(ov.rate_limit_per_min?.toString() ?? "");
  const [saving, setSaving] = useState(false);

  function numOrNull(s: string): number | null {
    const t = s.trim();
    if (!t) return null;
    const n = Number(t);
    return Number.isFinite(n) ? n : null;
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.updateCopilotSettings({
        enabled,
        provider,
        model: model.trim() || null,
        max_tokens: numOrNull(maxTokens),
        temperature: numOrNull(temperature),
        max_words: numOrNull(maxWords),
        rate_limit_per_min: numOrNull(rate),
      });
      await mutate("copilot-settings");
      toast.success("Configuração do copiloto salva.");
    } catch (err) {
      toast.error(errMessage(err, "Falha ao salvar a configuração."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="edge-gold-top shadow-premium max-w-3xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="size-5 text-gold" />
          Configuração do copiloto
        </CardTitle>
        <CardDescription>
          Provedor, modelo e limites. Campos em branco herdam o padrão (mostrado como dica).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={save} className="grid gap-5">
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label>Copiloto</Label>
              <Select value={enabled ? "on" : "off"} onValueChange={(v) => setEnabled(v === "on")}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="on">Ligado (usa IA)</SelectItem>
                  <SelectItem value="off">Desligado (só template)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Provedor</Label>
              <Select value={provider} onValueChange={setProvider}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PROVIDERS.map((p) => (
                    <SelectItem key={p.value} value={p.value}>
                      {p.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="cp-model">Modelo</Label>
            <Input
              id="cp-model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={`herda: ${eff.model}`}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="cp-tokens">Máx. tokens</Label>
              <Input
                id="cp-tokens"
                inputMode="numeric"
                value={maxTokens}
                onChange={(e) => setMaxTokens(e.target.value)}
                placeholder={`herda: ${eff.max_tokens}`}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="cp-temp">Temperatura (0–2)</Label>
              <Input
                id="cp-temp"
                inputMode="decimal"
                value={temperature}
                onChange={(e) => setTemperature(e.target.value)}
                placeholder={eff.temperature != null ? `herda: ${eff.temperature}` : "padrão do modelo"}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="cp-words">Máx. palavras da resposta</Label>
              <Input
                id="cp-words"
                inputMode="numeric"
                value={maxWords}
                onChange={(e) => setMaxWords(e.target.value)}
                placeholder={`herda: ${eff.max_words}`}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="cp-rate">Limite por minuto (por empresa)</Label>
              <Input
                id="cp-rate"
                inputMode="numeric"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
                placeholder={`herda: ${eff.rate_limit_per_min}`}
              />
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            Segurança sempre ativa (não editável): redação de PII/LGPD e trava anti-alucinação de
            valor de frete.
          </p>

          <Separator />
          <div className="flex justify-end">
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
              Salvar
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function CopilotPromptsCard({ prompts }: { prompts: CopilotPromptItem[] }) {
  const [editing, setEditing] = useState<CopilotPromptItem | null>(null);
  const [resetting, setResetting] = useState<string | null>(null);

  async function reset(key: string) {
    setResetting(key);
    try {
      await api.resetCopilotPrompt(key);
      await mutate("copilot-prompts");
      toast.success("Prompt restaurado ao padrão.");
    } catch (err) {
      toast.error(errMessage(err, "Falha ao restaurar."));
    } finally {
      setResetting(null);
    }
  }

  return (
    <Card className="shadow-premium max-w-3xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Pencil className="size-5 text-gold" />
          Prompts do copiloto
        </CardTitle>
        <CardDescription>
          Edite o texto que instrui a IA em cada fluxo. Templates Jinja — mantenha as variáveis
          entre chaves.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {prompts.map((p) => {
          const badge = SCOPE_BADGE[p.scope] ?? SCOPE_BADGE.default;
          return (
            <div
              key={p.key}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-secondary/30 p-4"
            >
              <div className="min-w-0">
                <div className="font-medium">{p.label}</div>
                <div className="mt-1 flex items-center gap-2">
                  <Badge variant="outline" className={badge.cls}>
                    {badge.label}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {p.content.length} caracteres
                  </span>
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setEditing(p)}>
                  <Pencil className="size-4" />
                  Editar
                </Button>
                {p.is_override && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={resetting === p.key}
                    onClick={() => reset(p.key)}
                  >
                    {resetting === p.key ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <RotateCcw className="size-4" />
                    )}
                    Restaurar
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </CardContent>
      <PromptEditDialog prompt={editing} onClose={() => setEditing(null)} />
    </Card>
  );
}

function PromptEditDialog({
  prompt,
  onClose,
}: {
  prompt: CopilotPromptItem | null;
  onClose: () => void;
}) {
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setContent(prompt?.content ?? "");
  }, [prompt?.key, prompt?.content]);

  async function save() {
    if (!prompt) return;
    if (!content.trim()) {
      toast.error("O prompt não pode ficar vazio.");
      return;
    }
    setSaving(true);
    try {
      await api.saveCopilotPrompt(prompt.key, content);
      await mutate("copilot-prompts");
      toast.success("Prompt salvo.");
      onClose();
    } catch (err) {
      toast.error(errMessage(err, "Falha ao salvar o prompt."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={!!prompt} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{prompt?.label}</DialogTitle>
          <DialogDescription>
            Texto que instrui a IA. Preserve as variáveis Jinja (ex.: {"{{ origem }}"},{" "}
            {"{{ frete }}"}) — elas são preenchidas com os dados da predição.
          </DialogDescription>
        </DialogHeader>
        <Textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="min-h-[320px] font-mono text-xs"
          spellCheck={false}
        />
        <DialogFooter className="gap-2">
          <Button
            variant="ghost"
            onClick={() => setContent(prompt?.default ?? "")}
            disabled={saving}
          >
            <RotateCcw className="size-4" />
            Carregar padrão
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
            Salvar prompt
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ----------------------------- Page ----------------------------- */

export default function ConfiguracoesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [tab, setTab] = useState("perfil");

  return (
    <>
      <PageHeader title="Configurações" subtitle="Perfil, empresa, usuários e copiloto" />

      <Tabs value={tab} onValueChange={setTab} className="w-full">
        <TabsList className="mb-6">
          <TabsTrigger value="perfil">
            <UserCog className="size-4" />
            Perfil
          </TabsTrigger>
          <TabsTrigger value="empresa">
            <Building2 className="size-4" />
            Empresa
          </TabsTrigger>
          <TabsTrigger value="usuarios">
            {isAdmin ? <Users2 className="size-4" /> : <ShieldAlert className="size-4" />}
            Usuários
          </TabsTrigger>
          {isAdmin && (
            <TabsTrigger value="perfis">
              <KeyRound className="size-4" />
              Perfis
            </TabsTrigger>
          )}
          {isAdmin && (
            <TabsTrigger value="copiloto">
              <Bot className="size-4" />
              Copiloto
            </TabsTrigger>
          )}
        </TabsList>

        {tab === "perfil" && <PerfilTab />}
        {tab === "empresa" && <EmpresaTab isAdmin={!!isAdmin} />}
        {tab === "usuarios" && (
          <UsuariosTab isAdmin={!!isAdmin} currentUserId={user?.user_id} />
        )}
        {tab === "perfis" && <PerfisTab isAdmin={!!isAdmin} />}
        {tab === "copiloto" && <CopilotoTab isAdmin={!!isAdmin} />}
      </Tabs>
    </>
  );
}
