# Café & Cupcakes

Aplicação web Django MVT para uma cafeteria/confeitaria especializada em cafés e cupcakes. O projeto possui área do cliente, catálogo, personalização, carrinho, cupons, checkout, pedidos, pagamentos simulados, avaliações e base administrativa/relatórios.

## Stack

- Python 3.12
- Django 5.1
- PostgreSQL via `DATABASE_URL`
- Django Templates
- Tailwind CSS
- Vanilla JavaScript com ES Modules

## Estrutura

- `accounts`: usuário por e-mail, CPF, papéis, endereços e autenticação.
- `catalog`: categorias, produtos, ingredientes, alérgenos e adicionais.
- `inventory`: insumos, saldo e movimentações.
- `cart`: carrinho persistido por usuário ou sessão.
- `coupons`: cupons, validação e histórico de uso.
- `orders`: checkout, pedidos, itens e status.
- `payments`: pagamento simulado Pix/cartão tokenizado.
- `reviews`: avaliações após entrega.
- `reports`: dashboard financeiro.
- `core`: home, templates compartilhados e seed.

## Instalação

### Docker Compose (desenvolvimento local)

Requer Docker com o plugin Compose. Na raiz do projeto:

```bash
# Copie apenas se ainda não existir um arquivo .env.
cp -n .env.example .env
docker compose up -d --build
docker compose logs -f web
```

Acesse http://localhost:8001. O serviço `web` usa Python 3.12 e aguarda
o PostgreSQL ficar pronto antes de aplicar as migrações e iniciar o Django.
O banco começa vazio; para carregar os produtos e usuários demonstrativos:

```bash
docker compose exec web python manage.py seed_demo
```

Comandos úteis:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py check
docker compose exec web python manage.py test
docker compose down
```

Banco e uploads ficam nos volumes `postgres_data` e `media_data`, preservados
ao executar `docker compose down`. O SQLite e os uploads locais não são
importados automaticamente. `docker compose down -v` apaga os dados dos volumes.

No `.env`, `APP_PORT` altera a porta publicada; `POSTGRES_DB`, `POSTGRES_USER`
e `POSTGRES_PASSWORD` configuram o banco na primeira inicialização do volume.
Ao personalizar usuário e senha, utilize caracteres seguros para URLs ou
ajuste a `DATABASE_URL` no Compose com as credenciais codificadas.
O Compose define sua própria `DATABASE_URL` com o host `db`; o valor local
do `.env` continua disponível para execução fora do Docker.

Esta configuração usa o servidor de desenvolvimento do Django e publica a
aplicação apenas em `127.0.0.1`. O Compose fixa `DEBUG=True` para servir CSS,
JavaScript e uploads, independentemente do ambiente local. Para publicar em produção, configure um servidor WSGI, um proxy
para estáticos/uploads, HTTPS e segredos próprios.

O código é copiado para a imagem. Após alterar os arquivos, execute novamente
`docker compose up -d --build`.

### Ambiente Python local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure o PostgreSQL em `.env`:

```env
DATABASE_URL=postgres://postgres:postgres@localhost:5432/appcoffee
```

Para desenvolvimento rápido, remova `DATABASE_URL` e o projeto usará SQLite local.

## Execução

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 0.0.0.0:8001
```

Se o ambiente local estiver com `DEBUG=False`, use
`python manage.py runserver 0.0.0.0:8001 --insecure` para servir CSS e JavaScript.
Essa opção é exclusiva para desenvolvimento; em produção, execute `collectstatic`
e configure o servidor web para servir o diretório `staticfiles`.

## Feedback de ações

O indicador de ações é compartilhado pelas páginas. Formulários POST recebem
feedback durante o envio; personalize o botão com `data-pending-label` e
`data-action-icon` (nome de um Material Symbol).
Para ações assíncronas, importe `beginActivity` de `static/js/core/activity.js`:

```javascript
const activity = beginActivity("Buscando endereço", "location_on");
// Ao receber o resultado real da operação:
activity.success("Endereço encontrado");
// Em caso de falha, use activity.error("Não foi possível consultar").
// Para interromper sem aviso de resultado, use activity.cancel().
```

## Testes e qualidade

```bash
python manage.py check
python manage.py test
```

## Usuários demo

Após `seed_demo`:

- Cliente: `cliente@demo.com` / `123456`
- Staff: `staff@demo.com` / `123456`
- Gerente: `gerente@demo.com` / `123456`

## Gestão do empreendimento

Acesse `/dashboard/` com o gerente demo (`gerente@demo.com` / `123456`) ou um
superusuário. O login do gerente abre o painel automaticamente. Clientes e
atendentes não têm acesso às telas de gestão.

O painel inclui recebimentos aprovados, despesas pagas, saldo por período,
exportação CSV, produtos mais vendidos, alertas de estoque, cadastro e edição
de funcionários, produtos e categorias, além da consulta de pedidos.
Funcionários podem ter cargo de atendimento ou gerente e o acesso pode ser
desativado. Produtos e categorias podem ser desativados sem apagar históricos.

Em Produtos, informe a quantidade em estoque e o estoque mínimo. Quantidade
em branco mantém o produto sem controle por unidades; zero indica esgotado.
O carrinho valida a soma das unidades do mesmo produto, e a finalização do
pedido revalida e baixa o estoque em uma transação. Cancelamentos pelo serviço
de pedidos ou pelo Django Admin devolvem apenas as unidades reservadas pelo
pedido, uma única vez. Pedidos antigos não têm baixa retroativa. O painel
mostra alertas de produtos no mínimo ou abaixo dele, além dos insumos.

O saldo é a diferença entre recebimentos e despesas cadastradas, não um cálculo
contábil de lucro. Os pagamentos continuam simulados; o período de recebimento
usa a data da última atualização do pagamento aprovado. Cadastros avançados
(insumos, adicionais, alérgenos e estoque) permanecem no Django Admin
(`/admin/`), disponível integralmente para superusuários.

## Observações

Clientes autenticados podem publicar e editar uma avaliação geral da loja em
`/avaliacoes/loja/`, com nota de 1 a 5 e comentário de até 1000 caracteres.
As avaliações publicadas aparecem na página inicial e na lista pública, com
primeiro nome e média das notas, sem e-mail ou CPF. Cada cliente possui uma
avaliação da loja, independente das avaliações de pedidos entregues.
Gerentes podem ocultar ou republicar feedbacks em `/dashboard/feedbacks/`;
editar um comentário oculto não remove a restrição do administrador.

O menu Cupons em `/dashboard/cupons/` permite cadastrar e editar códigos,
descontos fixos ou percentuais, validade, pedido mínimo e limites de uso.
Gerentes e superusuários podem desativar cupons sem apagar seus históricos.

Pix e cartão usam um simulador no detalhe do pedido: após etapas de envio e
análise, o servidor sorteia aprovado, pendente ou recusado com chances iguais.
O resultado fica salvo, com histórico de tentativas. Pendências podem ser
consultadas novamente e recusas permitem nova tentativa. Aprovações confirmam
o pedido e entram no financeiro. Reenvios da mesma tentativa não sorteiam
novamente. Dinheiro permanece pendente para recebimento na entrega.

Em `/dashboard/configuracoes/pagamentos/`, gerentes e superusuários podem
ativar ou desativar a simulação. A configuração é global e persistente,
inicialmente ativada. Ao desativar, novas simulações e novas tentativas são
bloqueadas, inclusive em páginas já abertas. Os resultados anteriores são
preservados; novos pagamentos Pix/cartão aguardam confirmação da loja.

O frontend é server-rendered, mobile-first e usa JS apenas para melhorias progressivas, como estados de ação e total dinâmico da personalização. O backend recalcula preços, descontos e totais, mantendo regras financeiras fora do frontend.
