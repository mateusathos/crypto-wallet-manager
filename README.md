# Crypto Portfolio Manager

Aplicação web para gestão de portfólio de criptomoedas, com autenticação por sessão, múltiplos portfólios, controle de compras e vendas, cálculo de performance e atualização de preços via CoinGecko.

O projeto também expõe uma API JSON para consumo por uma versão mobile em Flutter.

Link da aplicação: https://athos-crypto-wallet-manager.vercel.app/

## Visão geral

O Crypto Portfolio Manager permite que usuários acompanhem suas carteiras de criptoativos de forma organizada. A aplicação calcula custo médio, valor atual, lucro/prejuízo realizado e não realizado, além de consolidar transações por portfólio.

O sistema foi pensado em duas interfaces sobre a mesma base de domínio:

- uma versão web renderizada com Flask/Jinja;
- uma API JSON usada pela versão mobile.

## Funcionalidades

- Cadastro, login e logout com sessão persistente
- Criação de múltiplos portfólios com ícones Lucide selecionáveis
- Abertura automática do portfólio recém-criado
- Registro, edição e exclusão de transações de compra e venda
- Seleção de ativo antes da criação da transação, com modal de busca por criptomoeda
- Cálculo de custo médio, lucro/prejuízo realizado, não realizado e rentabilidade percentual
- Listagem de criptomoedas com busca, ordenação por moeda, preço, 24h e market cap
- Atualização automática de preços na tela de criptomoedas por polling
- Modal de detalhes de criptomoeda
- API JSON para autenticação, portfólios, transações e criptomoedas
- Endpoint protegido para atualização de preços via scheduler externo

## Stack

- Python 3.10+
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- SQLAlchemy + `sqlalchemy-libsql`
- Turso/libSQL
- CoinGecko API
- Jinja2
- Tailwind CSS
- Lucide Icons
- Vercel
- unittest

## Arquitetura

O backend concentra as regras de negócio e expõe duas superfícies:

- rotas HTML para a aplicação web;
- rotas `/api/...` em JSON para o app mobile.

Essa divisão permite reaproveitar as mesmas regras de cálculo entre web e mobile, evitando duplicação de lógica no Flutter.

Estrutura principal:

```text
api/
  index.py              # entrypoint serverless para Vercel

routes/
  auth.py               # autenticação web
  portfolio.py          # portfólios/transações web
  criptomoedas.py       # listagem web de criptomoedas
  cron.py               # endpoint de atualização de preços
  api_auth.py           # autenticação JSON
  api_cryptocurrencies.py
  api_portfolios.py
  api_helpers.py

services/
  portfolio_service.py  # cálculos de carteira
  coingecko_service.py  # integração com preços
  price_update_service.py
  portfolio_icons.py    # catálogo/normalização de ícones
  turso_service.py      # utilitários de integração com Turso

models.py              # modelos SQLAlchemy
app.py                 # criação da aplicação Flask
config.py              # configuração por ambiente
tests/                 # testes automatizados
```

## Decisões técnicas

- O banco usa Turso/libSQL como fonte única da verdade.
- O backend mantém a responsabilidade sobre regras sensíveis, como autenticação, ownership de portfólios e validação de venda maior que a quantidade disponível.
- A API mobile não acessa o banco diretamente; o fluxo correto é `Flutter -> Flask API -> Turso`.
- Os cálculos de portfólio ficam em `services/portfolio_service.py`, separados das rotas, para facilitar testes e reuso.
- As operações de leitura e escrita usam o Turso remoto via SQLAlchemy.
- A interface web usa polling para atualizar preços da listagem de criptomoedas sem recarregar a página.
- A atualização de preços é disparada por um endpoint protegido, pensado para scheduler externo.
- O deploy web usa Vercel com entrypoint serverless em `api/index.py`.

## Atualizações recentes

Mudanças incorporadas nas últimas 24 horas:

- Turso passou a ser o banco principal da aplicação
- Fluxos de CRUD e navegação do portfólio foram refinados para preservar o portfólio selecionado
- Interface padronizada com Lucide Icons
- Seleção de ativo antes de criar transação, com modal dedicado e busca
- Listagem de criptomoedas com ordenação por moeda, preço, 24h e market cap
- Flash messages em overlay, sem empurrar o layout
- Indicadores visuais de carregamento em operações de CRUD

## API mobile

Base local:

```text
http://127.0.0.1:5000
```

As rotas autenticadas usam sessão/cookie do Flask. Em clientes como Postman, Insomnia ou Thunder Client, faça login primeiro e mantenha os cookies habilitados nas próximas requisições.

Use:

```http
Content-Type: application/json
```

### Autenticação

```http
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

Exemplo de login:

```json
{
  "email": "teste@example.com",
  "password": "123456"
}
```

Resposta:

```json
{
  "user": {
    "id": 1,
    "email": "teste@example.com"
  }
}
```

### Criptomoedas

```http
GET /api/cryptocurrencies
```

Resposta resumida:

```json
{
  "cryptocurrencies": [
    {
      "id": 1,
      "name": "Bitcoin",
      "symbol": "BTC",
      "coingecko_id": "bitcoin",
      "image_url": "https://...",
      "current_price": 350000.0,
      "current_marketcap": 6900000000000.0,
      "price_change_percentage_24h": 1.25,
      "last_updated": "2026-05-23T13:30:00",
      "last_updated_formatted": "23/05/2026 10:30:00"
    }
  ]
}
```

### Portfólios

```http
GET    /api/portfolios
POST   /api/portfolios
PATCH  /api/portfolios/<portfolio_id>
DELETE /api/portfolios/<portfolio_id>
```

Criar portfólio:

```json
{
  "name": "Carteira Principal",
  "icon": "wallet"
}
```

Resposta resumida:

```json
{
  "portfolio": {
    "id": 1,
    "name": "Carteira Principal",
    "icon": "wallet",
    "summary": {
      "actives": [],
      "cost": 0.0,
      "value": 0.0,
      "unrealized_profit": 0.0,
      "realized_profit": 0.0,
      "profit_total": 0.0,
      "profit_percentage": 0.0,
      "invested_base": 0.0
    },
    "transactions": []
  }
}
```

### Transações

```http
POST   /api/portfolios/transactions
PATCH  /api/portfolios/transactions/<transaction_id>
DELETE /api/portfolios/transactions/<transaction_id>
```

Criar transação:

```json
{
  "portfolio_id": 1,
  "cryptocurrency_id": 1,
  "type": "compra",
  "quantity": 0.05,
  "price": 350000,
  "date": "2026-05-23"
}
```

`type` aceita:

- `compra`
- `venda`

Para vendas, a API valida se há quantidade disponível do ativo no portfólio.

## Rodar localmente

Pré-requisitos:

- Python 3.10+
- Banco configurado no Turso

Crie um `.env` com base em `.env.example`:

```env
TURSO_DATABASE_URL=libsql://your-database.turso.io
TURSO_AUTH_TOKEN=your_turso_token
SECRET_KEY=replace_with_a_strong_random_secret
CRON_SECRET=replace_with_a_strong_random_secret
COINGECKO_API_KEY=
```

Instale as dependências e execute:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Aplicação local:

```text
http://127.0.0.1:5000
```

## Atualização de preços

A atualização de preços é feita por endpoint protegido:

```http
GET /api/cron/update-prices
```

Quando `CRON_SECRET` está configurado, envie:

```http
Authorization: Bearer <CRON_SECRET>
```

Esse endpoint atualiza os dados das criptomoedas via CoinGecko e persiste o resultado no Turso. O uso esperado é chamar esse endpoint por um scheduler externo.

Na interface web de criptomoedas, os preços também são atualizados periodicamente por polling em:

```http
GET /api/cryptocurrencies
```

O polling atualiza os valores exibidos sem precisar dar refresh na página.

## Sessão e segurança

- A sessão do Flask é permanente por padrão e usa `SESSION_LIFETIME_HOURS`, que hoje cai em `12` horas quando a variável não é definida.
- Formulários HTML protegidos usam token CSRF de sessão.
- As rotas `/api/...` continuam autenticadas por sessão/cookie quando exigem login.

## Testes

```bash
python -m unittest discover -s tests
```

Atualmente a suíte cobre:

- regras de cálculo do portfólio
- parsing de datas da CoinGecko
- atualização de preços
- helpers da rota de criptomoedas
- normalização de ícones de portfólio
- configuração de conexão com Turso

## Próximos passos

- Evoluir a autenticação mobile de sessão/cookie para token próprio
- Adicionar testes automatizados para as rotas `/api/...`
- Implementar paginação/filtros para histórico de transações
- Finalizar a integração com o app Flutter
