# Laura IA 2.0

A série 2 inicia o aprendizado em jogos e tomada de decisões. Esta versão traz **Jogos → Labirinto da Laura**: uma grade 7 × 7 com obstáculos, origem, destino, comandos manuais e um botão para a Laura escolher o próximo passo. O labirinto sempre tem solução. A escolha automática usa busca de caminhos simples e ainda não aprende com os resultados. Recompensas e punições pertencem à 2.1; Q-learning à 2.2; decisões com rede neural à 2.3.

O jogo roda localmente, sem instalação adicional. O estado da partida permanece enquanto o servidor está aberto; reiniciar o programa inicia outra partida. As imagens, memórias e avaliações da série 1 permanecem disponíveis, sem mudanças gerais nas capacidades visuais. O backup JSON continua cobrindo os dados anteriores; a partida temporária não integra o backup.

Para atualizar a partir da 1.10, exporte o backup na instalação antiga, extraia esta pasta, execute `app_web.py` e importe o JSON na nova instalação. Mantenha a pasta antiga até verificar os dados.

As notas abaixo documentam as capacidades preservadas da 1.10.

Assistente pessoal local em Python: conversa, guarda memórias, aprende categorias de imagens, reconhece padrões e cria composições com as fotos ensinadas. Funciona offline no computador e no Pydroid 3, com interface no navegador.

## Revisão final antes da instalação

Consulte `REVISAO-1.10.md` para o histórico e os limites da etapa de imagens.

- **Variação da última:** usa a imagem anterior e agora respeita as opções atuais de resolução, formato, qualidade e estilo.
- **Desfazer avaliação:** remove a avaliação da última criação quando você mudar de ideia.
- **Cópia antes de importar:** guarda o banco atual em `data/laura-antes-da-importacao.db`. Use **Aprendizado → Baixar cópia anterior** para exportá-lo em JSON e depois importá-lo. É mantida uma cópia, substituída na próxima importação; reserve espaço livre para ela.
- **Posição na cena:** descrições como `cavalo na floresta à esquerda em cima` e `cavalo na floresta de ponta-cabeça` posicionam ou giram o recorte. Esquerda/direita indicam posição na imagem, não a direção para onde o animal olha.
- **Correção de reconhecimento:** disponível também quando a Laura acredita ter acertado. Trocar a foto limpa o vínculo da análise anterior, e respostas atrasadas são ignoradas.
- **Giro ambíguo:** exemplos em orientações conflitantes não produzem uma direção arbitrária quando os votos empatam.
- **Descrição incompatível:** avisa quando a categoria selecionada contradiz um objeto conhecido citado no texto ou quando o pedido exige mais de uma categoria de objeto.

## Novidades da 1.10

| Recurso | 1.9 | 1.10 |
|---|---|---|
| Maior lado da imagem criada | 768 pixels | 1536 pixels |
| Formatos na interface | Quadrado | Quadrado, paisagem 4:3 e retrato 3:4 |
| Cálculo da composição aprendida | Até 384 pixels | Rápido: 384; equilibrado: 512; detalhado: 768 |
| Fotos enviadas | Até 6 MB e 20 MP | Até 20 MB e 64 MP |
| Detalhes guardados em novos exemplos | Até 320 × 240 | Até 640 × 640, mantendo a proporção |
| Ensino em lote pela galeria | Até 20 fotos | Até 100 fotos por lote |
| ZIP | Até 50 MB; 100 fotos por categoria | Até 100 MB; 250 fotos por categoria |
| Backup importado | Até 120 milhões de bytes | Até 200 MB |
| Avaliações guardadas | Até 120 | Até 500 recentes |

Os limites de MB da 1.10 usam 1024 × 1024 bytes. Cada ZIP aceita até 1.000 imagens válidas, 2.000 entradas e 400 MB de conteúdo descompactado. Esses são limites por importação: você pode ensinar outros lotes depois. O total armazenado depende do espaço e do desempenho do aparelho.

### Reconhecimento

- Compara também imagens giradas em 90°, 180° e 270°, incluindo recortes do objeto.
- Reavalia as três categorias candidatas usando uma grade de detalhes de 32 × 32 e até seis fotos por categoria.
- Mantém o reconhecimento anterior quando a comparação adicional não oferece evidência suficiente.
- Aplica a orientação EXIF de fotografias de celular e coloca fundo branco nas áreas transparentes.
- Continua indicando posição e giro relativo às fotos ensinadas, quando consegue separar o objeto do fundo.

### Criação e avaliações

- Opções de 384, 512, 768, 1024 e 1536 pixels no maior lado.
- O modo detalhado usa mais pixels durante a composição e mais detalhe no recorte de cenas.
- O objeto colocado na cena acompanha o tamanho escolhido para a imagem.
- A interface mostra dimensões e tempo da criação.
- **Ficou boa** e **Melhorar** continuam orientando a escolha entre três candidatos.
- É possível desmarcar **Usar minhas avaliações** para criar uma única opção mais rapidamente; as avaliações continuam salvas.
- As opções são comparadas uma a uma para reduzir o uso de memória.
- ZIPs mantêm as prévias compactadas e decodificam uma por vez durante o ensino.

## Instalação no Android

1. Extraia a pasta `Laura-IA-2.0` do ZIP.
2. Se Pillow já funciona no Pydroid 3, pode usá-lo diretamente. Na primeira instalação, execute `pip install Pillow`.
3. Abra `app_web.py` no Pydroid 3 e execute.
4. No navegador do mesmo celular, abra `http://127.0.0.1:5000`.

Comece com **512 pixels / Equilibrado**. Para mais detalhe, teste **1024 / Detalhado** e depois **1536**. Resoluções maiores e avaliações ativas levam mais tempo; o desempenho depende do aparelho.

## Instalação no computador

Dentro da pasta do projeto:

```bash
python -m pip install -r requirements.txt
python app_web.py
```

Abra `http://127.0.0.1:5000`. Requer Python 3.10 ou mais recente. O arquivo `iniciar_web_windows.bat` também inicia a interface no Windows. `app.py` é a versão de conversa no terminal.

## Atualizar da 1.9 ou anterior

1. Na versão anterior, vá a **Aprendizado → Exportar backup** e guarde o JSON.
2. Encerre a versão anterior no Pydroid ou terminal.
3. Extraia a 1.10 em outra pasta, execute `app_web.py` e atualize a página do navegador.
4. Vá a **Aprendizado → Importar backup** na nova versão.
5. Confira categorias, fotos, memórias e avaliações antes de apagar a pasta antiga.

A importação substitui os dados da instalação atual. Os backups anteriores sem avaliações continuam aceitos. O novo backup se chama `laura-backup-1.10.json`. Importar um backup antigo não recria os detalhes perdidos em miniaturas: o limite de 640 pixels beneficia fotos ensinadas novamente ou fotos novas.

## Ensinar e testar imagens

Na aba **Imagens**, envie uma foto e toque em **Analisar**. Para ensinar, escreva a categoria e toque em **Ensinar**, ou use **Ensinar várias** para até 100 fotos. Use imagens variadas do mesmo objeto, com boa iluminação. Duplicatas são ignoradas.

Para importar um ZIP, organize uma pasta por categoria, por exemplo `cavalo/foto01.jpg` e `floresta/foto01.jpg`. Escolha o limite por categoria e toque em **Importar ZIP**. O número mostrado é o limite de leitura; fotos repetidas ou inválidas podem reduzir o total aprendido.

Na criação, selecione uma categoria ou descreva uma cena, como `cavalo na floresta`. Para compor com fotos, ensine pelo menos três imagens de cada categoria. Fundos simples ajudam a separar o objeto.

Deixe **Código da imagem** vazio para obter novas variações. Um código repetido reproduz uma criação com as mesmas opções, exemplos e avaliações. **Criar variação da última** mantém a última criação como referência e usa outro código.

## Testes rápidos para fechar a fase 1.x

1. Ensine uma foto maior que 6 MB e confira se foi aceita.
2. Analise a mesma foto na posição normal e girada; compare a categoria e o giro indicado.
3. Crie a mesma categoria em 512 e 1536 pixels; confira a resolução do arquivo baixado.
4. Teste paisagem e retrato, verificando o tamanho do objeto na cena.
5. Avalie uma criação como boa e outra para melhorar; teste novas variações com as avaliações ativadas e desativadas.
6. Exporte o backup da 1.10 e importe em outra instalação para conferir as memórias, fotos e avaliações.

## Outras capacidades mantidas

Conversa com personalidade calma, memórias editáveis, aprendizado de perguntas e respostas, cálculo local, classificadores de texto, histórico, correções de reconhecimento, métricas visuais, exclusão e renomeação de categorias e backup JSON.

## Limitações

A criação aprendida combina regiões das fotos ensinadas. Ainda pode misturar letras, texturas e contornos; não equivale a um grande modelo generativo. Uma saída de 1536 pixels não significa que todos esses detalhes foram inventados: a composição aprendida é calculada em até 768 pixels e ampliada. Paisagens procedurais são desenhadas no tamanho solicitado.

Fotos recebidas são reduzidas internamente a até 2048 pixels no maior lado. As fotos de treino são guardadas em JPEG de até 640 × 640; os arquivos originais do celular não são alterados.

O reconhecimento é aproximado e baseado em exemplos; não há garantia de identificar qualquer objeto. O percentual exibido é uma estimativa de similaridade, não uma probabilidade calibrada. O giro é relativo às fotos ensinadas e pode ser indeterminado em objetos simétricos, orientações variadas ou fundos confusos.

As avaliações ajudam a escolher por semelhança visual geral; não treinam um novo modelo de geração nem garantem melhora a cada clique.

## Privacidade

Os dados ficam em `data/laura.db`. Não há API externa, telemetria ou envio de fotos pela internet. O servidor atende apenas em `127.0.0.1` no próprio aparelho.

## Testes automatizados

```bash
python -m unittest discover -s tests
```

Com Node.js disponível no computador, execute também `node tests/test_ui.cjs` para verificar as interações da interface. Node.js não é necessário para usar a Laura.
