let projectList = [];

// Render the given list of projects into the table
function renderProjects(list) {
    const tbody = document.querySelector('#projects-table tbody');
    tbody.innerHTML = '';
    list.forEach(proj => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${proj.name}</td>
            <td>${proj.template}</td>
            <td>${proj.description || ''}</td>
            <td>
                <button onclick="buildProject('${proj.name}')">Build</button>
                <button onclick="deleteProject('${proj.name}')">Delete</button>
                <button onclick="deployPrompt('${proj.name}')">Deploy</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function loadProjects() {
    const resp = await fetch('/api/projects');
    const data = await resp.json();
    projectList = data.projects;
    renderProjects(projectList)

}

async function loadDevices() {
    const resp = await fetch('/api/devices');
    const data = await resp.json();
    const tbody = document.querySelector('#devices-table tbody');
    tbody.innerHTML = '';
    data.devices.forEach(dev => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${dev.port}</td>
            <td>${dev.name}</td>
            <td>${dev.state}</td>
        `;
        tbody.appendChild(tr);
    });
}

function appendLog(message) {
    const logs = document.getElementById('logs');
    logs.textContent += message + '\\n';
    logs.scrollTop = logs.scrollHeight;
}

async function createProject(event) {
    event.preventDefault();
    const name = document.getElementById('project-name').value;
    const description = document.getElementById('project-desc').value;
    const template = document.getElementById('project-template').value;
    const resp = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, template })
    });
    if (resp.ok) {
        document.getElementById('create-project-form').reset();
        await loadProjects();
    } else {
        const err = await resp.json();
        alert('Error creating project: ' + err.detail);
    }
}

async function deleteProject(name) {
    if (!confirm(`Delete project ${name}?`)) return;
    const resp = await fetch(`/api/projects/${name}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
    });
    if (resp.ok) {
        await loadProjects();
    } else {
        const err = await resp.json();
        alert('Error deleting project: ' + err.detail);
    }
}

async function buildProject(name) {
    appendLog(`Building ${name} ...`);
    const resp = await fetch(`/api/build/${name}`, { method: 'POST' });
    const result = await resp.json();
    if (result.success) {
        appendLog(`✅ Build of ${name} succeeded in ${result.build_time}s`);
        appendLog(`   Files processed: ${result.files_processed}, size: ${result.total_size} bytes`);
    } else {
        appendLog(`❌ Build of ${name} failed: ${result.errors.join(', ')}`);
    }
    await loadProjects(); // refresh list in case build status changed
}

function deployPrompt(name) {
    const port = prompt('Enter device port (e.g. /dev/ttyUSB0):');
    if (!port) return;
    deployProject(name, port);
}

async function deployProject(name, port) {
    appendLog(`Deploying ${name} to ${port} ...`);
    const resp = await fetch(`/api/deploy/${name}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ port })
    });
    const result = await resp.json();
    if (result.success) {
        appendLog(`🚀 Deployment successful: transferred ${result.files_transferred} files in ${result.transfer_time.toFixed(2)}s`);
    } else {
        appendLog(`❌ Deployment failed: ${result.errors.join(', ')}`);
    }
    await loadDevices(); // refresh device status
}


document.getElementById('create-project-form').addEventListener('submit', createProject);

window.addEventListener('DOMContentLoaded', async () => {
    await loadProjects();
    await loadDevices();
});

document.getElementById('project-search').addEventListener('input', () => {
    const query = document.getElementById('project-search').value.toLowerCase();
    const filtered = projectList.filter(p =>
        p.name.toLowerCase().includes(query) ||
        (p.description && p.description.toLowerCase().includes(query))
    );
    renderProjects(filtered);
});