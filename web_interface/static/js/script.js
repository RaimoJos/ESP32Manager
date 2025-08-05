// Enhanced ESP32 Manager Frontend
class ESP32Manager {

    appendLog(message) {
        const logs = document.getElementById('logs');
        if (!logs) return;
        logs.textContent += message + '\n';
        logs.scrollTop = logs.scrollHeight
    }
    constructor() {
        this.projects = [];
        this.devices = [];
        this.openFiles = new Map();
        this.activeFile = null;
        this.buildSocket = null;
        this.eventSource = null;
        this.currentProject = null;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadProjects();
        this.loadDevices();
        this.startEventStream();
        this.showTab('project'); // Show projects tab by default
    }

    setupEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', () => {
                const tab = button.getAttribute('data-tab');
                this.showTab(tab);
            });
        });

        // Project creation form
        const createForm = document.getElementById('create-project-form');
        if (createForm) {
            createForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.createProject();
            });
        }

        // Project search
        const searchInput = document.getElementById('project-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterProjects(e.target.value);
            });
        }

        // Modal close
        const modalClose = document.getElementById('modal-close');
        if (modalClose) {
            modalClose.addEventListener('click', () => {
                this.closeModal();
            });
        }

        // File editor integration
        this.setupFileEditor();
    }

    setupFileEditor() {
        // This would integrate with the file manager
        const codeEditor = document.getElementById('code-editor');
        if (codeEditor) {
            codeEditor.addEventListener('input', () => {
                this.markFileAsModified();
            });
            
            // Add keyboard shortcuts
            codeEditor.addEventListener('keydown', (e) => {
                if (e.ctrlKey || e.metaKey) {
                    if (e.key === 's') {
                        e.preventDefault();
                        this.saveCurrentFile();
                    } else if (e.key === 'b') {
                        e.preventDefault();
                        this.buildCurrentProject();
                    }
                }
            });
        }
    }

    // API Communication Methods
    async apiCall(endpoint, options = {}) {
        try {
            const response = await fetch(endpoint, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            this.showNotification('Error: ' + error.message, 'error');
            throw error;
        }
    }

    // Project Management
    async loadProjects() {
        try {
            const data = await this.apiCall('/api/projects');
            this.projects = data.projects;
            this.renderProjects();
        } catch (error) {
            console.error('Failed to load projects:', error);
        }
    }

    async createProject() {
        const name = document.getElementById('project-name').value.trim();
        const description = document.getElementById('project-desc').value.trim();
        const template = document.getElementById('project-template').value;

        if (!name) {
            this.showNotification('Project name is required', 'error');
            return;
        }

        try {
            await this.apiCall('/api/projects', {
                method: 'POST',
                body: JSON.stringify({
                    name,
                    description,
                    template,
                    author: 'User' // Could be made configurable
                })
            });

            // Clear form
            document.getElementById('create-project-form').reset();
            
            // Reload projects
            await this.loadProjects();
            this.showNotification('Project created successfully', 'success');
        } catch (error) {
            console.error('Failed to create project:', error);
        }
    }

    async deleteProject(projectName) {
        if (!confirm(`Are you sure you want to delete project "${projectName}"?`)) {
            return;
        }

        const removeFiles = confirm('Also delete project files from disk?');

        try {
            await this.apiCall(`/api/projects/${projectName}`, {
                method: 'DELETE',
                body: JSON.stringify({ remove_files: removeFiles })
            });

            await this.loadProjects();
            this.showNotification('Project deleted successfully', 'success');
        } catch (error) {
            console.error('Failed to delete project:', error);
        }
    }

    async showProjectDetails(projectName) {
        try {
            const data = await this.apiCall(`/api/projects/${projectName}/info`);
            this.displayProjectModal(data);
        } catch (error) {
            console.error('Failed to load project details:', error);
        }
    }

    // File Management
    async loadProjectFiles(projectName) {
        try {
            const data = await this.apiCall(`/api/projects/${projectName}/files`);
            this.renderFileTree(data.files);
            this.currentProject = projectName;
        } catch (error) {
            console.error('Failed to load project files:', error);
        }
    }

    async openFile(projectName, filePath) {
        try {
            const data = await this.apiCall(`/api/projects/${projectName}/files/${filePath}`);
            this.openFiles.set(filePath, {
                content: data.content,
                modified: false,
                path: filePath,
                project: projectName
            });
            this.setActiveFile(filePath);
            this.renderFileTabs();
        } catch (error) {
            console.error('Failed to open file:', error);
        }
    }

    async saveCurrentFile() {
        if (!this.activeFile || !this.currentProject) {
            this.showNotification('No file to save', 'warning');
            return;
        }

        const fileData = this.openFiles.get(this.activeFile);
        if (!fileData || !fileData.modified) {
            this.showNotification('No changes to save', 'info');
            return;
        }

        try {
            const codeEditor = document.getElementById('code-editor');
            await this.apiCall(`/api/projects/${this.currentProject}/files/${this.activeFile}`, {
                method: 'PUT',
                body: JSON.stringify({ content: codeEditor.value })
            });

            fileData.modified = false;
            this.renderFileTabs();
            this.showNotification('File saved successfully', 'success');
        } catch (error) {
            console.error('Failed to save file:', error);
        }
    }

    async createNewFile(projectName, fileName, content = '') {
        try {
            await this.apiCall(`/api/projects/${projectName}/files/${fileName}`, {
                method: 'POST',
                body: JSON.stringify({ content })
            });

            await this.loadProjectFiles(projectName);
            this.showNotification('File created successfully', 'success');
        } catch (error) {
            console.error('Failed to create file:', error);
        }
    }

    // Build and Deploy
    async buildProject(projectName) {
        try {
            this.showBuildProgress('Starting build...');
            this.connectBuildWebSocket(projectName);

            const result = await this.apiCall(`/api/build/${projectName}`, {
                method: 'POST'
            });

            if (result.success) {
                this.showNotification('Build completed successfully', 'success');
                this.displayBuildResults(result);
            } else {
                this.showNotification('Build failed', 'error');
                this.displayBuildErrors(result.errors, result.warnings);
            }
        } catch (error) {
            console.error('Build failed:', error);
            this.showBuildProgress('Build failed: ' + error.message, 'error');
        }
    }

    async deployProject(projectName, port) {
        try {
            this.showBuildProgress('Starting deployment...');
            
            const result = await this.apiCall(`/api/deploy/${projectName}`, {
                method: 'POST',
                body: JSON.stringify({ port })
            });

            if (result.success) {
                this.showNotification('Deployment completed successfully', 'success');
                this.displayDeployResults(result);
            } else {
                this.showNotification('Deployment failed', 'error');
                this.displayBuildErrors(result.errors);
            }
        } catch (error) {
            console.error('Deployment failed:', error);
        }
    }

    buildCurrentProject() {
        if (this.currentProject) {
            this.buildProject(this.currentProject);
        } else {
            this.showNotification('No project selected', 'warning');
        }
    }

    // WebSocket for real-time build progress
    connectBuildWebSocket(projectName) {
        if (this.buildSocket) {
            this.buildSocket.close();
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/build/${projectName}`;
        
        this.buildSocket = new WebSocket(wsUrl);
        
        this.buildSocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleBuildProgress(data);
        };

        this.buildSocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.showNotification('Build progress connection failed', 'warning');
        };

        this.buildSocket.onclose = () => {
            this.buildSocket = null;
        };
    }

    handleBuildProgress(data) {
        const { type, project, timestamp } = data;
        
        switch (type) {
            case 'build_start':
                this.showBuildProgress('Build started...', 'info');
                break;
            case 'build_complete':
                this.showBuildProgress(
                    data.success ? 'Build completed successfully' : 'Build failed', 
                    data.success ? 'success' : 'error'
                );
                break;
            case 'deploy_start':
                this.showBuildProgress(`Deploying to ${data.port}...`, 'info');
                break;
            case 'deploy_complete':
                this.showBuildProgress(
                    data.success ? 'Deployment completed' : 'Deployment failed',
                    data.success ? 'success' : 'error'
                );
                break;
            case 'build_error':
            case 'deploy_error':
                this.showBuildProgress(`Error: ${data.error}`, 'error');
                break;
        }
    }

    // Device Management
    async loadDevices() {
        try {
            const data = await this.apiCall('/api/devices');
            this.devices = data.devices;
            this.renderDevices();
        } catch (error) {
            console.error('Failed to load devices:', error);
        }
    }

    async scanDevices() {
        try {
            this.showNotification('Scanning for devices...', 'info');
            const data = await this.apiCall('/api/devices/scan', { method: 'POST' });
            this.devices = data.devices;
            this.renderDevices();
            this.showNotification(`Found ${data.devices.length} devices`, 'success');
        } catch (error) {
            console.error('Failed to scan devices:', error);
        }
    }

    async resetDevice(port) {
        if (!confirm(`Reset device on ${port}?`)) return;

        try {
            await this.apiCall(`/api/devices/${port}/reset`, { method: 'POST' });
            this.showNotification('Device reset successfully', 'success');
        } catch (error) {
            console.error('Failed to reset device:', error);
        }
    }

    // UI Rendering Methods
    renderProjects() {
        const tbody = document.querySelector('#projects-table tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        this.projects.forEach(project => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <strong>${project.name}</strong>
                    <div class="project-meta">
                        ${project.python_files} Python files, ${this.formatBytes(project.total_size)}
                    </div>
                </td>
                <td><span class="template-badge">${project.template}</span></td>
                <td>${project.description || '<em>No description</em>'}</td>
                <td>
                    ${project.last_success ? 
                        `<span class="build-success">${this.formatDate(project.last_success)}</span>` : 
                        '<span class="build-never">Never</span>'
                    }
                    ${project.build_errors.length > 0 ? 
                        `<div class="build-errors">${project.build_errors.length} errors</div>` : 
                        ''
                    }
                </td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-sm" onclick="manager.openProjectEditor('${project.name}')">
                            📝 Edit
                        </button>
                        <button class="btn btn-sm" onclick="manager.buildProject('${project.name}')">
                            🔨 Build
                        </button>
                        <button class="btn btn-sm" onclick="manager.showDeployDialog('${project.name}')">
                            📤 Deploy
                        </button>
                        <button class="btn btn-sm secondary" onclick="manager.showProjectDetails('${project.name}')">
                            ℹ️ Info
                        </button>
                        <button class="btn btn-sm danger" onclick="manager.deleteProject('${project.name}')">
                            🗑️ Delete
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    renderDevices() {
        const tbody = document.querySelector('#devices-table tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (this.devices.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td colspan="4" class="no-devices">
                    No devices connected. 
                    <button class="btn btn-sm" onclick="manager.scanDevices()">Scan for Devices</button>
                </td>
            `;
            tbody.appendChild(row);
            return;
        }

        this.devices.forEach(device => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><code>${device.port}</code></td>
                <td>${device.name || device.description || 'Unknown Device'}</td>
                <td>
                    <span class="device-status ${device.connected ? 'connected' : 'disconnected'}">
                        ${device.connected ? '🟢 Connected' : '🔴 Disconnected'}
                    </span>
                </td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-sm" onclick="manager.openSerialMonitor('${device.port}')">
                            📟 Monitor
                        </button>
                        <button class="btn btn-sm secondary" onclick="manager.resetDevice('${device.port}')">
                            🔄 Reset
                        </button>
                        <button class="btn btn-sm secondary" onclick="manager.showDeviceInfo('${device.port}')">
                            ℹ️ Info
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    renderFileTree(files) {
        const container = document.getElementById('file-tree');
        if (!container) return;

        container.innerHTML = '';

        const renderFile = (file, depth = 0) => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.style.paddingLeft = `${8 + depth * 16}px`;

            const icon = file.type === 'folder' ? '📁' : 
                        file.name.endsWith('.py') ? '🐍' : '📄';
            
            item.innerHTML = `
                <span class="file-icon">${icon}</span>
                <span class="file-name">${file.name}</span>
                ${file.size ? `<span class="file-size">${this.formatBytes(file.size)}</span>` : ''}
            `;

            if (file.type === 'file') {
                item.addEventListener('click', () => {
                    this.openFile(this.currentProject, file.path);
                });
                item.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    this.showFileContextMenu(e, file);
                });
            }

            container.appendChild(item);

            if (file.children) {
                file.children.forEach(child => renderFile(child, depth + 1));
            }
        };

        files.forEach(file => renderFile(file));
    }

    renderFileTabs() {
        const container = document.getElementById('file-tabs');
        if (!container) return;

        container.innerHTML = '';

        this.openFiles.forEach((fileData, fileName) => {
            const tab = document.createElement('div');
            tab.className = `file-tab ${fileName === this.activeFile ? 'active' : ''}`;
            
            const icon = fileName.endsWith('.py') ? '🐍' : '📄';
            const modifiedIndicator = fileData.modified ? ' •' : '';
            
            tab.innerHTML = `
                <span class="tab-icon">${icon}</span>
                <span class="tab-name">${fileName}${modifiedIndicator}</span>
                <span class="tab-close" onclick="manager.closeFile('${fileName}')">&times;</span>
            `;

            tab.addEventListener('click', (e) => {
                if (!e.target.classList.contains('tab-close')) {
                    this.setActiveFile(fileName);
                }
            });

            container.appendChild(tab);
        });
    }

    // UI Helper Methods
    showTab(tabName) {
        // Hide all tab contents
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });

        // Hide all tab buttons active state
        document.querySelectorAll('.tab-button').forEach(button => {
            button.classList.remove('active');
        });

        // Show selected tab
        const selectedContent = document.getElementById(`${tabName}-section`);
        const selectedButton = document.querySelector(`.tab-button[data-tab="${tabName}"]`);

        if (selectedContent) selectedContent.classList.add('active');
        if (selectedButton) selectedButton.classList.add('active');

        // Load data based on tab
        switch (tabName) {
            case 'project':
                this.loadProjects();
                break;
            case 'device':
                this.loadDevices();
                break;
            case 'logs':
                this.loadSystemLogs();
                break;
        }
    }

    showNotification(message, type = 'info') {
        // Create notification element if it doesn't exist
        let notification = document.getElementById('notification');
        if (!notification) {
            notification = document.createElement('div');
            notification.id = 'notification';
            notification.className = 'notification';
            document.body.appendChild(notification);
        }

        notification.className = `notification ${type} show`;
        notification.textContent = message;

        // Auto-hide after 5 seconds
        setTimeout(() => {
            notification.classList.remove('show');
        }, 5000);
    }

    showBuildProgress(message, type = 'info') {
        const progressElement = document.getElementById('build-progress');
        if (progressElement) {
            progressElement.className = `build-progress ${type}`;
            progressElement.textContent = message;
            progressElement.style.display = 'block';
        } else {
            this.showNotification(message, type);
        }
    }

    displayProjectModal(data) {
        const modal = document.getElementById('project-modal');
        if (!modal) return;

        document.getElementById('modal-title').textContent = data.project.name;
        document.getElementById('modal-desc').textContent = data.project.description || 'No description';
        document.getElementById('modal-files').textContent = data.stats.file_count || 0;
        document.getElementById('modal-pyfiles').textContent = data.stats.python_files || 0;
        document.getElementById('modal-size').textContent = data.stats.total_size || 0;
        document.getElementById('modal-last-built').textContent = 
            data.build_status.last_success ? this.formatDate(data.build_status.last_success) : 'Never';
        
        document.getElementById('modal-errors').textContent = 
            data.build_status.last_errors.join('\n') || 'None';
        document.getElementById('modal-warnings').textContent = 
            data.build_status.last_warnings.join('\n') || 'None';

        modal.classList.remove('hidden');
    }

    closeModal() {
        const modal = document.getElementById('project-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    }

    showDeployDialog(projectName) {
        const port = prompt('Enter device port (e.g., COM3, /dev/ttyUSB0):');
        if (port) {
            this.deployProject(projectName, port);
        }
    }

    // Project Editor Integration
    openProjectEditor(projectName) {
        // This would switch to a file editor view
        this.loadProjectFiles(projectName);
        this.showNotification(`Opening ${projectName} in editor`, 'info');
        
        // If you have a separate editor view, switch to it here
        // For now, we'll just load the files in the current interface
    }

    setActiveFile(fileName) {
        this.activeFile = fileName;
        const fileData = this.openFiles.get(fileName);
        
        if (fileData) {
            const codeEditor = document.getElementById('code-editor');
            if (codeEditor) {
                codeEditor.value = fileData.content;
            }
            this.renderFileTabs();
        }
    }

    closeFile(fileName) {
        const fileData = this.openFiles.get(fileName);
        
        if (fileData && fileData.modified) {
            if (!confirm(`${fileName} has unsaved changes. Close anyway?`)) {
                return;
            }
        }

        this.openFiles.delete(fileName);
        
        if (this.activeFile === fileName) {
            const remaining = Array.from(this.openFiles.keys());
            this.activeFile = remaining.length > 0 ? remaining[0] : null;
        }

        this.renderFileTabs();
        
        if (this.activeFile) {
            this.setActiveFile(this.activeFile);
        } else {
            const codeEditor = document.getElementById('code-editor');
            if (codeEditor) {
                codeEditor.value = '';
            }
        }
    }

    markFileAsModified() {
        if (this.activeFile) {
            const fileData = this.openFiles.get(this.activeFile);
            if (fileData) {
                fileData.modified = true;
                this.renderFileTabs();
            }
        }
    }

    filterProjects(searchTerm) {
        const rows = document.querySelectorAll('#projects-table tbody tr');
        const term = searchTerm.toLowerCase();

        rows.forEach(row => {
            const projectName = row.querySelector('td:first-child strong')?.textContent.toLowerCase() || '';
            const description = row.querySelector('td:nth-child(3)')?.textContent.toLowerCase() || '';
            
            if (projectName.includes(term) || description.includes(term)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    // Event Stream for real-time updates
    startEventStream() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        this.eventSource = new EventSource('/api/events');
        
        this.eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.projects = data.projects;
            this.devices = data.devices;
            
            // Update UI if we're on the relevant tabs
            const activeTab = document.querySelector('.tab-button.active')?.getAttribute('data-tab');
            if (activeTab === 'project') {
                this.renderProjects();
            } else if (activeTab === 'device') {
                this.renderDevices();
            }
        };

        this.eventSource.onerror = (error) => {
            console.error('EventSource error:', error);
            // Reconnect after 5 seconds
            setTimeout(() => {
                this.startEventStream();
            }, 5000);
        };
    }

    // Utility Methods
    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString();
    }

    // Advanced Features (placeholders for future implementation)
    openSerialMonitor(port) {
        // Toggle existing socket*
        if (this.logSocket) {
            this.logSocket.close();
            this.logSocket = null;
            this.appendLog(`🛑 Stopped monitoring ${port}`);
            return;
        }

        this.appendLog(`▶️ Starting monitor for ${port}`);
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${proto}//${window.location.host}/ws/logs/${encodeURIComponent(port)}`;
        this.logSocket = new WebSocket(url);

        this.logSocket.onmessage = (event) => {
            this.appendLog(`[${port}] ${event.data}`);
        };

        this.logSocket.onclose = () => {
            this.appendLog(`🛑 Monitor disconnected for ${port}`);
            this.logSocket = null;
        };

        this.logSocket.onerror = (err) => {
            this.appendLog(`⚠️ Monitor error: ${err.message || err}`);
            this.logSocket.close();
            this.logSocket = null;
        };
    }

    showDeviceInfo(port) {
        this.showNotification(`Device info for ${port} (feature coming soon)`, 'info');
        // TODO: Show detailed device information modal
    }

    loadSystemLogs() {
        const logsElement = document.getElementById('logs');
        if (logsElement) {
            logsElement.textContent = 'System logs (feature coming soon)';
        }
        // TODO: Load and display system logs
    }

    showFileContextMenu(event, file) {
        // TODO: Implement context menu for file operations
        console.log('Context menu for file:', file);
    }

    // Cleanup
    destroy() {
        if (this.eventSource) {
            this.eventSource.close();
        }
        if (this.buildSocket) {
            this.buildSocket.close();
        }
    }
}

// Initialize the manager when the page loads
let manager;
document.addEventListener('DOMContentLoaded', () => {
    manager = new ESP32Manager();
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (manager) {
        manager.destroy();
    }
});
