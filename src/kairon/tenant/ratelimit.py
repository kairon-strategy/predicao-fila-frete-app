"""Rate limit simples e in-memory para o login (anti brute-force).

MVP single-instance: janela deslizante por chave (IP+email) em memória do
processo. NÃO sobrevive a restart nem se replica entre workers — suficiente para
frear brute-force no MVP. Em produção multi-réplica, trocar por um store
compartilhado (ex.: Postgres/Redis) sem mudar a interface `hit()`.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

# chave -> timestamps (segundos) das tentativas dentro da janela.
_attempts: dict[str, deque[float]] = defaultdict(deque)


def hit(key: str, *, max_attempts: int, window_seconds: int) -> bool:
    """Registra uma tentativa. Retorna True se DENTRO do limite, False se estourou.

    Chame a cada tentativa de login. Ao retornar False, responda 429.
    """
    now = time.monotonic()
    q = _attempts[key]
    cutoff = now - window_seconds
    while q and q[0] < cutoff:
        q.popleft()
    q.append(now)
    return len(q) <= max_attempts


def reset(key: str) -> None:
    """Zera o contador (ex.: após login bem-sucedido)."""
    _attempts.pop(key, None)
