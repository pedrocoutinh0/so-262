#!/usr/bin/env python3
"""Executa os testes do Algoritmo do Banqueiro separadamente. Aluno: Pedro Coutinho"""
import sys, io, contextlib, datetime, platform
from bankers_algorithm import BankersAlgorithm

ALUNO = "Pedro Coutinho"

def novo_banqueiro():
    return BankersAlgorithm(
        ["P0", "P1", "P2", "P3", "P4"], [10, 5, 7],
        [[0,1,0],[2,0,0],[3,0,2],[2,1,1],[0,0,2]],
        [[7,5,3],[3,2,2],[9,0,2],[2,2,2],[4,3,3]])

def cabecalho(titulo):
    print("*" * 70)
    print(f"Aluno: {ALUNO}")
    print(f"Atividade 07 - Algoritmo do Banqueiro | {titulo}")
    print(f"Data/hora: {datetime.datetime.now():%d/%m/%Y %H:%M:%S} | Python {platform.python_version()}")
    print("*" * 70)

def teste1():
    cabecalho("Teste 1 - Estado inicial e verificacao de seguranca")
    b = novo_banqueiro(); b.display_state(); b.is_safe_state(verbose=True)

def teste2():
    cabecalho("Teste 2 - P1 solicita [1, 0, 2]")
    b = novo_banqueiro(); b.request_resources(1, [1, 0, 2]); b.display_state()

def teste3():
    cabecalho("Teste 3 - P4 solicita [3, 3, 0] (apos o Teste 2)")
    b = novo_banqueiro()
    with contextlib.redirect_stdout(io.StringIO()):
        b.request_resources(1, [1, 0, 2])  # reaplica o Teste 2 (saida omitida)
    print(">>> Estado de partida: apos a concessao do Teste 2 (Disponivel = [2, 3, 0])")
    b.request_resources(4, [3, 3, 0]); b.display_state()

if __name__ == "__main__":
    {"1": teste1, "2": teste2, "3": teste3}[sys.argv[1]]()
