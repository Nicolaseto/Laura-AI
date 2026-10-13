const panels = document.querySelectorAll('.panel');
const navs = document.querySelectorAll('.nav');
const titles = {chat:['Conversa','Laura está pronta para conversar'],memories:['Memórias','O que Laura aprendeu sobre você'],profile:['Relacionamento','Confiança e estado atual'],history:['Histórico','Conversas salvas neste aparelho'],learning:['Aprendizado','Treinamento local do classificador'],vision:['Imagens','Visão computacional local e treinável'],game:['Jogos','Primeiro ambiente de decisões da Laura']};

async function api(url, options={}) { const r=await fetch(url,options);const data=await r.json();if(!r.ok) throw new Error(data.error||'Falha local');return data; }

navs.forEach(btn=>btn.addEventListener('click',()=>{
  navs.forEach(x=>x.classList.remove('active')); panels.forEach(x=>x.classList.remove('active'));
  btn.classList.add('active'); const name=btn.dataset.panel; document.getElementById(name).classList.add('active');
  document.getElementById('panel-title').textContent=titles[name][0]; document.getElementById('panel-subtitle').textContent=titles[name][1];
  if(name==='memories') loadMemories(); if(name==='profile') loadProfile(); if(name==='history') loadHistory(); if(name==='learning') loadLearning(); if(name==='vision') loadVisualCategories();
}));

const form=document.getElementById('chat-form'), input=document.getElementById('message-input'), messages=document.getElementById('messages');
function addMessage(role,text,meta=null){const el=document.createElement('div');el.className=`message ${role}`;if(role==='laura')el.innerHTML='<span class="orb"></span>';const box=document.createElement('div'),label=document.createElement('small'),p=document.createElement('p');label.textContent=role==='laura'?'Laura':'Nicolas';p.textContent=text;box.append(label,p);if(role==='laura'&&meta){const info=document.createElement('small');info.className='model-meta';const context=meta.context_topic?` | Contexto: ${meta.context_topic}`:'';const personality=meta.personality_tone?` | Tom: ${meta.personality_tone} • ${meta.personality_mood}`:'';info.textContent=`Rede neural: ${meta.neural_intent} • ${Math.round(meta.neural_confidence*100)}% | Probabilístico: ${meta.model_intent} • ${Math.round(meta.model_confidence*100)}%${context}${personality}`;const feedback=document.createElement('div');feedback.className='feedback';const up=document.createElement('button'),down=document.createElement('button');up.textContent='👍';down.textContent='👎';up.onclick=()=>sendFeedback(meta.input,meta.neural_confidence>=meta.model_confidence?meta.neural_intent:meta.model_intent,feedback);down.onclick=()=>correctFeedback(meta.input,feedback);feedback.append(up,down);box.append(info,feedback);}el.append(box);messages.append(el);messages.scrollTop=messages.scrollHeight;}
form.addEventListener('submit',async e=>{e.preventDefault();const text=input.value.trim();if(!text)return;addMessage('user',text);input.value='';input.disabled=true;try{const data=await api('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});addMessage('laura',data.answer,data);}catch{addMessage('laura','Não consegui acessar meu núcleo local. Verifique se o programa continua aberto.');}finally{input.disabled=false;input.focus();}});
async function sendFeedback(text,label,box){await api('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,label})});box.textContent='Aprendido ✓';}
async function correctFeedback(text,box){const labels='greeting, thanks, farewell, question, calculation, teaching, positive, negative';const label=prompt('Qual é a intenção correta?\n'+labels);if(label)try{await sendFeedback(text,label.trim().toLowerCase(),box);}catch{alert('Use uma das categorias mostradas.');}}
input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();form.requestSubmit();}});

let memoryData=[];async function loadMemories(){const list=document.getElementById('memory-list'),answers=document.getElementById('answer-list');const [data,learned]=await Promise.all([api('/api/memories'),api('/api/learned-answers')]);memoryData=data;renderMemories(data,list);answers.innerHTML='';if(!learned.length)answers.innerHTML='<div class="empty">Nenhuma resposta ensinada ainda.</div>';learned.forEach(item=>{const card=document.createElement('article');card.className='memory-card';const key=document.createElement('small'),value=document.createElement('p');key.textContent=item.question;value.textContent=item.answer;card.append(key,value);answers.append(card);});}
function renderMemories(data,list=document.getElementById('memory-list')){list.innerHTML='';if(!data.length){list.innerHTML='<div class="empty">Nenhuma memória encontrada.</div>';return;}data.forEach(item=>{const card=document.createElement('article');card.className='memory-card';const key=document.createElement('small'),value=document.createElement('p'),del=document.createElement('button'),edit=document.createElement('button');key.textContent=item.key.replaceAll('_',' ');value.textContent=item.value;del.textContent='×';edit.textContent='✎';edit.style.right='36px';del.onclick=async()=>{if(confirm('Excluir esta memória?')){await api('/api/memories/'+encodeURIComponent(item.key),{method:'DELETE'});loadMemories();}};edit.onclick=async()=>{const v=prompt('Novo valor:',item.value);if(v){await api('/api/memories/'+encodeURIComponent(item.key),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:v})});loadMemories();}};card.append(key,value,edit,del);list.append(card);});}
document.getElementById('memory-search').oninput=e=>{const q=e.target.value.toLowerCase();renderMemories(memoryData.filter(x=>(x.key+' '+x.value).toLowerCase().includes(q)));};
document.getElementById('refresh-memories').onclick=loadMemories;

async function loadProfile(){const p=await api('/api/profile');document.getElementById('relationship').textContent=p.relationship;for(const key of ['trust','patience']){const value=Math.round(p[key]);document.getElementById(key+'-value').textContent=value+'%';document.getElementById(key+'-meter').style.width=value+'%';}}

async function loadHistory(){const list=document.getElementById('history-list'),data=await api('/api/history');list.innerHTML='';if(!data.length){list.innerHTML='<div class="empty">O histórico está vazio.</div>';return;}[...data].reverse().forEach(item=>{const el=document.createElement('div');el.className='history-item '+item.role;const who=document.createElement('b'),text=document.createElement('span'),time=document.createElement('time');who.textContent=item.role==='assistant'?'Laura':'Nicolas';text.textContent=item.content;time.textContent=item.created_at;el.append(who,text,time);list.append(el);});}
document.getElementById('clear-history').onclick=async()=>{if(confirm('Apagar todo o histórico? As memórias serão mantidas.')){await api('/api/history',{method:'DELETE'});loadHistory();}};
async function loadLearning(){const [data,diag]=await Promise.all([api('/api/model'),api('/api/diagnostics')]),list=document.getElementById('training-list');document.getElementById('example-count').textContent=data.count+' exemplos seus';list.innerHTML='';if(!data.custom_examples.length)list.innerHTML='<div class="empty">Você ainda não corrigiu nenhuma intenção.</div>';data.custom_examples.forEach(item=>{const el=document.createElement('div');el.className='history-item';const label=document.createElement('b'),text=document.createElement('span'),time=document.createElement('time');label.textContent=item.label;text.textContent=item.text;time.textContent=item.created_at;el.append(label,text,time);list.append(el);});document.getElementById('diagnostics').innerHTML=`<h2>Laura ${diag.version}</h2><p style="margin:8px 0">Banco: ${diag.integrity==='ok'?'Íntegro':'Verificar'}</p><small>Memórias: ${diag.counts.facts} • Respostas: ${diag.counts.learned_answers} • Exemplos: ${diag.counts.training_examples} • Mensagens: ${diag.counts.messages} • Alterações: ${diag.counts.fact_history}</small>`;}
document.getElementById('export-backup').onclick=async()=>{const data=await api('/api/export'),blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='laura-backup-1.10.json';a.click();URL.revokeObjectURL(a.href);};
document.getElementById('import-backup').onchange=async e=>{const file=e.target.files[0];if(file&&file.size>200*1024*1024){alert('O backup deve ter no máximo 200 MB.');e.target.value='';return;}if(!file||!confirm('Restaurar este backup? Os dados atuais serão substituídos pelos dados do arquivo.'))return;try{const data=JSON.parse(await file.text());const result=await api('/api/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),optimized=result.thumbnails_compacted?` ${result.thumbnails_compacted} miniaturas antigas também foram compactadas.`:'';alert(`Cópia anterior guardada. Use ‘Baixar cópia anterior’ para recuperá-la. Backup restaurado: ${result.facts} memórias, ${result.answers} respostas, ${result.examples} exemplos, ${result.history} mensagens e ${result.visual_examples||0} imagens.${optimized}`);loadLearning();loadVisualCategories();}catch(error){alert('Não foi possível importar o backup: '+error.message);}finally{e.target.value='';}};

let currentImageData='',currentRecognitionId=0,imageSelection=0;
const imageDrop=document.getElementById('image-drop'),imagePreview=document.getElementById('image-preview'),dropHint=document.getElementById('drop-hint'),visionResult=document.getElementById('vision-result'),analyzeButton=document.getElementById('analyze-image'),teachButton=document.getElementById('teach-image');
function selectImage(file){
  if(!file)return;
  if(!file.type.startsWith('image/')){visionResult.textContent='Escolha um arquivo de imagem.';return;}
  if(file.size>20*1024*1024){visionResult.textContent='A imagem deve ter no máximo 20 MB.';return;}
  const selection=++imageSelection;currentRecognitionId=0;currentImageData='';analyzeButton.disabled=true;teachButton.disabled=true;visionResult.textContent='Lendo imagem...';
  const reader=new FileReader();reader.onload=()=>{if(selection!==imageSelection)return;currentImageData=reader.result;imagePreview.src=currentImageData;imagePreview.hidden=false;dropHint.hidden=true;analyzeButton.disabled=false;teachButton.disabled=false;visionResult.textContent='Imagem pronta. Você pode analisar ou ensinar uma categoria.';};reader.readAsDataURL(file);
}
for(const id of ['image-file','image-camera'])document.getElementById(id).onchange=e=>selectImage(e.target.files[0]);
function fileToDataURL(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('Não consegui ler uma das imagens.'));reader.readAsDataURL(file);});}
document.getElementById('image-batch').onchange=async e=>{
  const input=e.target,label=document.getElementById('image-label').value.trim(),files=[...input.files].slice(0,100);
  if(input.files.length>100){visionResult.textContent='Escolha no máximo 100 fotos por lote. Você pode enviar outro lote depois.';input.value='';return;}
  if(!label){visionResult.textContent='Digite a categoria antes de escolher várias fotos.';input.value='';return;}
  if(!files.length)return;
  input.disabled=true;
  let learned=0,duplicates=0,failures=0;
  for(let index=0;index<files.length;index++){
    const file=files[index];visionResult.textContent=`Ensinando ${index+1} de ${files.length} imagens...`;
    if(file.size>20*1024*1024){failures++;continue;}
    try{const image=await fileToDataURL(file),data=await api('/api/vision/teach',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image,label})});if(data.duplicate)duplicates++;else learned++;}catch{failures++;}
  }
  const parts=[`${learned} aprendida${learned===1?'':'s'}`];if(duplicates)parts.push(`${duplicates} repetida${duplicates===1?'':'s'} ignorada${duplicates===1?'':'s'}`);if(failures)parts.push(`${failures} com erro`);
  visionResult.textContent=`Lote concluído para “${label}”: ${parts.join(', ')}.`;input.value='';input.disabled=false;loadVisualCategories();
};
document.getElementById('image-package').onchange=async e=>{
  const input=e.target,file=input.files[0],limit=Number(document.getElementById('package-limit').value);
  if(!file)return;
  if(file.size>100*1024*1024){visionResult.textContent='O pacote ZIP deve ter no máximo 100 MB.';input.value='';return;}
  if(!file.name.toLowerCase().endsWith('.zip')){visionResult.textContent='Escolha um arquivo no formato ZIP.';input.value='';return;}
  if(!confirm(`Importar até ${limit} imagens de cada categoria encontrada no pacote?`)){input.value='';return;}
  input.disabled=true;visionResult.textContent='Abrindo o pacote e aprendendo as categorias. Isso pode levar alguns minutos...';
  try{const archive=await fileToDataURL(file),data=await api('/api/vision/import-package',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({archive,limit_per_category:limit})}),categories=Object.entries(data.categories).map(([name,count])=>`${name}: ${count}`).join(' • ');visionResult.textContent=`Pacote concluído: ${data.learned} imagens aprendidas em ${Object.keys(data.categories).length} categorias. ${data.duplicates} repetidas, ${data.skipped} inválidas e ${data.limited} acima do limite foram ignoradas.${categories?' '+categories:''}`;loadVisualCategories();}
  catch(error){visionResult.textContent='Não foi possível importar: '+error.message;}
  finally{input.disabled=false;input.value='';}
};
imageDrop.onclick=e=>{if(e.target===imageDrop||e.target===dropHint||dropHint.contains(e.target))document.getElementById('image-file').click();};
imageDrop.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();document.getElementById('image-file').click();}};
for(const event of ['dragenter','dragover'])imageDrop.addEventListener(event,e=>{e.preventDefault();imageDrop.classList.add('drag');});
for(const event of ['dragleave','drop'])imageDrop.addEventListener(event,e=>{e.preventDefault();imageDrop.classList.remove('drag');});
imageDrop.addEventListener('drop',e=>selectImage(e.dataTransfer.files[0]));

function renderVisionResult(data){
  currentRecognitionId=data.recognition_id||0;
  visionResult.innerHTML='';const text=document.createElement('p');text.textContent=data.text;visionResult.append(text);
  if(data.alternatives?.length){const title=document.createElement('small');title.textContent='Melhores possibilidades:';const choices=document.createElement('div');choices.className='vision-choices';data.alternatives.forEach(item=>{const button=document.createElement('button');button.textContent=`${item.label} • ${Math.round(item.confidence*100)}%`;button.onclick=()=>correctVisualCategory(item.label);choices.append(button);});visionResult.append(title,choices);}
  {const correction=document.createElement('button');correction.className='vision-correct';correction.textContent='Corrigir categoria';correction.onclick=()=>{const label=prompt('Qual é a categoria correta?');if(label)correctVisualCategory(label);};visionResult.append(correction);}
}
async function correctVisualCategory(label){if(!currentImageData)return;visionResult.textContent=`Aprendendo a correção “${label}”...`;try{const data=await api('/api/vision/teach',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:currentImageData,label,recognition_id:currentRecognitionId})});visionResult.textContent=data.duplicate?`Correção salva. A foto já existia em “${label}”, então não foi duplicada.`:`Correção salva: esta imagem agora é “${label}”.`;currentRecognitionId=0;loadVisualCategories();}catch(error){visionResult.textContent=error.message;}}
analyzeButton.onclick=async()=>{const selection=imageSelection,image=currentImageData;if(!image)return;visionResult.textContent='Analisando localmente...';analyzeButton.disabled=true;try{const data=await api('/api/vision/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image})});if(selection===imageSelection)renderVisionResult(data);}catch(error){if(selection===imageSelection)visionResult.textContent=error.message;}finally{if(selection===imageSelection)analyzeButton.disabled=false;}};
teachButton.onclick=async()=>{const label=document.getElementById('image-label').value.trim();if(!label){visionResult.textContent='Digite o nome da categoria antes de ensinar.';return;}visionResult.textContent='Aprendendo esta imagem...';teachButton.disabled=true;try{const data=await api('/api/vision/teach',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:currentImageData,label})});visionResult.textContent=data.duplicate?`Esta foto já existe em “${data.label}” e não foi duplicada.`:`Aprendi esta imagem como “${data.label}”. Para ficar mais precisa, ensine outras fotos da mesma categoria.`;if(!data.duplicate)document.getElementById('image-label').value='';loadVisualCategories();}catch(error){visionResult.textContent=error.message;}finally{teachButton.disabled=false;}};

async function renameVisualCategory(oldLabel){
  const newLabel=prompt(`Novo nome para “${oldLabel}”:`,oldLabel);
  if(!newLabel||newLabel.trim()===oldLabel)return;
  try{const data=await api('/api/vision/categories/'+encodeURIComponent(oldLabel),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({label:newLabel})});if(!data.renamed)throw new Error('Categoria não encontrada.');document.getElementById('visual-items-section').hidden=true;loadVisualCategories();}catch(error){alert(error.message);}
}

async function loadVisualCategories(){
  const list=document.getElementById('visual-categories'),[data,report,accuracy]=await Promise.all([api('/api/vision/examples'),api('/api/vision/report'),api('/api/vision/accuracy')]),reports=new Map(report.map(item=>[item.label,item]));
  const total=data.reduce((sum,item)=>sum+item.count,0);document.getElementById('visual-count').textContent=total+' '+(total===1?'imagem':'imagens');
  const source=document.getElementById('generation-source'),selectedSource=source.value;source.innerHTML='<option value="">Somente descrição</option>';data.forEach(item=>{const option=document.createElement('option');option.value=item.label;option.textContent=`Aprendizado: ${item.label} (${item.count})`;option.disabled=item.count<3;source.append(option);});if([...source.options].some(option=>option.value===selectedSource&&!option.disabled))source.value=selectedSource;
  const stats=document.getElementById('visual-accuracy');stats.innerHTML='';
  const title=document.createElement('h2'),summary=document.createElement('p'),detail=document.createElement('small');title.textContent='Precisão acompanhada';summary.textContent=`${accuracy.total_analyses} análises • ${accuracy.unknown} imagens recusadas`;detail.textContent=accuracy.evaluated?`${Math.round(accuracy.accuracy*100)}% de acerto em ${accuracy.evaluated} correções avaliadas`:'Corrija classificações para a Laura medir a precisão.';stats.append(title,summary,detail);
  if(accuracy.confusions?.length){const confusions=document.createElement('div');confusions.className='confusion-list';confusions.textContent='Confusões mais frequentes: '+accuracy.confusions.map(item=>`${item.actual} → ${item.predicted} (${item.count})`).join(' • ');stats.append(confusions);}
  list.innerHTML='';if(!data.length){list.innerHTML='<div class="empty">Nenhuma categoria visual ensinada ainda.</div>';return;}
  data.forEach(item=>{const card=document.createElement('article');card.className='memory-card';if(item.thumbnail){const img=document.createElement('img');img.className='visual-thumb';img.src=item.thumbnail;card.append(img);}const name=document.createElement('small'),count=document.createElement('p'),quality=document.createElement('span'),tip=document.createElement('div'),actions=document.createElement('div'),view=document.createElement('button'),rename=document.createElement('button'),del=document.createElement('button'),status=reports.get(item.label);name.textContent=item.label;count.textContent=item.count+' '+(item.count===1?'exemplo':'exemplos');quality.className='quality-badge '+(status?.quality||'iniciante');quality.textContent=status?.quality||'iniciante';tip.className='training-tip';tip.textContent=status?.tip||'';actions.className='category-actions';view.textContent='Ver fotos';view.onclick=()=>loadVisualItems(item.label);rename.textContent='Renomear';rename.onclick=()=>renameVisualCategory(item.label);del.textContent='Excluir categoria';del.onclick=async()=>{if(confirm(`Apagar a categoria “${item.label}”?`)){await api('/api/vision/categories/'+encodeURIComponent(item.label),{method:'DELETE'});loadVisualCategories();}};actions.append(view,rename,del);card.append(name,count,quality,tip,actions);list.append(card);});
}

async function loadVisualItems(label){const section=document.getElementById('visual-items-section'),list=document.getElementById('visual-items'),items=await api('/api/vision/items?label='+encodeURIComponent(label));document.getElementById('visual-items-title').textContent='Exemplos de '+label;section.hidden=false;list.innerHTML='';items.forEach(item=>{const card=document.createElement('article'),img=document.createElement('img'),del=document.createElement('button');card.className='visual-item';img.src=item.thumbnail;img.alt=item.label;del.textContent='×';del.onclick=async()=>{if(confirm('Excluir somente esta imagem?')){await api('/api/vision/examples/'+item.id,{method:'DELETE'});loadVisualItems(label);loadVisualCategories();}};card.append(img,del);list.append(card);});section.scrollIntoView({behavior:'smooth'});}
document.getElementById('close-visual-items').onclick=()=>{document.getElementById('visual-items-section').hidden=true;};

let generationCount=0, lastGeneration=null, lastCreated=null;
async function rateImage(rating){
  if(!lastCreated)return;
  const good=document.getElementById('rate-good'),bad=document.getElementById('rate-bad');
  const status=document.getElementById('rating-info');good.disabled=true;bad.disabled=true;document.getElementById('undo-rating').disabled=true;
  document.getElementById('generate-image').disabled=true;
  document.getElementById('repeat-image').disabled=true;
  try{
    const data=await api('/api/vision/rate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      image:lastCreated.image,generation_id:lastCreated.generation_id,
      context:lastCreated.context,rating})});
    document.getElementById('undo-rating').hidden=false;
    good.classList.toggle('selected',rating==='good');bad.classList.toggle('selected',rating==='bad');
    status.textContent=rating==='good'
      ?`Anotei que ficou boa. Nas próximas variações desta categoria vou priorizar resultados parecidos. (${data.counts.good} boas, ${data.counts.bad} a melhorar)`
      :`Anotei para melhorar. Nas próximas variações desta categoria vou testar opções diferentes. (${data.counts.good} boas, ${data.counts.bad} a melhorar)`;
  }catch(error){status.textContent=error.message;}
  finally{document.getElementById('undo-rating').disabled=false;good.disabled=false;bad.disabled=false;document.getElementById('generate-image').disabled=false;document.getElementById('repeat-image').disabled=!lastGeneration;}
}
document.getElementById('rate-good').onclick=()=>rateImage('good');
document.getElementById('rate-bad').onclick=()=>rateImage('bad');
async function createImage(repeat=false){
  const button=document.getElementById('generate-image'),repeatButton=document.getElementById('repeat-image');
  const image=document.getElementById('generated-image'),download=document.getElementById('download-image');
  const info=document.getElementById('generation-info');
  const prompt=document.getElementById('image-prompt').value.trim();
  const learnedLabel=document.getElementById('generation-source').value;
  if(!prompt&&!learnedLabel){alert('Descreva a imagem ou selecione uma categoria aprendida.');return;}
  const size=Number(document.getElementById('generation-size').value);
  const format=document.getElementById('generation-format').value;
  const request={prompt,learned_label:learnedLabel,width:format==='portrait'?Math.round(size*.75):size,
    height:format==='landscape'?Math.round(size*.75):size,
    quality:document.getElementById('generation-quality').value,
    use_feedback:document.getElementById('use-image-feedback').checked,
    variation:document.getElementById('generation-variation').value,
    seed:repeat?`${Date.now()}-${++generationCount}`:
      document.getElementById('generation-code').value.trim()||`${Date.now()}-${++generationCount}`};
  if(repeat&&lastCreated)request.reference_image=lastCreated.image;
  button.disabled=true;repeatButton.disabled=true;document.getElementById('undo-rating').disabled=true;
  document.getElementById('rate-good').disabled=true;
  document.getElementById('rate-bad').disabled=true;
  const started=performance.now();
  button.textContent='Criando localmente...';
  info.textContent=request.learned_label?`Criando a partir de “${request.learned_label}”...`:'Criando arte a partir da descrição...';
  try {
    const data=await api('/api/vision/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
    image.src=data.image;image.hidden=false;download.href=data.image;download.hidden=false;download.download=`laura-${Date.now()}-${request.width}x${request.height}.png`;
    lastGeneration=request;lastCreated=data;document.getElementById('undo-rating').hidden=true;
    document.getElementById('rating-actions').hidden=false;
    document.getElementById('rating-info').hidden=false;
    document.getElementById('rating-info').textContent='Avalie esta imagem para orientar as próximas variações desta categoria.';
    document.getElementById('rate-good').classList.remove('selected');
    document.getElementById('rate-bad').classList.remove('selected');
    info.textContent=data.mode==='scene'
      ? `Cena: ${data.label} em ${data.scene}. Código: ${request.seed}.`
      : data.mode==='learned'
        ? `Criada com ${data.examples_used} exemplos de “${data.label}”. Estilo: ${request.variation}. Código: ${request.seed}.`
        : `Paisagem desenhada localmente. Código: ${request.seed}.`;
    info.textContent+=` ${request.width} × ${request.height} pixels • ${((performance.now()-started)/1000).toFixed(1)} s.`;
  } catch(error){info.textContent=error.message;}
  finally {document.getElementById('undo-rating').disabled=false;button.disabled=false;repeatButton.disabled=!lastGeneration;button.textContent='Criar imagem';document.getElementById('rate-good').disabled=!lastCreated;document.getElementById('rate-bad').disabled=!lastCreated;}
}
document.getElementById('generate-image').onclick=()=>createImage();
document.getElementById('repeat-image').onclick=()=>createImage(true);

document.getElementById('undo-rating').onclick=async()=>{
  if(!lastCreated)return;
  const controls=['undo-rating','rate-good','rate-bad','generate-image','repeat-image'];
  controls.forEach(id=>document.getElementById(id).disabled=true);
  try{
    await api('/api/vision/ratings/'+encodeURIComponent(lastCreated.generation_id),{method:'DELETE'});
    document.getElementById('undo-rating').hidden=true;
    ['rate-good','rate-bad'].forEach(id=>document.getElementById(id).classList.remove('selected'));
    document.getElementById('rating-info').textContent='Avaliação desfeita. Esta imagem deixou de orientar as próximas criações.';
  }catch(error){document.getElementById('rating-info').textContent=error.message;}
  finally{controls.forEach(id=>document.getElementById(id).disabled=false);}
};
document.getElementById('export-previous-backup').onclick=async()=>{
  try{
    const data=await api('/api/export-previous-backup');
    const blob=new Blob([JSON.stringify(data)],{type:'application/json'}),a=document.createElement('a');
    a.href=URL.createObjectURL(blob);a.download='laura-antes-da-importacao.json';a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href),1000);
  }catch(error){alert(error.message);}
};
