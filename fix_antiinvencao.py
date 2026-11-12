import shutil, datetime

p = "src/prompt/prompt_builder.py"
bak = p + ".bak_antiinvencao_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy2(p, bak)

L = open(p, encoding="utf-8").readlines()
idx_a = [i for i, l in enumerate(L) if "Se os resultados forem vagos" in l]
idx_b = [i for i, l in enumerate(L) if "combine-os com seu conhecimento" in l]

if len(idx_a) != 1 or len(idx_b) != 1 or idx_b[0] != idx_a[0] + 1:
    print("ABORTADO: padrao inesperado", idx_a, idx_b)
    raise SystemExit(1)

i = idx_a[0]
ind = L[i][: len(L[i]) - len(L[i].lstrip())]
novo = [
    ind + '"Se a pergunta pede um numero e nenhum numero aparecer nos dados abaixo, "\n',
    ind + '"diga claramente que nao encontrou o valor exato agora. "\n',
    ind + '"NUNCA estime, arredonde ou invente valores.\\n"\n',
]
L[i:i + 2] = novo
open(p, "w", encoding="utf-8").writelines(L)

print("OK - backup:", bak)
print("Linhas alteradas:", i + 1, "a", i + len(novo))