# Crypto Portfolio Manager

Aplicação Flask para gestão de portfólio de criptomoedas, com autenticação, controle de transações (compra/venda), cálculo de performance e atualização de preços via CoinGecko.

O projeto está preparado para usar **Turso (libSQL)** e para deploy na **Vercel**, incluindo cron automático para atualização de preços a cada 3 horas.

## Funcionalidades

- Cadastro/login de usuários
- Criação e gestão de múltiplos portfólios
- Registro, edição e exclusão de transações
- Cálculo de:
  - valor atual
  - custo médio (média ponderada)
  - lucro/prejuízo realizado e não realizado
  - lucro percentual
- Listagem de criptomoedas com dados de mercado
- Endpoint de cron para atualização automática de preços

## Stack

- Python + Flask
- Flask-SQLAlchemy + Flask-Migrate
- Turso/libSQL
- CoinGecko API
- Jinja2 + Tailwind

## Estrutura do projeto

- `app.py`: inicialização da aplicação e registro de blueprints
- `config.py`: configuração por variáveis de ambiente
- `models.py`: modelos do banco
- `routes/`: rotas HTTP (`auth`, `portfolio`, `criptomoedas`, `cron`)
- `services/`: lógica de domínio e integrações (`coingecko`, `price_update`, `portfolio`, `turso`)
- `migrate_to_turso.py`: publicação de snapshot SQLite para o Turso
- `sync_turso.py`: reenvio manual do snapshot local para o Turso
- `vercel.json`: configuração de runtime e cron da Vercel
- `api/index.py`: entrypoint serverless para Vercel

## Pré-requisitos

- Python 3.10+
- Conta/banco no Turso

## Variáveis de ambiente

Use `.env` (base em `.env.example`):

```env
TURSO_DATABASE_URL=libsql://your-database.turso.io
TURSO_AUTH_TOKEN=your_turso_token
TURSO_LOCAL_DB_PATH=instance/app.db
SECRET_KEY=replace_with_a_strong_random_secret
CRON_SECRET=replace_with_a_strong_random_secret
COINGECKO_API_KEY=
```

## Rodar localmente

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Aplicação disponível em `http://127.0.0.1:5000`.

## Publicar snapshot para Turso

1. Se você já usa `TURSO_LOCAL_DB_PATH` como snapshot local, execute:

```bash
python migrate_to_turso.py
```

2. Se quiser publicar a partir de outro arquivo SQLite:

```bash
python migrate_to_turso.py --from-sqlite C:\caminho\seu_arquivo.db
```

3. Alinhe estado de migração local (caso tenha recriado o snapshot):

```bash
flask db stamp head
flask db upgrade
```

## Atualização de preços (cron)

Endpoint:

- `GET /api/cron/update-prices`

Com `CRON_SECRET` configurado, envie:

```http
Authorization: Bearer <CRON_SECRET>
```

## Deploy na Vercel

O projeto já está preparado para Vercel com:

- entrypoint serverless em `api/index.py`
- cron configurado em `vercel.json`:
  - `0 */3 * * *` (a cada 3 horas)
  - path `/api/cron/update-prices`

No painel da Vercel, configure as variáveis:

- `SECRET_KEY`
- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`
- `TURSO_LOCAL_DB_PATH=/tmp/app.db`
- `CRON_SECRET`
- `COINGECKO_API_KEY` (opcional)

## Testes

```bash
python -m unittest discover -s tests
```
