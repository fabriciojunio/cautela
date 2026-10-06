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

| Projeto | O que entra |
|---|---|
| Prumo | persistência de desempenho de fundo, por classe, e cobertura do dado de taxa |
| Anteparo | sensibilidade da provisão de crédito à hipótese |

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

Com `LANGFUSE_PUBLIC_KEY` e `LANGFUSE_SECRET_KEY` configuradas, cada execução vai
para o Langfuse com uma span por etapa: os termos da pergunta, quais fatos foram
recuperados, o tamanho do texto gerado e o veredicto do auditor.

O campo que mais vale é o veredicto: ele transforma "o agente respondeu estranho"
numa contagem de quantas respostas foram barradas e por quê.

Sem as chaves, o rastro é desligado e o agente roda igual. Falha de telemetria
nunca derruba a resposta de quem perguntou.

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

21 testes, nenhum deles tocando a rede.
