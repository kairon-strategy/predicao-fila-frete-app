"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import {
  Plus,
  Pencil,
  Trash2,
  MapPin,
  Package,
  Route as RouteIcon,
  Loader2,
  Lock,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { api, ApiError, type RouteRecord } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { brl, num } from "@/lib/format";
import { cn } from "@/lib/utils";

const PRODUTOS = ["ureia", "MAP", "KCl", "NPK", "algodão", "soja", "milho"];

type FormState = {
  origem: string;
  destino: string;
  produto: string;
  distancia_km: string;
  corredor: string;
  piso_antt_r_per_ton: string;
};

const EMPTY_FORM: FormState = {
  origem: "",
  destino: "",
  produto: "ureia",
  distancia_km: "",
  corredor: "",
  piso_antt_r_per_ton: "",
};

function rowToForm(r: RouteRecord): FormState {
  return {
    origem: r.origem,
    destino: r.destino,
    produto: r.produto,
    distancia_km: String(r.distancia_km),
    corredor: r.corredor ?? "",
    piso_antt_r_per_ton:
      r.piso_antt_r_per_ton != null ? String(r.piso_antt_r_per_ton) : "",
  };
}

function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 403) return "Seu papel não permite editar rotas";
    return err.message;
  }
  return "Erro";
}

export default function RotasPage() {
  const { user } = useAuth();
  const canWrite = user?.role !== "viewer";

  const { data, error, isLoading } = useSWR("routes-manage", () =>
    api.listRoutesManage(),
  );

  // edit/create dialog
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<RouteRecord | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  // delete dialog
  const [deleting, setDeleting] = useState<RouteRecord | null>(null);
  const [removing, setRemoving] = useState(false);

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setEditOpen(true);
  }

  function openEdit(r: RouteRecord) {
    setEditing(r);
    setForm(rowToForm(r));
    setEditOpen(true);
  }

  function setField<K extends keyof FormState>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite) return;

    const origem = form.origem.trim();
    const destino = form.destino.trim();
    const distancia = Number(form.distancia_km);

    if (!origem || !destino || !form.produto) {
      toast.error("Preencha origem, destino e produto");
      return;
    }
    if (!Number.isFinite(distancia) || distancia <= 0) {
      toast.error("Distância deve ser maior que zero");
      return;
    }

    const corredor = form.corredor.trim();
    const pisoRaw = form.piso_antt_r_per_ton.trim();
    const piso = pisoRaw === "" ? null : Number(pisoRaw);
    if (piso != null && !Number.isFinite(piso)) {
      toast.error("Piso ANTT inválido");
      return;
    }

    const body = {
      origem,
      destino,
      produto: form.produto,
      distancia_km: distancia,
      corredor: corredor === "" ? null : corredor,
      piso_antt_r_per_ton: piso,
    };

    setSaving(true);
    try {
      if (editing) {
        await api.updateRoute(editing.route_id, body);
        toast.success("Rota atualizada");
      } else {
        await api.createRoute(body);
        toast.success("Rota criada");
      }
      await mutate("routes-manage");
      setEditOpen(false);
    } catch (err) {
      toast.error(friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleting || !canWrite) return;
    setRemoving(true);
    try {
      await api.deleteRoute(deleting.route_id);
      toast.success("Rota excluída");
      await mutate("routes-manage");
      setDeleting(null);
    } catch (err) {
      toast.error(friendlyError(err));
    } finally {
      setRemoving(false);
    }
  }

  const routes = data ?? [];
  const colCount = canWrite ? 6 : 5;

  return (
    <div>
      <PageHeader
        title="Rotas & corredores"
        subtitle="Cadastro das rotas monitoradas do seu tenant"
      >
        {canWrite ? (
          <Button onClick={openCreate} className="font-medium">
            <Plus className="size-4" />
            Nova rota
          </Button>
        ) : (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Lock className="size-3.5" />
            Somente leitura (papel viewer)
          </span>
        )}
      </PageHeader>

      <Card className="edge-gold-top shadow-premium overflow-hidden">
        <CardContent className="p-0">
          {isLoading ? (
            <LoadingTable canWrite={canWrite} colCount={colCount} />
          ) : error ? (
            <ErrorState message={friendlyError(error)} />
          ) : routes.length === 0 ? (
            <EmptyState canWrite={canWrite} onCreate={openCreate} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="pl-5">Rota</TableHead>
                  <TableHead>Produto</TableHead>
                  <TableHead className="text-right">Distância</TableHead>
                  <TableHead>Corredor</TableHead>
                  <TableHead className="text-right">Piso ANTT</TableHead>
                  {canWrite && (
                    <TableHead className="pr-5 text-right">Ações</TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {routes.map((r) => (
                  <TableRow key={r.route_id} className="group">
                    <TableCell className="pl-5">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-foreground">
                          {r.origem}
                        </span>
                        <RouteIcon className="size-3.5 text-gold" />
                        <span className="text-muted-foreground">{r.destino}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="font-medium">
                        {r.produto}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-foreground">
                      {num(r.distancia_km, 0)} km
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {r.corredor ?? "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-foreground">
                      {r.piso_antt_r_per_ton != null
                        ? brl(r.piso_antt_r_per_ton)
                        : "—"}
                    </TableCell>
                    {canWrite && (
                      <TableCell className="pr-5">
                        <div className="flex items-center justify-end gap-1 opacity-70 transition-opacity group-hover:opacity-100">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => openEdit(r)}
                            aria-label={`Editar rota ${r.origem} → ${r.destino}`}
                          >
                            <Pencil className="size-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => setDeleting(r)}
                            aria-label={`Excluir rota ${r.origem} → ${r.destino}`}
                            className="text-muted-foreground hover:text-destructive"
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* CREATE / EDIT ------------------------------------------------------ */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Editar rota" : "Nova rota"}</DialogTitle>
            <DialogDescription>
              {editing
                ? "Atualize os dados da rota monitorada."
                : "Cadastre uma nova rota para o seu tenant."}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="origem" className="flex items-center gap-1.5">
                  <MapPin className="size-3.5 text-muted-foreground" />
                  Origem
                </Label>
                <Input
                  id="origem"
                  value={form.origem}
                  onChange={(e) => setField("origem", e.target.value)}
                  placeholder="Cidade-UF"
                  autoFocus
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="destino" className="flex items-center gap-1.5">
                  <MapPin className="size-3.5 text-muted-foreground" />
                  Destino
                </Label>
                <Input
                  id="destino"
                  value={form.destino}
                  onChange={(e) => setField("destino", e.target.value)}
                  placeholder="Cidade-UF"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label className="flex items-center gap-1.5">
                  <Package className="size-3.5 text-muted-foreground" />
                  Produto
                </Label>
                <Select
                  value={form.produto}
                  onValueChange={(v) => setField("produto", v)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Selecione" />
                  </SelectTrigger>
                  <SelectContent>
                    {PRODUTOS.map((p) => (
                      <SelectItem key={p} value={p}>
                        {p}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="distancia">Distância (km)</Label>
                <Input
                  id="distancia"
                  type="number"
                  min={0}
                  step="1"
                  value={form.distancia_km}
                  onChange={(e) => setField("distancia_km", e.target.value)}
                  placeholder="0"
                  className="tabular-nums"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="corredor">
                  Corredor{" "}
                  <span className="text-muted-foreground">(opcional)</span>
                </Label>
                <Input
                  id="corredor"
                  value={form.corredor}
                  onChange={(e) => setField("corredor", e.target.value)}
                  placeholder="—"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="piso">
                  Piso ANTT{" "}
                  <span className="text-muted-foreground">(R$/t, opcional)</span>
                </Label>
                <Input
                  id="piso"
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.piso_antt_r_per_ton}
                  onChange={(e) =>
                    setField("piso_antt_r_per_ton", e.target.value)
                  }
                  placeholder="—"
                  className="tabular-nums"
                />
              </div>
            </div>

            <Separator className="bg-border" />

            <DialogFooter className="mx-0 mb-0 border-0 bg-transparent p-0">
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditOpen(false)}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={saving} className="font-medium">
                {saving && <Loader2 className="size-4 animate-spin" />}
                {editing ? "Salvar alterações" : "Criar rota"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* DELETE CONFIRM ---------------------------------------------------- */}
      <Dialog
        open={deleting != null}
        onOpenChange={(open) => !open && setDeleting(null)}
      >
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="size-4 text-destructive" />
              Excluir rota
            </DialogTitle>
            <DialogDescription>
              {deleting ? (
                <>
                  Excluir a rota{" "}
                  <span className="font-medium text-foreground">
                    {deleting.origem} → {deleting.destino}
                  </span>
                  ? Esta ação não pode ser desfeita.
                </>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mx-0 mb-0 border-0 bg-transparent p-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => setDeleting(null)}
            >
              Cancelar
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={removing}
              onClick={handleDelete}
              className="font-medium"
            >
              {removing && <Loader2 className="size-4 animate-spin" />}
              Excluir
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function LoadingTable({
  canWrite,
  colCount,
}: {
  canWrite: boolean;
  colCount: number;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="pl-5">Rota</TableHead>
          <TableHead>Produto</TableHead>
          <TableHead className="text-right">Distância</TableHead>
          <TableHead>Corredor</TableHead>
          <TableHead className="text-right">Piso ANTT</TableHead>
          {canWrite && (
            <TableHead className="pr-5 text-right">Ações</TableHead>
          )}
        </TableRow>
      </TableHeader>
      <TableBody>
        {Array.from({ length: 5 }).map((_, i) => (
          <TableRow key={i} className="hover:bg-transparent">
            {Array.from({ length: colCount }).map((__, j) => (
              <TableCell key={j} className={cn(j === 0 && "pl-5")}>
                <Skeleton className="h-4 w-full max-w-[140px]" />
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function EmptyState({
  canWrite,
  onCreate,
}: {
  canWrite: boolean;
  onCreate: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-4 px-6 py-20 text-center">
      <div className="flex size-16 items-center justify-center rounded-2xl bg-secondary">
        <RouteIcon className="size-7 text-gold" />
      </div>
      <div className="max-w-xs space-y-1">
        <p className="text-lg font-medium text-foreground">
          Nenhuma rota cadastrada
        </p>
        <p className="text-sm text-muted-foreground">
          {canWrite
            ? "Cadastre a primeira rota para começar a monitorar fretes."
            : "Nenhuma rota disponível para visualização."}
        </p>
      </div>
      {canWrite && (
        <Button onClick={onCreate} className="font-medium">
          <Plus className="size-4" />
          Criar primeira rota
        </Button>
      )}
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-20 text-center">
      <AlertTriangle className="size-7 text-destructive" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
