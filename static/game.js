const board = document.getElementById('game-board');
const gameStatus = document.getElementById('game-status');
const gameControls = document.querySelectorAll('[data-move], #game-decide, #game-new');
let gameBusy = false;
let lastGameState = null;

function renderGame(state) {
  lastGameState = state;
  board.style.gridTemplateColumns = `repeat(${state.size}, 1fr)`;
  const walls = new Set(state.walls.map(([x,y]) => `${x},${y}`));
  board.replaceChildren();
  for(let y=0; y<state.size; y++) for(let x=0; x<state.size; x++) {
    const cell = document.createElement('div');
    cell.className = 'game-cell';
    if(walls.has(`${x},${y}`)) cell.classList.add('wall');
    if(x===state.goal[0] && y===state.goal[1]) {cell.classList.add('goal');cell.textContent='★';}
    if(x===state.player[0] && y===state.player[1]) {cell.classList.add('player');cell.textContent='●';}
    board.append(cell);
  }
  document.getElementById('game-steps').textContent=`Passos: ${state.steps}`;
  gameStatus.textContent=state.done?'Laura chegou ao objetivo!':
    (state.last_move?.message || 'Leve o círculo até a estrela.');
  const history=document.getElementById('game-history');
  history.replaceChildren();
  state.history.slice().reverse().forEach(item=>{
    const row=document.createElement('p');row.textContent=item.message;history.append(row);
  });
  document.querySelectorAll('[data-move], #game-decide').forEach(button=>button.disabled=state.done);
}

async function gameRequest(path, payload={}) {
  if(gameBusy)return;
  gameBusy=true;
  gameControls.forEach(button=>button.disabled=true);
  try {
    renderGame(await api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}));
  } catch(error) {gameStatus.textContent=error.message;}
  finally {
    gameBusy=false;
    // Uma partida encerrada mantém os controles de movimento desativados.
    if(lastGameState) renderGame(lastGameState);
    document.getElementById('game-new').disabled=false;
  }
}

document.querySelectorAll('[data-move]').forEach(button=>button.onclick=()=>
  gameRequest('/api/game/move',{direction:button.dataset.move}));
document.getElementById('game-decide').onclick=()=>gameRequest('/api/game/decide');
document.getElementById('game-new').onclick=()=>gameRequest('/api/game/new');
api('/api/game').then(renderGame).catch(error=>gameStatus.textContent=error.message);
