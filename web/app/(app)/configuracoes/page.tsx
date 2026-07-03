"use client";

import {
  Building2,
  Loader2,
  Lock,
  Plus,
  Save,
  ShieldAlert,
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
  type TenantResponse,
  type UserResponse,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const ROLES = ["admin", "analyst", "viewer"] as const;
type Role = (typeof ROLES)[number];

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
  const [role, setRole] = useState<Role>("viewer");
  const [saving, setSaving] = useState(false);

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
            <Label htmlFor="novo-papel">Papel</Label>
            <Select value={role} onValueChange={(v) => setRole(v as Role)}>
              <SelectTrigger id="novo-papel" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => (
                  <SelectItem key={r} value={r}>
                    {ROLE_LABEL[r]}
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
  const isSelf = u.id === currentUserId;

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
          <SelectTrigger className="h-8 w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ROLES.map((r) => (
              <SelectItem key={r} value={r}>
                {ROLE_LABEL[r]}
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

/* ----------------------------- Page ----------------------------- */

export default function ConfiguracoesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [tab, setTab] = useState("perfil");

  return (
    <>
      <PageHeader title="Configurações" subtitle="Perfil, empresa e usuários" />

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
        </TabsList>

        {tab === "perfil" && <PerfilTab />}
        {tab === "empresa" && <EmpresaTab isAdmin={!!isAdmin} />}
        {tab === "usuarios" && (
          <UsuariosTab isAdmin={!!isAdmin} currentUserId={user?.user_id} />
        )}
      </Tabs>
    </>
  );
}
