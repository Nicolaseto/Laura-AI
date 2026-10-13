# Revisão da Laura 1.10 — 23/09/2026

Esta revisão compara os pedidos da série 1.x com o código entregue. A versão continua offline, usa Python e Pillow e foi preparada para Pydroid 3 e computador. Os testes foram executados neste ambiente Linux; desempenho e interface no Android ainda precisam ser conferidos no aparelho.

## O que combinamos e o que está entregue

| Pedido | Situação na 1.10 revisada |
|---|---|
| Aprender com fotos | Presente: categorias, ensino individual, câmera, galeria, lotes e ZIP de pastas. |
| Reconhecer e corrigir categorias | Presente: comparação por características, giros, recorte e comparação adicional de detalhes; correção disponível inclusive para resultados considerados conhecidos. |
| Aumentar resolução | Saída até 1536 pixels no maior lado. Composição aprendida calculada em até 384/512/768 pixels conforme a qualidade. A ampliação não inventa todos os detalhes de uma foto de alta resolução. |
| Formatos e qualidade | Quadrado, paisagem 4:3 e retrato 3:4; rápido, equilibrado e detalhado. |
| Mais fotos e arquivos maiores | Foto até 20 MiB e 64 MP; lote de 100; ZIP até 100 MiB, 250 por categoria e 1.000 imagens válidas no total. Novos exemplos guardados em até 640 × 640. |
| Criar variações sem repetir sempre | Presente: novo código quando o campo está vazio, seleção variada de exemplos e modos fiel/equilibrado/criativo. Não há garantia de diferença perceptível para qualquer conjunto de fotos. |
| Usar a imagem anterior | Presente: “Criar variação da última” usa a última criação como referência e outro código. A revisão faz o botão respeitar também as configurações atuais. |
| Descrever “cavalo na floresta” | Presente para categorias ensinadas: compõe um objeto sobre um cenário aprendido ou procedural. O recorte exige contraste com o fundo. Não é interpretação livre de qualquer frase. |
| Silhuetas variadas | Há escolha entre contornos dos exemplos, espelhamento e mudanças de enquadramento. Poses novas e anatomia inédita não são aprendidas por este mecanismo. |
| Criar imagens totalmente do zero | Parcial: paisagens e padrões são desenhados por regras; objetos aprendidos são recombinados/recortados das fotos ensinadas. A versão não contém um modelo generativo neural de imagens. |
| Reconhecer direção | Posição em cima/embaixo/esquerda/direita/centro e giro relativo aos exemplos. Objetos simétricos, fundos confusos e referências conflitantes podem resultar em “indeterminada”. Não identifica semanticamente para onde um animal olha. |
| Marcar imagens boas ou ruins | Presente: avaliações orientam a escolha entre três candidatos por semelhança visual. Até 500 avaliações recentes são armazenadas; a escolha consulta até 50 do contexto. Não garante evolução contínua nem treina um modelo gerador. |
| Preservar backups e aprendizado | Importação/exportação de memórias, respostas, categorias, exemplos, correções e avaliações; aceita backups antigos sem avaliações. Não recupera detalhes já perdidos em miniaturas antigas. |
| Manter demais capacidades | Conversa, personalidade, memórias editáveis, cálculos, histórico e classificadores de texto continuam presentes. Não foi acrescentado um modelo de linguagem geral nesta revisão. |

## Correções e adições desta revisão

1. **Variações respeitam as opções atuais.** Alterar resolução, formato, qualidade ou estilo também afeta a próxima variação da última imagem.
2. **Desfazer avaliação.** Permite retirar a avaliação da criação atual sem afetar outras avaliações.
3. **Cópia anterior à importação.** Antes de substituir dados, salva uma cópia completa do banco; “Baixar cópia anterior” exporta essa cópia em JSON. Apenas uma cópia é mantida, e a próxima importação a substitui.
4. **Posicionamento por descrição em cenas.** “À esquerda”, “à direita”, “em cima”, “embaixo”, “no centro” e “de ponta-cabeça” controlam o recorte do objeto. Não se aplicam como instruções gerais a qualquer criação abstrata.
5. **Correção vinculada à foto certa.** Selecionar outra imagem limpa o identificador de reconhecimento; respostas atrasadas de uma análise anterior não substituem o resultado atual.
6. **Correção sempre acessível.** A opção de informar outra categoria também aparece quando o reconhecimento tem confiança alta.
7. **Giros empatados tratados como incertos.** Evita escolher arbitrariamente uma direção quando referências opostas empatam.
8. **Pedidos incompatíveis têm mensagem explicativa.** Por exemplo, selecionar banana e pedir cavalo, ou pedir cavalo e gato juntos. A checagem de palavras é limitada ao vocabulário incorporado; não substitui compreensão geral da linguagem.
9. **Arquivos baixados têm nomes diferentes.** Incluem horário e resolução para facilitar comparar versões.
10. **Atualização da interface e dados.** Cabeçalhos de cache evitam reaproveitamento indevido de dados; pedidos JSON com formato incorreto recebem erro legível.

## Como instalar preservando seus dados

1. Exporte um backup JSON da instalação que você usa hoje.
2. Encerre essa instalação e extraia a pasta `Laura-IA-1.10` do novo ZIP em outro local.
3. Execute `app_web.py` no Pydroid 3; acesse `http://127.0.0.1:5000`.
4. Em Aprendizado, importe seu backup. Confira fotos e memórias antes de excluir a instalação antiga.
5. O ZIP não inclui o banco de desenvolvimento nem fotos pessoais.

## Verificações

**Resultado nesta revisão: 50 testes Python aprovados, testes de lógica da interface aprovados e sintaxe JavaScript validada.**

A suíte Python verifica reconhecimento, variações, cenas, limites, backups, memória, classificadores e personalidade. Foram acrescentados testes de cópia anterior, falha de importação com preservação dos dados, retirada de avaliação, posições da cena, giro ambíguo e respostas HTTP inválidas.

O teste JavaScript verifica alterações de formato/qualidade na variação, novo código, troca de foto durante reconhecimento e retirada de avaliação. Ele usa uma simulação do DOM, não substitui um teste visual no navegador do celular.

```bash
python -m unittest discover -s tests
node tests/test_ui.cjs
```

## Teste curto no seu celular

- Gere uma categoria em 512 pixels; mude para retrato e 1024 pixels e toque em “Criar variação da última”.
- Marque “Ficou boa”, depois “Desfazer avaliação”.
- Com três fotos de objeto e cenário ensinadas, peça `cavalo na floresta à esquerda` e depois `cavalo na floresta em cima à direita`.
- Analise uma foto e, enquanto processa, selecione outra. A análise antiga não deve aparecer como resultado da nova foto.
- Confira o backup importado e a opção “Baixar cópia anterior”. Guarde também seu backup externo.
