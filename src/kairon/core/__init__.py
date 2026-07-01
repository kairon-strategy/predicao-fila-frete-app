"""Core cross-cutting: config, logging, database, events, exceptions.

Este é o ÚNICO pacote que os bounded contexts podem importar em comum.
Contexts nunca importam uns aos outros diretamente (ver ADR-008).
"""
