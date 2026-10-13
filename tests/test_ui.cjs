// Run with node tests/test_ui.cjs; no browser dependencies required.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const elements=new Map();
function element(){return {value:'',disabled:false,hidden:false,src:'',textContent:'',dataset:{},classList:{add(){},remove(){},toggle(){}},addEventListener(){},append(){},click(){},contains(){return false;},focus(){},scrollIntoView(){}};}
const get=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
const calls=[];
let responseHandler=async(url,options)=>({ok:true,json:async()=>({image:'data:image/png;base64,test',mode:'learned',examples_used:3,label:'cavalo',context:'learned:cavalo',generation_id:'test-id',removed:true})});
const context=vm.createContext({document:{querySelectorAll:()=>[],getElementById:get,createElement:element},fetch:async(url,options)=>{calls.push({url,options});return responseHandler(url,options);},performance:{now:()=>1},Date,console,setTimeout,URL,Blob,alert:message=>{throw Error(message);},confirm:()=>true,FileReader:class{readAsDataURL(file){this.result=file.data;this.onload();}}});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8'),context);
(async()=>{
  get('image-prompt').value='cavalo';get('generation-source').value='cavalo';get('generation-size').value='512';get('generation-format').value='square';get('generation-quality').value='equilibrada';get('generation-variation').value='equilibrado';get('use-image-feedback').checked=true;
  await vm.runInContext('createImage()',context);
  get('generation-size').value='1536';get('generation-format').value='portrait';get('generation-quality').value='detalhada';get('generation-variation').value='criativo';
  await vm.runInContext('createImage(true)',context);
  const body=JSON.parse(calls.at(-1).options.body);
  assert.equal(body.width,1152);assert.equal(body.height,1536);assert.equal(body.quality,'detalhada');assert.equal(body.variation,'criativo');assert.equal(body.reference_image,'data:image/png;base64,test');
  assert.notEqual(body.seed,JSON.parse(calls[0].options.body).seed);
  vm.runInContext("currentRecognitionId=99;selectImage({type:'image/png',size:10,data:'photo-A'})",context);
  assert.equal(vm.runInContext('currentRecognitionId',context),0);
  let resolve;
  responseHandler=()=>new Promise(r=>resolve=r);
  const pending=get('analyze-image').onclick();
  vm.runInContext("selectImage({type:'image/png',size:10,data:'photo-B'})",context);
  resolve({ok:true,json:async()=>({recognition_id:123,text:'stale result',known:true})});
  await pending;
  assert.equal(vm.runInContext('currentRecognitionId',context),0);
  assert.notEqual(get('vision-result').textContent,'stale result');
  responseHandler=async()=>({ok:true,json:async()=>({removed:true})});
  await get('undo-rating').onclick();
  assert.equal(calls.at(-1).options.method,'DELETE');assert.equal(get('undo-rating').hidden,true);
  console.log('UI OK: variation settings, fresh seed, photo identity, stale response, undo rating');
})().catch(error=>{console.error(error);process.exitCode=1;});
