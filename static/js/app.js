// Z-API WhatsApp Sender - Main JavaScript

const API_BASE = '/api';

// Utility function for API calls
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        let data;
        try {
            data = await response.clone().json();
        } catch (e) {
            const text = await response.text();
            try {
                data = JSON.parse(text);
            } catch {
                data = { error: text || 'API error (non-JSON response)' };
            }
        }
        
        if (!response.ok) {
            const msg = data.error || data.message || `HTTP ${response.status}`;
            throw new Error(msg);
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        showAlert('danger', error.message || 'Failed to fetch');
        throw error;
    }
}

// Show alert message
function showAlert(type, message) {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    const mainContainer = document.querySelector('main.container');
    mainContainer.insertAdjacentHTML('afterbegin', alertHtml);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const alert = mainContainer.querySelector('.alert');
        if (alert) {
            alert.remove();
        }
    }, 5000);
}

// Load contacts
async function loadContacts() {
    try {
        const data = await apiCall('/contacts');
        const tbody = document.getElementById('contactsTableBody');
        
        if (tbody) {
            tbody.innerHTML = data.contacts.map(contact => `
                <tr>
                    <td>${contact.name}</td>
                    <td>${contact.whatsapp_number}</td>
                    <td>${contact.group_name || '-'}</td>
                    <td>
                        <button class="btn btn-sm btn-warning" onclick="editContact(${contact.id})">Editar</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteContact(${contact.id})">Excluir</button>
                    </td>
                </tr>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading contacts:', error);
    }
}

// Load groups
async function loadGroups() {
    try {
        const data = await apiCall('/groups');
        const select = document.getElementById('contactGroup');
        
        if (select) {
            select.innerHTML = '<option value="">Sem grupo</option>' +
                data.groups.map(group => `<option value="${group.id}">${group.name}</option>`).join('');
        }
    } catch (error) {
        console.error('Error loading groups:', error);
    }
}

// Load groups list
async function loadGroupsList() {
    try {
        const data = await apiCall('/groups');
        const tbody = document.getElementById('groupsTableBody');
        
        if (tbody) {
            tbody.innerHTML = data.groups.map(group => `
                <tr>
                    <td>${group.name}</td>
                    <td>${group.description || '-'}</td>
                    <td>${group.contact_count}</td>
                    <td class="d-flex gap-2">
                        <button class="btn btn-sm btn-secondary" onclick="showInviteLink(${group.id})">Link de Cadastro</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteGroup(${group.id})">Excluir</button>
                    </td>
                </tr>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading groups:', error);
    }
}

// Save contact
async function saveContact() {
    const name = document.getElementById('contactName').value;
    const phone = document.getElementById('contactPhone').value;
    const groupId = document.getElementById('contactGroup').value;
    
    try {
        await apiCall('/contacts', {
            method: 'POST',
            body: JSON.stringify({
                name: name,
                whatsapp_number: phone,
                group_id: groupId || null
            })
        });
        
        showAlert('success', 'Contato adicionado com sucesso!');
        
        // Close modal and reload contacts
        const modal = bootstrap.Modal.getInstance(document.getElementById('addContactModal'));
        modal.hide();
        
        document.getElementById('addContactForm').reset();
        loadContacts();
        
    } catch (error) {
        showAlert('danger', `Erro ao adicionar contato: ${error.message}`);
    }
}

// Delete contact
async function deleteContact(id) {
    if (confirm('Tem certeza que deseja excluir este contato?')) {
        try {
            await apiCall(`/contacts/${id}`, { method: 'DELETE' });
            showAlert('success', 'Contato excluído com sucesso!');
            loadContacts();
        } catch (error) {
            showAlert('danger', `Erro ao excluir contato: ${error.message}`);
        }
    }
}

// Save group
async function saveGroup() {
    const name = document.getElementById('groupName').value;
    const description = document.getElementById('groupDescription').value;
    
    try {
        await apiCall('/groups', {
            method: 'POST',
            body: JSON.stringify({
                name: name,
                description: description
            })
        });
        
        showAlert('success', 'Grupo criado com sucesso!');
        
        // Close modal and reload groups
        const modal = bootstrap.Modal.getInstance(document.getElementById('addGroupModal'));
        modal.hide();
        
        document.getElementById('addGroupForm').reset();
        loadGroupsList();
        
    } catch (error) {
        showAlert('danger', `Erro ao criar grupo: ${error.message}`);
    }
}

// Delete group
async function deleteGroup(id) {
    if (confirm('Tem certeza que deseja excluir este grupo? Todos os contatos ficarão sem grupo.')) {
        try {
            await apiCall(`/groups/${id}`, { method: 'DELETE' });
            showAlert('success', 'Grupo excluído com sucesso!');
            loadGroupsList();
        } catch (error) {
            showAlert('danger', `Erro ao excluir grupo: ${error.message}`);
        }
    }
}

// Load contacts for select
async function loadContactsForSelect() {
    try {
        const data = await apiCall('/contacts');
        const select = document.getElementById('contactSelect');
        
        if (select) {
            select.innerHTML = '<option value="">Selecione um contato...</option>' +
                data.contacts.map(contact => 
                    `<option value="${contact.id}">${contact.name} (${contact.whatsapp_number})</option>`
                ).join('');
        }
    } catch (error) {
        console.error('Error loading contacts for select:', error);
    }
}

// Load groups for select
async function loadGroupsForSelect() {
    try {
        const data = await apiCall('/groups');
        const select = document.getElementById('groupSelect');
        
        if (select) {
            select.innerHTML = '<option value="">Selecione um grupo...</option>' +
                data.groups.map(group => 
                    `<option value="${group.id}">${group.name} (${group.contact_count} contatos)</option>`
                ).join('');
        }
    } catch (error) {
        console.error('Error loading groups for select:', error);
    }
}

// Schedule UI toggles - Individual
(function setupIndividualScheduleUI() {
    const toggle = document.getElementById('individualScheduleToggle');
    const options = document.getElementById('individualScheduleOptions');
    const onceRadio = document.getElementById('individualScheduleOnce');
    const cronRadio = document.getElementById('individualScheduleCron');
    const onceFields = document.getElementById('individualOnceFields');
    const cronFields = document.getElementById('individualCronFields');
    if (toggle && options && onceRadio && cronRadio && onceFields && cronFields) {
        toggle.addEventListener('change', () => {
            options.style.display = toggle.checked ? 'block' : 'none';
        });
        const onChange = () => {
            const isOnce = onceRadio.checked;
            onceFields.style.display = isOnce ? 'block' : 'none';
            cronFields.style.display = isOnce ? 'none' : 'block';
        };
        onceRadio.addEventListener('change', onChange);
        cronRadio.addEventListener('change', onChange);
        onChange();
    }
})();

// Send individual message (or schedule)
if (document.getElementById('individualSendForm')) {
    document.getElementById('individualSendForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const contactId = document.getElementById('contactSelect').value;
        const phone = document.getElementById('phoneNumber').value;
        const message = document.getElementById('individualMessage').value;
        const scheduleOn = document.getElementById('individualScheduleToggle')?.checked;
        const scheduleType = document.getElementById('individualScheduleOnce')?.checked ? 'once' : 'cron';
        const runAt = document.getElementById('individualRunAt')?.value;
        const cron = document.getElementById('individualCron')?.value;
        
        if (!contactId && !phone) {
            showAlert('warning', 'Selecione um contato ou digite um número');
            return;
        }
        
        try {
            if (scheduleOn) {
                const payload = {
                    type: 'individual',
                    schedule_type: scheduleType,
                    message: message,
                    contact_id: contactId || null,
                    phone: phone || null,
                    run_at: scheduleType === 'once' ? runAt : null,
                    cron: scheduleType === 'cron' ? cron : null,
                };
                await apiCall('/schedule', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });
                showAlert('success', 'Agendamento criado com sucesso!');
            } else {
                await apiCall('/send', {
                    method: 'POST',
                    body: JSON.stringify({
                        contact_id: contactId || null,
                        phone: phone || null,
                        message: message
                    })
                });
                showAlert('success', 'Mensagem enviada com sucesso!');
            }
            document.getElementById('individualSendForm').reset();
            const options = document.getElementById('individualScheduleOptions');
            if (options) options.style.display = 'none';
        } catch (error) {
            showAlert('danger', `${scheduleOn ? 'Erro ao agendar' : 'Erro ao enviar'}: ${error.message}`);
        }
    });
}

// Schedule UI toggles - Bulk
(function setupBulkScheduleUI() {
    const toggle = document.getElementById('bulkScheduleToggle');
    const options = document.getElementById('bulkScheduleOptions');
    const onceRadio = document.getElementById('bulkScheduleOnce');
    const cronRadio = document.getElementById('bulkScheduleCron');
    const onceFields = document.getElementById('bulkOnceFields');
    const cronFields = document.getElementById('bulkCronFields');
    if (toggle && options && onceRadio && cronRadio && onceFields && cronFields) {
        toggle.addEventListener('change', () => {
            options.style.display = toggle.checked ? 'block' : 'none';
        });
        const onChange = () => {
            const isOnce = onceRadio.checked;
            onceFields.style.display = isOnce ? 'block' : 'none';
            cronFields.style.display = isOnce ? 'none' : 'block';
        };
        onceRadio.addEventListener('change', onChange);
        cronRadio.addEventListener('change', onChange);
        onChange();
    }
})();

// Send bulk messages (or schedule)
if (document.getElementById('bulkSendForm')) {
    document.getElementById('bulkSendForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const groupId = document.getElementById('groupSelect').value;
        const message = document.getElementById('bulkMessage').value;
        const scheduleOn = document.getElementById('bulkScheduleToggle')?.checked;
        const scheduleType = document.getElementById('bulkScheduleOnce')?.checked ? 'once' : 'cron';
        const runAt = document.getElementById('bulkRunAt')?.value;
        const cron = document.getElementById('bulkCron')?.value;
        
        if (!groupId) {
            showAlert('warning', 'Selecione um grupo');
            return;
        }
        
        try {
            if (scheduleOn) {
                const payload = {
                    type: 'group',
                    schedule_type: scheduleType,
                    message: message,
                    group_id: parseInt(groupId),
                    run_at: scheduleType === 'once' ? runAt : null,
                    cron: scheduleType === 'cron' ? cron : null,
                };
                await apiCall('/schedule', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });
                showAlert('success', 'Agendamento em massa criado com sucesso!');
                document.getElementById('bulkSendForm').reset();
            } else {
                const data = await apiCall('/send-bulk', {
                    method: 'POST',
                    body: JSON.stringify({
                        group_id: parseInt(groupId),
                        message: message
                    })
                });
                showAlert('info', 'Envio em massa iniciado! Acompanhe o progresso...');
                const modal = new bootstrap.Modal(document.getElementById('jobStatusModal'));
                modal.show();
                pollJobStatus(data.job_id);
                document.getElementById('bulkSendForm').reset();
            }
            const options = document.getElementById('bulkScheduleOptions');
            if (options) options.style.display = 'none';
        } catch (error) {
            showAlert('danger', `${scheduleOn ? 'Erro ao agendar' : 'Erro ao iniciar envio em massa'}: ${error.message}`);
        }
    });
}

// Poll job status
async function pollJobStatus(jobId) {
    const statusDiv = document.getElementById('jobStatusContent');
    
    const updateStatus = async () => {
        try {
            const data = await apiCall(`/jobs/${jobId}/status`);
            const job = data.job;
            
            let statusHtml = `
                <h5>Status: ${job.status}</h5>
                <div class="progress mb-3">
                    <div class="progress-bar" role="progressbar" 
                         style="width: ${(job.progress / job.total * 100) || 0}%">
                        ${job.progress} / ${job.total}
                    </div>
                </div>
                <p>Enviados: ${job.sent} | Falhas: ${job.failed}</p>
            `;
            
            if (job.status === 'completed' || job.status === 'failed') {
                statusHtml += `
                    <div class="alert alert-${job.status === 'completed' ? 'success' : 'danger'}">
                        Envio ${job.status === 'completed' ? 'concluído' : 'falhou'}!
                    </div>
                `;
                
                if (job.results && job.results.length > 0) {
                    statusHtml += `
                        <h6>Detalhes:</h6>
                        <ul class="list-group">
                            ${job.results.map(r => `
                                <li class="list-group-item">
                                    ${r.contact_name}: 
                                    ${r.success ? 
                                        '<span class="badge bg-success">Enviado</span>' : 
                                        `<span class="badge bg-danger">Falhou</span> ${r.error || ''}`
                                    }
                                </li>
                            `).join('')}
                        </ul>
                    `;
                }
                
                clearInterval(polling);
            }
            
            statusDiv.innerHTML = statusHtml;
            
        } catch (error) {
            console.error('Error polling job status:', error);
            clearInterval(polling);
        }
    };
    
    updateStatus();
    const polling = setInterval(updateStatus, 2000);
}

// Load schedules
async function loadSchedules() {
  try {
    const data = await apiCall('/schedules');
    const tbody = document.getElementById('schedulesTableBody');
    if (!tbody) return;
    tbody.innerHTML = (data.schedules || []).map(s => {
      const when = s.schedule_type === 'once' ? (s.run_at || '-') : (s.cron_expression || '-');
      const actions = s.status === 'paused' ?
        `<button class="btn btn-sm btn-success me-1" onclick="scheduleResume(${s.id})">Reativar</button>` :
        `<button class="btn btn-sm btn-warning me-1" onclick="schedulePause(${s.id})">Pausar</button>`;
      return `
        <tr>
          <td>${s.id}</td>
          <td>${s.type}</td>
          <td>${s.schedule_type}</td>
          <td>${s.status}</td>
          <td>${when}</td>
          <td>
            ${actions}
            <button class="btn btn-sm btn-danger" onclick="scheduleCancel(${s.id})">Cancelar</button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading schedules', err);
  }
}

async function schedulePause(id) {
  try {
    await apiCall(`/schedules/${id}/pause`, { method: 'POST' });
    showAlert('info', 'Agendamento pausado');
    loadSchedules();
  } catch (e) {}
}

async function scheduleResume(id) {
  try {
    await apiCall(`/schedules/${id}/resume`, { method: 'POST' });
    showAlert('success', 'Agendamento reativado');
    loadSchedules();
  } catch (e) {}
}

async function scheduleCancel(id) {
  if (!confirm('Cancelar este agendamento?')) return;
  try {
    await apiCall(`/schedules/${id}`, { method: 'DELETE' });
    showAlert('success', 'Agendamento cancelado');
    loadSchedules();
  } catch (e) {}
}

// Load message history
async function loadHistory() {
    try {
        const status = document.getElementById('statusFilter')?.value || '';
        const contactId = document.getElementById('contactFilter')?.value || '';
        
        let url = '/messages?';
        if (status) url += `status=${status}&`;
        if (contactId) url += `contact_id=${contactId}&`;
        
        const data = await apiCall(url);
        const tbody = document.getElementById('historyTableBody');
        
        if (tbody) {
            tbody.innerHTML = data.messages.map(msg => `
                <tr>
                    <td>${new Date(msg.created_at).toLocaleString('pt-BR')}</td>
                    <td>${msg.contact_name || msg.phone_number}</td>
                    <td>${msg.content.substring(0, 50)}${msg.content.length > 50 ? '...' : ''}</td>
                    <td>
                        ${msg.status === 'sent' ? 
                            '<span class="badge bg-success">Enviado</span>' :
                            msg.status === 'failed' ?
                            '<span class="badge bg-danger">Falhou</span>' :
                            '<span class="badge bg-warning">Na Fila</span>'
                        }
                    </td>
                    <td>${msg.error || '-'}</td>
                </tr>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

// Invite link helpers
async function showInviteLink(groupId) {
    try {
        const data = await apiCall(`/groups/${groupId}/invite-link`);
        const input = document.getElementById('inviteLinkInput');
        if (input) {
            input.value = data.link;
            const modal = new bootstrap.Modal(document.getElementById('inviteLinkModal'));
            modal.show();
        } else {
            showAlert('info', `Link: ${data.link}`);
        }
    } catch (err) {
        // apiCall already alerts
    }
}

function copyInviteLink() {
    const input = document.getElementById('inviteLinkInput');
    if (input && input.value) {
        navigator.clipboard.writeText(input.value).then(() => {
            showAlert('success', 'Link copiado para a área de transferência');
        }).catch(() => {
            showAlert('warning', 'Não foi possível copiar automaticamente. Copie manualmente.');
        });
    }
}

// Load contacts for filter
async function loadContactsForFilter() {
    try {
        const data = await apiCall('/contacts');
        const select = document.getElementById('contactFilter');
        
        if (select) {
            select.innerHTML = '<option value="">Todos</option>' +
                data.contacts.map(contact => 
                    `<option value="${contact.id}">${contact.name}</option>`
                ).join('');
        }
    } catch (error) {
        console.error('Error loading contacts for filter:', error);
    }
}

// Search contacts
if (document.getElementById('searchContacts')) {
    let searchTimeout;
    document.getElementById('searchContacts').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(async () => {
            const search = e.target.value;
            try {
                const data = await apiCall(`/contacts?search=${search}`);
                const tbody = document.getElementById('contactsTableBody');
                
                if (tbody) {
                    tbody.innerHTML = data.contacts.map(contact => `
                        <tr>
                            <td>${contact.name}</td>
                            <td>${contact.whatsapp_number}</td>
                            <td>${contact.group_name || '-'}</td>
                            <td>
                                <button class="btn btn-sm btn-warning" onclick="editContact(${contact.id})">Editar</button>
                                <button class="btn btn-sm btn-danger" onclick="deleteContact(${contact.id})">Excluir</button>
                            </td>
                        </tr>
                    `).join('');
                }
            } catch (error) {
                console.error('Error searching contacts:', error);
            }
        }, 300);
    });
}