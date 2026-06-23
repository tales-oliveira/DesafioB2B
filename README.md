# Desafio da B2BFlow

Sistema desenvolvido em **Python**, integrado ao **Supabase** e à **Z-API**.

A aplicação consulta contatos e telefones cadastrados no Supabase e envia, pelo WhatsApp, a seguinte mensagem personalizada:

```text
Olá, <nome_contato> tudo bem com você?
```

## Fluxo da aplicação

1. O Python carrega as credenciais armazenadas no arquivo `.env`.
2. A aplicação conecta-se ao Supabase.
3. O Supabase retorna o contato e seus telefones ativos.
4. O Python normaliza cada telefone para o formato `DDI + DDD + número`.
5. A mensagem é personalizada com o nome do contato.
6. O Python envia a requisição para a Z-API.
7. A Z-API utiliza a instância conectada ao WhatsApp para enviar a mensagem.
8. O terminal informa os envios aceitos e as eventuais falhas.

```text
Supabase
   │
   │ contatos e telefones
   ▼
main.py
   │
   │ requisição HTTP
   ▼
Z-API
   │
   │ instância conectada
   ▼
WhatsApp
```

## Estrutura de arquivos

Todos os arquivos ficam na mesma pasta:

```text
B2B/
├── main.py
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

## Banco de dados no Supabase

O banco possui duas tabelas:

- `contatos`: guarda o identificador e o nome do contato;
- `telefones`: guarda os telefones associados ao contato.

Um contato pode possuir vários telefones. A aplicação consulta no máximo três telefones ativos por contato.

### Códigos SQL

```sql
CREATE TABLE IF NOT EXISTS public.contatos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome_contato TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS public.telefones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contato_id UUID NOT NULL
        REFERENCES public.contatos(id)
        ON DELETE CASCADE,
    telefone TEXT NOT NULL UNIQUE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT ON TABLE public.contatos, public.telefones TO service_role;

INSERT INTO public.contatos (nome_contato)
VALUES ('NOMECONTATO')
ON CONFLICT (nome_contato) DO NOTHING;

INSERT INTO public.telefones (contato_id, telefone)
SELECT
    id,
    'TELEFONE'
FROM public.contatos
WHERE nome_contato = 'NOMECONTATO'
ON CONFLICT (telefone) DO NOTHING;
```

Antes de executar, substitua:

- `NOMECONTATO` pelo nome do contato;
- `TELEFONE` pelo número no formato `DDI + DDD + número`, somente com dígitos, tudo junto.


Para cadastrar outro telefone para o mesmo contato, repita apenas o último `INSERT` com o novo número.

## Variáveis de ambiente

Crie um arquivo chamado `.env` na mesma pasta do `main.py`.

```env
# Supabase
SUPABASE_URL=https://SEU-PROJETO.supabase.co
SUPABASE_KEY=SUA_CHAVE_SUPABASE
SUPABASE_TABLE=contatos

# Z-API
ZAPI_INSTANCE_ID=SUA_INSTANCE_ID
ZAPI_INSTANCE_TOKEN=SEU_INSTANCE_TOKEN
ZAPI_CLIENT_TOKEN=SEU_CLIENT_TOKEN

# Configurações
DEFAULT_COUNTRY_CODE=55
MAX_CONTACTS=3
```

### Credenciais do Supabase

No painel do projeto:

1. Acesse **Integrations → Data API**.
2. Copie a URL do projeto para `SUPABASE_URL`.
3. Acesse **Settings → API Keys**.
4. Copie uma **Secret key**, normalmente iniciada por `sb_secret_`.
5. Caso o projeto use chaves legadas, copie a chave `service_role`.
6. Coloque a chave em `SUPABASE_KEY`.

A Secret key ou `service_role` deve ser usada somente no backend e nunca deve ser publicada.

### Credenciais da Z-API

No painel da Z-API:

1. Crie ou abra uma instância.
2. Clique em **Editar** na instância.
3. Copie o ID para `ZAPI_INSTANCE_ID`.
4. Copie o token da instância para `ZAPI_INSTANCE_TOKEN`.
5. Acesse **Segurança**.
6. Abra **Token de segurança da conta**.
7. Crie ou copie o token para `ZAPI_CLIENT_TOKEN`.
8. Conecte a instância ao WhatsApp pelo QR Code.

A instância precisa estar conectada antes do envio.

## Dependências

### Arquivo `requirements.txt`

```text
supabase==2.18.1
python-dotenv==1.0.1
requests==2.32.4
```

Instale as dependências:

```powershell
python -m pip install -r requirements.txt
```

## Como executar

Abra o terminal na pasta do projeto.

### Execução completa

```powershell
python main.py 
```


