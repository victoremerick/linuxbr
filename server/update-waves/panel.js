'use strict';

const element = (id) => document.getElementById(id);
const labels = {
  authorized: 'Autorizada', completed: 'Concluída', failed: 'Falhou', restored: 'Restaurada',
  pending: 'Aguardando', expired: 'Expirada', received: 'Recebida', declined: 'Recusada',
  pilot: 'Piloto', general: 'Geral',
  promote: 'Promoção ao grupo geral', pause: 'Pausa', resume: 'Retomada',
  retire: 'Retirada da revisão', diagnostic: 'Diagnóstico solicitado',
  'delete-diagnostic': 'Diagnóstico descartado', 'assign-policy': 'Política atribuída',
  'clear-policy': 'Atribuição retirada', 'disable-device': 'Dispositivo desabilitado',
  'enable-device': 'Dispositivo habilitado',
  'set-window': 'Janela cadastrada', 'reschedule-window': 'Janela reagendada',
  'clear-window': 'Janela removida',
};
let currentRevision = null;
let busy = false;
let revisionsByName = new Map();
let canManageWindows = false;

async function api(path, payload) {
  const options = payload === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
  };
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Operação não concluída.');
  return result;
}

function addRow(table, cells) {
  const row = table.insertRow();
  for (const value of cells) row.insertCell().textContent = value ?? '—';
  return row;
}

function button(cell, label, action) {
  const control = document.createElement('button');
  control.type = 'button';
  control.textContent = label;
  control.addEventListener('click', action);
  cell.append(control);
}

function when(value) {
  return value ? new Date(value).toLocaleString('pt-BR') : '—';
}

function contact(value) {
  return when(value) + (!value || Date.now() - Date.parse(value) > 86400000 ? ' · sem contato recente' : '');
}

const utcDate = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short', timeStyle: 'medium', timeZone: 'UTC',
});

function windowRange(window) {
  return utcDate.format(new Date(window.starts_at)) + ' até ' +
    utcDate.format(new Date(window.ends_at)) + ' (UTC)';
}

function localOffset() {
  const minutes = -new Date().getTimezoneOffset();
  const absolute = Math.abs(minutes);
  const hours = String(Math.floor(absolute / 60)).padStart(2, '0');
  const remainder = String(absolute % 60).padStart(2, '0');
  return (minutes < 0 ? '-' : '+') + hours + ':' + remainder;
}

function selectedRevision() {
  return revisionsByName.get(element('revisions').value);
}

function updateWindowButtons() {
  const revision = selectedRevision();
  element('window-editor').disabled = busy || !canManageWindows || !revision;
  element('clear-window').disabled = !revision?.window;
}

function showWindow() {
  const revision = selectedRevision();
  const window = revision?.window;
  element('window-summary').textContent = !revision ? 'Selecione uma revisão cadastrada.'
    : revision.name + ' · ' + (window ? windowRange(window) : 'Sem janela de manutenção.');
  element('window-start').value = window?.starts_at.slice(0, 19) || '';
  element('window-end').value = window?.ends_at.slice(0, 19) || '';
  element('window-offset').value = window ? '+00:00' : localOffset();
  updateWindowButtons();
}

async function refresh() {
  const state = await api('/v1/admin/status');
  const {active, revisions, devices, diagnostics, audit, policies, operator_role: role} = state;
  const releaseAllowed = role === 'admin' || role === 'release';
  const supportAllowed = role === 'admin' || role === 'support';
  canManageWindows = releaseAllowed;
  currentRevision = active.revision;
  const windowStates = {scheduled: 'Aguardando abertura da janela', open: 'Janela aberta', closed: 'Janela encerrada'};
  const windowState = windowStates[active.window_state];
  element('active').textContent = currentRevision
    ? currentRevision + ' · ' + (active.paused ? 'Pausada' : active.general ? 'Geral' : 'Piloto')
      + (windowState ? ' · ' + windowState : '')
    : 'Nenhuma revisão ativa.';
  revisionsByName = new Map(revisions.map((revision) => [revision.name, revision]));
  const choices = element('revisions');
  const selected = choices.value;
  choices.replaceChildren();
  for (const revision of revisions) {
    const option = document.createElement('option');
    option.value = revision.name;
    option.textContent = revision.name;
    choices.append(option);
  }
  if (revisions.some((revision) => revision.name === selected)) choices.value = selected;
  else if (revisionsByName.has(currentRevision)) choices.value = currentRevision;
  showWindow();
  const policyChoices = element('policies');
  const selectedPolicy = policyChoices.value;
  policyChoices.replaceChildren();
  for (const policy of policies) {
    const option = document.createElement('option');
    option.value = policy.name;
    option.textContent = policy.name;
    policyChoices.append(option);
  }
  if (policies.some((policy) => policy.name === selectedPolicy)) policyChoices.value = selectedPolicy;
  element('pilot').disabled = !releaseAllowed || !revisions.length;
  element('promote').disabled = !releaseAllowed || !currentRevision || !!active.general || !!active.paused;
  element('pause').disabled = !releaseAllowed || !currentRevision || !!active.paused;
  element('resume').disabled = !releaseAllowed || !currentRevision || !active.paused;
  element('retire').disabled = !releaseAllowed || !currentRevision;

  element('devices').replaceChildren();
  for (const device of devices) {
    const row = addRow(element('devices'), [
      device.name, labels[device.wave], device.release,
      device.free_bytes === null ? '—' : (device.free_bytes / 1073741824).toFixed(1) + ' GiB',
      device.reboot_pending === null ? '—' : device.reboot_pending ? 'Pendente' : 'Em dia',
      contact(device.last_contact), labels[device.state] || 'Aguardando', device.confirmed_revision,
      device.profile,
    ]);
    const actions = row.insertCell();
    if (device.enabled) {
      if (supportAllowed) button(actions, 'Solicitar diagnóstico', () => change('diagnostic', device.name));
      if (role === 'admin') {
        if (policies.length) button(actions, 'Atribuir política', () => change('assign-policy', device.name));
        if (device.profile) button(actions, 'Retirar atribuição', () => change('clear-policy', device.name));
        button(actions, 'Desabilitar', () => change('disable-device', device.name));
      }
    } else if (role === 'admin') {
      button(actions, 'Habilitar', () => change('enable-device', device.name));
    }
  }
  element('diagnostics').replaceChildren();
  for (const item of diagnostics) {
    const row = addRow(element('diagnostics'), [item.device, when(item.created),
      when(item.expires), labels[item.state]]);
    const actions = row.insertCell();
    if (supportAllowed && item.state === 'received') button(actions, 'Ver relatório', async () => {
      try {
        const report = await api('/v1/admin/report', {request_id: item.id});
        const preview = element('report');
        preview.textContent = JSON.stringify(report, null, 2);
        preview.hidden = false;
        preview.focus();
      } catch (error) { element('message').textContent = error.message; }
    });
    if (supportAllowed) button(actions, 'Descartar', () => change('delete-diagnostic', item.id));
  }
  element('audit').replaceChildren();
  for (const event of audit) addRow(element('audit'), [when(event.checked), event.actor,
    labels[event.action] || event.action, event.target]);
}

const actions = {
  pilot: 'Liberar ao piloto', promote: 'Promover para geral', pause: 'Pausar', resume: 'Retomar',
  retire: 'Retirar revisão', diagnostic: 'Solicitar diagnóstico', 'delete-diagnostic': 'Descartar solicitação',
  'disable-device': 'Desabilitar dispositivo', 'enable-device': 'Habilitar dispositivo',
  'assign-policy': 'Atribuir política', 'clear-policy': 'Retirar atribuição de política',
  'set-window': 'Salvar janela', 'clear-window': 'Remover janela',
};
async function change(action, target, fields = {}, confirmation = undefined) {
  if (busy || !target || !window.confirm(confirmation ?? actions[action] + ' · ' + target + '?')) return;
  const feedback = element(action === 'set-window' || action === 'clear-window' ? 'window-feedback' : 'message');
  if (feedback.id === 'window-feedback') element('message').textContent = '';
  busy = true;
  updateWindowButtons();
  try {
    const payload = {action, target, ...fields};
    if (action === 'assign-policy') payload.profile = element('policies').value;
    await api('/v1/admin/action', payload);
    element('report').hidden = true;
    element('report').textContent = '';
    await refresh();
    feedback.textContent = 'Alteração registrada.';
  } catch (error) { feedback.textContent = error.message; }
  finally {
    busy = false;
    updateWindowButtons();
  }
}

function saveWindow() {
  const revision = selectedRevision();
  if (!canManageWindows || !revision) return;
  const start = element('window-start');
  const end = element('window-end');
  const offset = element('window-offset');
  if (!start.reportValidity() || !end.reportValidity() || !offset.reportValidity()) return;
  const timezone = offset.value.trim();
  if (!/^[+-](?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(timezone)) {
    element('window-feedback').textContent = 'Informe o fuso no formato +hh:mm ou -hh:mm.';
    offset.focus();
    return;
  }
  const proposed = {starts_at: start.value + timezone, ends_at: end.value + timezone};
  if (!(Date.parse(proposed.ends_at) > Date.parse(proposed.starts_at))) {
    element('window-feedback').textContent = 'O fim da janela precisa ser depois do início.';
    end.focus();
    return;
  }
  const verb = revision.window ? 'Reagendar' : 'Cadastrar';
  return change('set-window', revision.name, {window: proposed, expected_window: revision.window},
    verb + ' janela de ' + revision.name + '?\n\n' + windowRange(proposed));
}

function clearWindow() {
  const revision = selectedRevision();
  if (!canManageWindows || !revision?.window) return;
  return change('clear-window', revision.name, {expected_window: revision.window},
    'Remover a janela de ' + revision.name + '?\n\n' +
    'A revisão poderá voltar a autorizar atualizações fora desse horário se a onda estiver liberada.');
}

async function reload() {
  try {
    await refresh();
    element('message').textContent = 'Painel atualizado.';
  } catch (error) { element('message').textContent = error.message; }
}

element('refresh').addEventListener('click', reload);
element('revisions').addEventListener('change', () => {
  element('window-feedback').textContent = '';
  showWindow();
});
element('set-window').addEventListener('click', saveWindow);
element('clear-window').addEventListener('click', clearWindow);
element('pilot').addEventListener('click', () => change('pilot', element('revisions').value));
for (const action of ['promote', 'pause', 'resume', 'retire']) {
  element(action).addEventListener('click', () => change(action, currentRevision));
}
reload();
