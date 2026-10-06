# Cautela

Agente de investimentos que **não recomenda**. Ele responde com número medido,
cita a fonte e termina declarando a limitação. Quando não tem número, diz que
não sabe.

O nome é termo de mercado (cautela é o certificado de ações) e é o que o sistema
faz.

```
python -m cautela.interface.cli
python -m cautela.interface.cli "o desempenho passado de um fundo de ações prediz o futuro?"
```

## A premissa

Um assistente que fala de dinheiro tem um risco que os outros não têm: número
inventado com tom de autoridade. Um que erra a data de uma prova atrapalha um
aluno; um que erra a rentabilidade de um fundo, ou inventa uma, induz decisão de
dinheiro de alguém.

Daí as três regras que não dependem de o modelo colaborar:

**Não recomendar.** Recomendação de investimento no Brasil é atividade regulada
pela CVM e exige analista certificado. A regra não é de estilo, é de não exercer
profissão alheia. O auditor barra "compre", "venda", "recomendo", "vale a pena
investir".

**Não citar número que não veio do acervo.** Cada resposta é conferida contra os
números que foram entregues ao modelo. Número que está na resposta e não estava
no contexto não veio do dado, veio do modelo, e a resposta é substituída.

**Sempre declarar o limite.** Fato sem limitação não entra no acervo.

Instrução em prompt é pedido, não garantia. O que garante é código que lê a saída
e a recusa.

## De onde vêm os números

Nenhum número é digitado à mão. O acervo é montado lendo os artefatos JSON dos
experimentos dos projetos vizinhos:

| Projeto | Artefato lido | O que entra |
|---|---|---|
| Prumo | `prumo/resultados/persistencia.json` | persistência de desempenho de fundo, por classe de carteira |
| Prumo | `prumo/resultados/taxa.json` | cobertura do dado de taxa de administração |
| Anteparo | `credito-ifrs9/resultados/cartao_do_modelo.json` | sensibilidade da provisão de crédito à hipótese |
| Decurso | `decurso/resultados/duracao.json` | duração de processo judicial, com a base e o recorte |
| Verbete | `verbete/resultados/treino.json` | classificação de texto regulatório |
| Trato | `trato/resultados/cartao_do_dado.json` | efeito medido do contato na renegociação |

São 17 fatos ao todo, de seis carregadores.

Isso tem uma consequência prática: **se o experimento for refeito e o resultado
mudar, o agente passa a responder o número novo sem ninguém editar texto.** Já
aconteceu em outro projeto da mesma família: a base cresceu de 2.648 para 4.118
processos e um achado deixou de ser significativo. Um acervo escrito à mão
continuaria afirmando o achado morto.

Quando o artefato não está presente, os fatos daquele projeto simplesmente não
entram, e o agente recusa a pergunta. Ausência de dado não é permissão para
opinar.

## O grafo

```
recuperar  ->  redigir  ->  auditar  ->  entrega ou substitui
```

Em LangGraph. A razão de ser grafo e não função em linha reta é que o caminho da
recusa é um caminho de verdade, com saída própria, e não um `if` escondido no
meio da redação. Desenhado assim, dá para olhar e responder "como esse agente
pode recusar?" sem ler o código todo, que é a pergunta de quem audita.

O nó de auditoria roda sempre, inclusive quando o modelo não foi chamado.

## Modos de operação

| Modo | Quando | O que muda |
|---|---|---|
| Gemini | `GEMINI_API_KEY` configurada | o modelo redige a prosa em volta do fato |
| Local | sem chave, sem rede | o fato é transcrito na forma em que foi medido |

O número é o mesmo nos dois. A diferença é só o texto em volta. O modo local não
é remendo, é degradação projetada: demonstração em sala cai e cota de tier
gratuito acaba.

## Observabilidade

Dois destinos pela mesma porta, porque eles respondem perguntas diferentes:

**Langfuse** é específico de LLM. Guarda entrada, saída e veredicto de cada
etapa, e serve para abrir **uma** execução e entender por que ela saiu assim. A
execução aparece como um `agent` com três spans dentro: recuperar, redigir e
auditar.

**Datadog LLM Observability** é a visão de conjunto: quantas execuções, quanto
tempo, quantas recusas, e é onde o alerta dispara quando a taxa de recusa muda
de patamar.

O campo que mais vale nos dois é o veredicto do auditor: ele transforma "o agente
respondeu estranho" numa contagem de quantas respostas foram barradas e por quê.

Configuração, num `.env` local que não vai para o repositório:

```
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://us.cloud.langfuse.com

DD_LLMOBS_ENABLED=1
DD_LLMOBS_ML_APP=cautela
DD_API_KEY=...
```

Nenhuma credencial passa pelo código: os dois SDKs leem as próprias variáveis, e
o projeto só verifica se elas existem.

Sem chave, o rastro desliga e o agente roda igual. Falha de telemetria nunca
derruba a resposta de quem perguntou, e cada exportador é isolado do outro.

Para conferir que o rastro chegou mesmo: `python scripts/conferir_rastro.py`.

### O defeito que esse script encontrou

A primeira versão do exportador chamava `start_span`, que é o nome do método na
versão 3 do SDK do Langfuse. Na versão 4 ele se chama `start_observation`. O
`try` em volta, que existe para telemetria não derrubar resposta, engoliu o
`AttributeError`: o agente respondia normalmente e **nada era registrado**.

É o modo de falha mais perigoso de observabilidade, e o único jeito de pegar é
ler de volta. Por isso o script existe.

Segunda lição do mesmo episódio: depois de corrigir, a consulta continuou
devolvendo vazio por alguns minutos. A ingestão tem atraso, e vazio logo depois
de rodar não prova que nada foi enviado, prova que nada chegou ainda.

Terceira, e a mais sutil das três: o script passou a listar as observações
corretamente, com nome, tipo e horário, e **todas as gerações apareciam sem
modelo e sem token**. A conclusão fácil era que os atributos não estavam
subindo. Não era isso. A versão 2 da API devolve grupos de campos, o padrão é
`core,basic`, e entrada, saída, modelo, token e custo ficam fora — e vêm
ausentes, não nulos. O dado estava lá desde o começo; quem não pedia era a
conferência.

É o mesmo erro das outras duas vezes com o sinal trocado. Antes a ferramenta
dizia que estava tudo bem e não estava; agora dizia que faltava dado e não
faltava. Nos dois casos a causa é a mesma: acreditar na ferramenta de
verificação sem verificar a ferramenta.

## Um defeito que o próprio sistema encontrou

Na primeira execução contra os artefatos reais, o agente **recusou a própria
transcrição**. O fato traz o intervalo de confiança escrito como `IC 95%`, o modo
local repetiu o fato inteiro, e o auditor tratou o `95%` como número inventado
pelo modelo.

A correção foi arrumar a definição, não afrouxar a regra: vale o número que foi
**entregue ao modelo**, e o intervalo de confiança estava no contexto. O caso
virou teste.

## Rodar

```
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
```

34 testes, nenhum deles tocando a rede.
