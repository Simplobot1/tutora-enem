# Provas ENEM

Coloque os PDFs das provas ENEM aqui.

## Como adicionar um PDF:

1. Baixe o PDF do OneDrive em seu computador
2. Copie para esta pasta: `materiais/provas/`
3. Execute:
   ```bash
   cd /root/projetos/tutora
   python scripts/ingest_enem.py --file materiais/provas/NOME_DO_SEU_PDF.pdf --dry-run
   ```

## Exemplo:
```bash
python scripts/ingest_enem.py --file materiais/provas/enem2024.pdf --dry-run
```

**Teste rápido antes de inserir no banco (recomendado).**
