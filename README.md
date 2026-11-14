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

Requer Docker com Compose. Na raiz:

```bash
cp .env.example .env
# Edite SECRET_KEY e POSTGRES_PASSWORD no .env antes da primeira execução.
docker compose up --build
```

Acesse http://localhost:8000 e http://localhost:8000/health/. O Compose usa
PostgreSQL 16 com healthcheck, aplica as migrations versionadas e inicia
`runserver` com `DEBUG=True`. O código e o Tailwind são compilados na imagem;
após alterações, reconstrua com `docker compose up --build`. Não há volume de
código sobrescrevendo os assets gerados. Node só existe no estágio de build.

```bash
docker compose exec web python manage.py migrate --noinput
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo  # manual, somente demonstração
docker compose exec web python manage.py check
docker compose exec web python manage.py test
docker compose down
```

Os volumes `postgres_data` e `media_data` persistem banco e uploads locais.
`docker compose down` os preserva; adicionar `-v` apaga os dados. O SQLite antigo
não é utilizado nem importado. Não existe fallback automático para SQLite.
O nome do projeto Compose continua `appcoffee`, preservando os volumes existentes.
Se já possui um volume PostgreSQL, mantenha as credenciais originais no `.env`:
alterar `POSTGRES_PASSWORD` não altera a senha de um banco já inicializado.

`APP_PORT` altera a porta publicada (padrão 8000); ajuste também a origem CSRF.
O Compose carrega `.env`, força o host `db` e ignora `DATABASE_URL` para evitar
conectar acidentalmente ao Neon. As variáveis `POSTGRES_*` locais não precisam
ser copiadas para o Render. A publicação local é restrita a `127.0.0.1`.

### Ambiente Python local sem Docker

Requer Python 3.12, Node/npm para compilar CSS e um PostgreSQL acessível.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
npm ci
npm run build
```

Edite `.env`: mantenha `DEBUG=True`, defina `SECRET_KEY`, use
`POSTGRES_HOST=localhost` e as credenciais do seu PostgreSQL. Alternativamente,
defina `DATABASE_URL=postgresql://USUARIO:SENHA@localhost:5432/appcoffee`
(com valores próprios e senha codificada para URL). `DATABASE_URL` tem
precedência sobre `POSTGRES_*` fora do Compose. Crie o banco previamente.

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo  # opcional, somente desenvolvimento
python manage.py runserver
```

`npm run watch` recompila CSS durante o desenvolvimento, em outro terminal.
O Tailwind 3.4 usa a mesma paleta, fontes e sombras antes declaradas no template;
a configuração única fica em `tailwind.config.cjs`. O build varre templates,
formulários e JavaScript, incluindo classes usadas em mensagens dinâmicas.
`static/css/tailwind.css` é gerado por `npm run build` e não é versionado.
Os estilos próprios permanecem em `static/css/`. Nenhum CDN de desenvolvimento
Tailwind é carregado pelo navegador.

## Deploy no Render com Neon PostgreSQL

Arquitetura: **Render → Docker → Gunicorn (`config.wsgi:application`) → Neon
PostgreSQL com SSL**. O PostgreSQL do Compose participa somente do desenvolvimento.
WhiteNoise serve os estáticos compilados; não serve uploads. O deploy usa o
Dockerfile diretamente, sem configuração concorrente em `render.yaml`.

1. Envie o projeto e migrations para um repositório GitHub, na branch `main`.
   Nunca envie `.env`, uploads locais, senhas ou connection strings reais.
2. No Neon, crie um projeto e escolha uma região próxima do serviço Render.
   Crie/selecione banco e role pelo console. Em **Connect**, copie a connection
   string PostgreSQL. Prefira a conexão **pooled** para o serviço web.
3. Preserve os parâmetros SSL fornecidos pelo Neon, inclusive
   `sslmode=require` (ou mais rigoroso) e `channel_binding=require`, se presentes.
   Exemplo estrutural, sem credenciais reais:
   `postgresql://USUARIO:SENHA@HOST_POOLER/BANCO?sslmode=require`.
   Não remova SSL. O projeto mantém psycopg 3 e desativa cursores de servidor
   para compatibilidade com pooling transacional.
4. No Render, crie **New → Web Service**, conecte o repositório, selecione
   branch `main`, runtime **Docker**, Dockerfile `./Dockerfile` e plano **Free**
   para demonstração. Deixe **Docker Command** vazio para utilizar o CMD.
5. Configure as variáveis abaixo no painel. Use o domínio real atribuído ao
   serviço, sem presumir seu nome. Gere uma chave exclusiva para produção.
6. Configure **Health Check Path** como `/health/`. Habilite Auto Deploy para
   `main` se quiser publicar cada alteração dessa branch.
7. Faça o deploy. O build executa `npm ci`, compila Tailwind, instala Python e
   executa `collectstatic --noinput` sem acessar banco nem precisar de segredos.
   O container final roda como usuário sem privilégios e não contém Node ou `.env`.
8. No startup, o entrypoint executa `python manage.py migrate --noinput` e só
   inicia Gunicorn se as migrations passarem. Não há `makemigrations` nem seed
   automático. Consulte os logs para confirmar que as migrations terminaram.
9. Crie o superusuário manualmente conforme explicado abaixo.
10. Teste HTTPS, `/health/`, home, catálogo, login, `/admin/` e os arquivos de
    `/static/`, incluindo `css/tailwind.css`. Teste login por formulário para
    verificar CSRF, proxy HTTPS e cookies seguros.

### Variáveis do Render

| Variável | Valor/configuração |
| --- | --- |
| `SECRET_KEY` | Segredo aleatório exclusivo; obrigatório |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | Domínio real `SEU-SERVICO.onrender.com`, sem protocolo; múltiplos separados por vírgula |
| `CSRF_TRUSTED_ORIGINS` | `https://SEU-SERVICO.onrender.com`; inclua seu domínio customizado se houver |
| `DATABASE_URL` | Connection string do Neon, com SSL; obrigatória |
| `PORT` | Injetada pelo Render; não precisa definir |

Para gerar a chave na sua máquina: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`.
Cole o resultado somente no painel. Não use a chave de exemplo local em produção.

Sem `DATABASE_URL` ou `SECRET_KEY`, com banco diferente de PostgreSQL ou SSL
explicitamente desabilitado, a produção falha com erro de configuração.
Gunicorn escuta `0.0.0.0:${PORT:-8000}`, com logs de acesso/erro em stdout/stderr.
O Django também usa logs de console. `X-Forwarded-Proto` do proxy Render permite
reconhecer HTTPS; cookies de sessão e CSRF são seguros com `DEBUG=False`.
O redirecionamento HTTPS fica ativo em produção (a liveness `/health/` é isenta).
Somente publique atrás de um proxy confiável que defina esse cabeçalho.

### Migrations e superusuário no plano gratuito

A configuração não depende de pre-deploy commands, shell remoto ou jobs pagos.
O startup aplica migrations para a demonstração de instância única. Não execute
várias réplicas nem deploys concorrentes com essa estratégia. Antes de escalar,
separe migrations em um único job controlado, desative o startup com
`RUN_MIGRATIONS=false` e mantenha migrations compatíveis com a versão anterior
(o Render pode manter o container anterior atendendo durante um deploy).
Não gere migrations em produção.

O plano Free não oferece shell SSH/painel. Na máquina local, use o mesmo commit e
as dependências Python instaladas. Em um terminal dedicado, exporte as variáveis
`SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` e `DATABASE_URL`
do ambiente de produção. Insira os segredos com segurança, sem gravá-los no Git
ou no histórico do shell. Para operações administrativas, pode usar a connection
string **direta** do mesmo banco Neon, também com SSL. Execute:

```bash
python manage.py migrate --noinput  # se necessário; startup já aplica as migrations
python manage.py createsuperuser
```

Esses comandos usam diretamente o Neon, sem depender do container do Render.
Não use `docker compose exec` nesse caso: ele aponta para o PostgreSQL local.
Não execute os comandos contra produção ao mesmo tempo que um deploy.
`seed_demo` permanece manual e cria/resetta contas com senhas públicas de
desenvolvimento; não o execute em um ambiente real.

### Estáticos, uploads e limites

WhiteNoise usa `CompressedStaticFilesStorage` e `STATIC_ROOT=/app/staticfiles`.
As URLs estáveis preservam imports relativos dos ES Modules e recursos do PWA;
não configuramos cache imutável para esses nomes sem hash. O CSS já está
compilado antes de Gunicorn iniciar. Fontes Google continuam sendo recursos
externos, como no frontend existente.

O filesystem do Render é efêmero, inclusive no Free: não serve para persistir
imagens de produtos ou outros uploads. Por padrão, novos uploads em produção
falham explicitamente com erro de configuração, antes de gravar, para evitar
perda silenciosa. O catálogo pode ser usado sem imagens; os placeholders
existentes continuam funcionando. Uploads locais continuam no volume `media_data`.
Imagens demonstrativas fixas novas podem ser versionadas em `static/`.

Para habilitar uploads reais, escolha um serviço externo e instale o backend
Django correspondente. Configure `MEDIA_STORAGE_BACKEND` com a classe do backend
e `MEDIA_STORAGE_OPTIONS` com suas opções em JSON no ambiente; credenciais ficam
somente em variáveis/secretos do provedor. Configure `MEDIA_URL` se o backend
precisar. Migre também os uploads existentes para esse serviço preservando os
nomes armazenados no banco. Nenhuma integração externa foi instalada sem
necessidade. WhiteNoise nunca deve servir `media/` em produção.

O plano Free pode suspender o serviço após inatividade, causando demora no
primeiro acesso, e não fornece disco persistente. O Neon também pode suspender
o compute ocioso; as conexões reutilizadas têm health checks. Confirme cotas e
limites nas páginas dos provedores antes da apresentação. O projeto preserva
Django 5.1; uma atualização para uma versão suportada deve ser planejada antes
de uso real em produção ([suporte do Django](https://www.djangoproject.com/download/)).

Referências: [Docker no Render](https://render.com/docs/docker),
[limitações do Free](https://render.com/docs/free),
[Django com Neon](https://neon.com/docs/guides/django),
[WhiteNoise](https://whitenoise.readthedocs.io/en/stable/django.html),
[Tailwind CLI v3](https://v3.tailwindcss.com/docs/installation).

### Validar a imagem de produção localmente

```bash
docker build -t app .
```

Crie um arquivo local ignorado pelo Git (`.env.production-test`) com as cinco
variáveis de produção e um PostgreSQL acessível ao container com SSL. Para Neon,
use um banco/branch separado para testes. Acrescente `SECURE_SSL_REDIRECT=False`
apenas nesse arquivo para testar em HTTP local; cookies seguros continuam
exigindo HTTPS para login. Execute sem passar um comando alternativo:

```bash
docker run --rm --env-file .env.production-test -e PORT=8080 -p 127.0.0.1:8080:8080 app
curl http://localhost:8080/health/
curl -I http://localhost:8080/static/css/tailwind.css
```

Para testar login em condições de produção, use HTTPS por um proxy confiável,
ou faça a validação final no próprio domínio HTTPS do Render.

## Feedback de ações

Nos cards da página inicial e do catálogo, **Pedir** adiciona o produto sem
sair da página. Produtos já adicionados ficam destacados e exibem **No carrinho**
com a quantidade total, somando inclusive personalizações. O contador da sacola
é atualizado na mesma ação. Os detalhes do produto também permitem adicionar
sem redirecionar. Para finalizar, abra o carrinho pelo menu ou pelo ícone da sacola.
Ao recarregar ou voltar do carrinho, as quantidades são consultadas novamente.

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

Com ambiente PostgreSQL de desenvolvimento configurado e CSS compilado:

```bash
python manage.py check
python manage.py test
node --test tests/*.test.mjs
```

Ou execute os checks Python no container:

```bash
docker compose exec web python manage.py check
docker compose exec web python manage.py test --noinput
```

A configuração de deploy inclui regressões para variáveis obrigatórias,
PostgreSQL sem fallback, SSL, cookies seguros, bloqueio de uploads efêmeros e
health check sem consultas ao banco. A validação da infraestrutura em
14/11/2026 passou com 116 testes Django, dois arquivos de testes JavaScript,
build Docker e smoke test de produção com PostgreSQL SSL, Gunicorn em porta
customizada, login com CSRF e estáticos comprimidos. O layout do login foi
verificado em 390 e 1440 px. Os testes usaram banco e containers isolados;
não representam uma publicação real nas contas Render/Neon.


## Usuários demo

Somente em desenvolvimento, após executar manualmente `seed_demo`:

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

## Cartões cadastrados

Em **Minha conta → Formas de pagamento**, o cliente pode cadastrar cartões de
teste, escolher um padrão e remover cartões. No checkout, ao escolher cartão,
selecione um dos cartões cadastrados ou use **Cadastrar cartão** para adicionar
e visualizar o cartão salvo antes de voltar à finalização. Após cadastrar, a
página recarrega na posição do novo cartão, com o formulário limpo e confirmação.
Cartões vencidos e cartões de outros usuários não
podem ser usados. A remoção preserva a identificação mascarada nos pedidos antigos.

O cadastro faz parte do simulador local: aceita apenas os números de teste
Visa `4242 4242 4242 4242` e Mastercard `5555 5555 5555 4444`, com validade atual
ou futura. Não informe cartões reais. Não há cobrança ou integração com uma
operadora; o resultado do pagamento continua sendo sorteado pelo simulador.
São armazenados apenas titular, bandeira, últimos quatro dígitos, validade e
referência aleatória. O número completo e o CVV não são armazenados; o formulário
não solicita CVV. Os números de teste constam na
[documentação da Stripe](https://docs.stripe.com/testing#cards); o projeto não usa
a API da Stripe.

## Aplicativo instalável (PWA)

O site inclui ícones próprios, manifest e service worker. Em navegadores que
oferecem instalação, o botão **Instalar aplicativo** aparece quando a instalação
está disponível. No iPhone/iPad, abra no Safari e use **Compartilhar → Adicionar
à Tela de Início**. O aplicativo abre em uma janela própria.

Em desenvolvimento, utilize `http://localhost:8000`. Em produção, o PWA precisa
de **HTTPS**, incluindo ao acessar pelo celular em outro dispositivo. Um endereço
HTTP da rede local não habilita o service worker. Os arquivos estáticos devem
estar publicados e `/service-worker.js` precisa permanecer acessível na raiz,
com seu tipo JavaScript e sem cache permanente.

Sem internet, a navegação exibe uma página de conexão indisponível com opção de
tentar novamente. Apenas essa página e os ícones são guardados no cache do PWA;
pedidos, pagamentos, endereços, entregas e páginas administrativas não são salvos
para uso offline. Não há envio de pedidos nem pagamentos em segundo plano.

Os ícones estão em `static/icons/`; `icon.svg` é a fonte vetorial. Foram incluídos
favicon ICO (16/32/48 px), ícones de instalação 192/512 px, versões maskable
192/512 px e ícone Apple de 180 px. Ao modificar os recursos pré-armazenados,
atualize a versão do cache em `core/templates/core/service-worker.js`.

## Rastreamento da entrega

Em Meus pedidos ou nos detalhes do pedido, o cliente pode usar **Rastrear entrega**
para consultar as etapas, previsão inicial, endereço e histórico. A página consulta
as atualizações da loja a cada 15 segundos e permite atualizar manualmente.
Pedidos entregues ou cancelados encerram a consulta automática. Se a previsão
inicial passar, a tela informa o atraso sem inventar uma nova previsão.

Em `/dashboard/pedidos/`, o gerente abre **Gerenciar entrega** e avança por
Confirmado → Preparando → Pronto → Saiu para entrega → Entregue. Também pode
cancelar um pedido em andamento e escrever uma mensagem de até 180 caracteres
para o cliente. Cada alteração registra responsável e horário. A tela impede
pular ou retroceder etapas e protege contra atualizações de uma página desatualizada.
O acompanhamento é por etapas informadas pela loja; não há localização GPS.
Cada cliente só pode consultar seus próprios pedidos.
Para pagamentos com cartão, o botão e o acesso ao rastreamento só são liberados
quando o pagamento está aprovado. Pagamentos pendentes, recusados ou estornados
não liberam o rastreamento de pedidos com cartão. Pix e dinheiro mantêm o
acompanhamento disponível independentemente da aprovação.

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
