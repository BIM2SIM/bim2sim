/**
 * bim2sim GUI - Main Application
 * Phase 2: Project and Decision Management
 */

/**
 * Copy text to the clipboard. Uses the async Clipboard API where available
 * (secure contexts such as http://localhost) and falls back to a hidden
 * textarea + execCommand otherwise.
 */
async function copyTextToClipboard(text) {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch (e) {
        console.warn('Clipboard API failed, using fallback:', e);
    }

    try {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(textarea);
        return ok;
    } catch (e) {
        console.error('Copy failed:', e);
        return false;
    }
}

/** Format log entries as plain text, one entry per line. */
function formatLogsAsText(logs) {
    return (logs || [])
        .map(l => `${l.time} ${String(l.level).padEnd(7)} ${l.message}`)
        .join('\n');
}

document.addEventListener('alpine:init', () => {
    // Shared Blender state: connection, the process this GUI started, and
    // which IFC is loaded. A store (not component state) because the header,
    // the project cards and the Server tab all need the same values.
    Alpine.store('blender', {
        connected: false,
        info: null,
        process: { running: false, seconds_since_launch: null },
        ifc: { known: false, loaded: false, path: '', loading: false,
               loadingPath: '', error: null },
        launching: false,         // a launch request is in flight
        error: null,
        selectedProject: null,    // { id, name, ifc_path }, set by the project list
        pendingProject: null,     // project whose IFC loads once Blender connects
        lastStatusRequest: 0,

        // ---- state shown in the header --------------------------------
        /**
         * connected | starting | unconnected | offline
         *  starting    - we started Blender recently, not connected yet
         *  unconnected - our Blender runs for a while but never connected
         *                (auto-connect failed, user must press Connect)
         */
        get state() {
            if (this.connected) return 'connected';
            if (this.process && this.process.running) {
                const age = this.process.seconds_since_launch;
                return (age !== null && age < 60) ? 'starting' : 'unconnected';
            }
            return 'offline';
        },

        get label() {
            return {
                connected: 'Blender Connected',
                starting: 'Blender starting...',
                unconnected: 'Blender running, not connected',
                offline: 'Blender Offline'
            }[this.state];
        },

        // ---- fed by the app component ---------------------------------
        setConnection(connected, info) {
            const was = this.connected;
            this.connected = !!connected;

            if (!this.connected) {
                this.info = null;
                this.ifc = { known: false, loaded: false, path: '', loading: false,
                             loadingPath: '', error: null };
                return;
            }
            if (info) this.info = info;

            if (!was && this.pendingProject) {
                // The server sends the pending IFC the moment Blender connects
                this.ifc.loading = true;
                this.ifc.loadingPath = this.pendingProject.ifc_path;
                this.ifc.error = null;
                this._loadTimeout(this.pendingProject.ifc_path);
                this.pendingProject = null;
            }

            // After a page reload Blender won't repeat its status by itself
            if (!this.ifc.known) this.requestStatus();
        },

        handleMessage(data) {
            if (!data) return;
            if (data.type === 'status') {
                this.ifc.known = true;
                this.ifc.loaded = !!data.ifc_loaded;
                this.ifc.path = data.ifc_path || '';
            } else if (data.type === 'ifc_load_result') {
                this.ifc.loading = false;
                this.ifc.loadingPath = '';
                if (data.success) {
                    this.ifc.known = true;
                    this.ifc.loaded = true;
                    this.ifc.path = data.ifc_path || this.ifc.path;
                    this.ifc.error = null;
                } else {
                    this.ifc.error = data.error || 'Blender could not load the IFC file.';
                }
            }
        },

        async refreshProcess() {
            try {
                const response = await fetch('/api/blender/process');
                if (response.ok) this.process = await response.json();
            } catch (error) {
                // Endpoint unavailable (older server): treat as not started
                this.process = { running: false, seconds_since_launch: null };
            }
        },

        async requestStatus() {
            // At most every 15 s, in case an older add-on never answers
            const now = Date.now();
            if (now - this.lastStatusRequest < 15000) return;
            this.lastStatusRequest = now;
            try {
                await fetch('/api/blender/refresh-status', { method: 'POST' });
            } catch (error) { /* not critical */ }
        },

        // ---- per-project helpers for the cards ------------------------
        _norm(path) {
            return String(path || '').replace(/\\/g, '/').toLowerCase();
        },

        isLoaded(project) {
            return !!project && this.connected && this.ifc.loaded &&
                this._norm(this.ifc.path) === this._norm(project.ifc_path);
        },

        isLoading(project) {
            return !!project && this.ifc.loading &&
                this._norm(this.ifc.loadingPath) === this._norm(project.ifc_path);
        },

        isStartingFor(project) {
            return !!project && !this.connected && !!this.pendingProject &&
                this.pendingProject.id === project.id;
        },

        projectLabel(project) {
            if (this.isLoading(project)) return 'Loading in Blender...';
            if (this.isLoaded(project)) return 'Loaded in Blender';
            if (this.isStartingFor(project)) return 'Waiting for Blender...';
            return this.connected ? 'Load in Blender' : 'Open in Blender';
        },

        projectDisabled(project) {
            return this.launching || this.isLoading(project) || this.isLoaded(project);
        },

        // ---- actions ----------------------------------------------------
        /** Header button: start Blender, loading the selected project's IFC. */
        async start() {
            return this._launch(this.selectedProject);
        },

        /** Project card: load the IFC, starting Blender first if needed. */
        async openProject(project) {
            if (!project) return;
            if (this.connected) return this._loadIfc(project);
            return this._launch(project);
        },

        async _launch(project) {
            this.launching = true;
            this.error = null;
            try {
                const body = { auto_connect: true };
                if (project) body.project_id = project.id;
                const response = await fetch('/api/blender/launch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || 'Could not start Blender');
                }
                // Server keeps the IFC and sends it once Blender connects
                if (project) this.pendingProject = project;
                await this.refreshProcess();
            } catch (error) {
                console.error('Error starting Blender:', error);
                this._setError(error.message);
            } finally {
                this.launching = false;
            }
        },

        async _loadIfc(project) {
            this.error = null;
            this.ifc.loading = true;
            this.ifc.loadingPath = project.ifc_path;
            this.ifc.error = null;
            try {
                const response = await fetch('/api/blender/load-ifc', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_id: project.id })
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || 'Could not load the IFC file');
                }
                // The result arrives later as an ifc_load_result message
                this._loadTimeout(project.ifc_path);
            } catch (error) {
                console.error('Error loading IFC in Blender:', error);
                this.ifc.loading = false;
                this.ifc.loadingPath = '';
                this._setError(error.message);
            }
        },

        // Give up waiting for Blender's answer (e.g. an older add-on that
        // never reports back), so the button doesn't stay "Loading" forever.
        _loadTimeout(path) {
            setTimeout(() => {
                if (this.ifc.loading && this.ifc.loadingPath === path) {
                    this.ifc.loading = false;
                    this.ifc.loadingPath = '';
                    this._setError('No answer from Blender. Check its console.');
                }
            }, 5 * 60 * 1000);
        },

        _setError(message) {
            this.error = message;
            setTimeout(() => { if (this.error === message) this.error = null; }, 10000);
        }
    });

    Alpine.data('app', () => ({
        // State
        currentView: 'projects',
        serverConnected: false,
        blenderConnected: false,
        blenderInfo: null,
        blenderStatus: null,
        serverAddress: window.location.host,
        socket: null,

        // Initialization
        init() {
            console.log('bim2sim GUI initialized');
            this.connectWebSocket();
            this.checkServerStatus();
        },

        // WebSocket Connection
        connectWebSocket() {
            console.log('Connecting to WebSocket...');

            this.socket = io({
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionDelayMax: 5000,
                reconnectionAttempts: Infinity
            });

            this.socket.on('connect', () => {
                console.log('WebSocket connected');
                this.serverConnected = true;
            });

            this.socket.on('disconnect', () => {
                console.log('WebSocket disconnected');
                this.serverConnected = false;
            });

            this.socket.on('server_message', (data) => {
                console.log('Server message:', data);
            });

            this.socket.on('connect_error', (error) => {
                console.error('WebSocket connection error:', error);
                this.serverConnected = false;
            });

            // Blender connection events
            this.socket.on('blender_connected', (data) => {
                console.log('Blender connected:', data);
                this.blenderConnected = true;
                this.blenderInfo = data;
                Alpine.store('blender').setConnection(true, data);
            });

            this.socket.on('blender_disconnected', (data) => {
                console.log('Blender disconnected:', data);
                this.blenderConnected = false;
                this.blenderInfo = null;
                Alpine.store('blender').setConnection(false);
            });

            this.socket.on('blender_message', (data) => {
                console.log('Blender message:', data);
                // Handle specific message types
                if (data.type === 'status') {
                    this.blenderStatus = data;
                }
                // status / ifc_load_result update which IFC is loaded
                Alpine.store('blender').handleMessage(data);
            });

            // Project status updates from backend
            this.socket.on('project_status_changed', (data) => {
                console.log('Project status changed:', data);
                // Dispatch custom event so projectManager can react
                window.dispatchEvent(new CustomEvent('project-status-changed', {
                    detail: data
                }));
            });

            // Decisions available from backend
            this.socket.on('decisions_available', (data) => {
                console.log('Decisions available:', data);
                window.dispatchEvent(new CustomEvent('decisions-available', {
                    detail: data
                }));
            });
        },

        // Check server status via REST
        async checkServerStatus() {
            try {
                const response = await fetch('/api/status');
                if (response.ok) {
                    const data = await response.json();

                    const wasConnected = this.blenderConnected;
                    this.serverConnected = data.server_running;
                    this.blenderConnected = data.blender_connected;

                    if (data.blender_info) {
                        this.blenderInfo = data.blender_info;
                    }
                    Alpine.store('blender').setConnection(
                        this.blenderConnected, data.blender_info);

                    // Log status changes
                    if (wasConnected !== this.blenderConnected) {
                        console.log('Blender connection changed:', this.blenderConnected);
                        console.log('Blender info:', this.blenderInfo);
                    }
                }
            } catch (error) {
                console.error('Failed to check server status:', error);
                this.serverConnected = false;
            }

            await Alpine.store('blender').refreshProcess();

            // Poll every 3 seconds
            setTimeout(() => this.checkServerStatus(), 3000);
        },

        // Helper: Send ping to test WebSocket
        sendPing() {
            if (this.socket && this.socket.connected) {
                this.socket.emit('ping', { timestamp: Date.now() });
                console.log('Ping sent');
            }
        }
    }));

    // Project Manager Component
    Alpine.data('projectManager', () => ({
        projects: [],
        selectedProject: null,
        loading: false,
        error: null,

        // Run history state
        projectRuns: [],
        loadingRuns: false,
        expandedRunId: null,
        expandedRunDetail: null,
        copiedRunId: null,
        copiedPathRunId: null,
        loadingRunDetail: false,

        // Create form state
        showCreateForm: false,
        editingProjectId: null,  // null = create, string = edit
        backends: [],
        backendSettings: null,
        settingsLoading: false,
        newProject: {
            name: '',
            description: '',
            backend: '',
            domain: '',
            ifc_path: '',
            settings: {}
        },

        async init() {
            await this.loadProjects();
            await this.loadBackends();

            window.addEventListener('project-status-changed', (event) => {
                const data = event.detail;
                console.log('projectManager received status change:', data);
                this.updateProjectStatus(data.project_id, data.status);
                if (this.selectedProject && this.selectedProject.id === data.project_id) {
                    this.selectedProject.status = data.status;
                    // Refresh run history so the finished/failed run appears
                    this.loadRuns(data.project_id);
                }
            });
        },

        async loadProjects() {
            this.loading = true;
            this.error = null;
            try {
                const response = await fetch('/api/projects');
                if (!response.ok) throw new Error('Failed to load projects');
                const data = await response.json();
                this.projects = data.projects || [];
            } catch (error) {
                console.error('Error loading projects:', error);
                this.error = error.message;
            } finally {
                this.loading = false;
            }
        },

        async loadBackends() {
            try {
                const response = await fetch('/api/backends');
                if (!response.ok) throw new Error('Failed to load backends');
                const data = await response.json();
                this.backends = data.backends || [];
                console.log('Loaded backends:', this.backends);
            } catch (error) {
                console.error('Error loading backends:', error);
            }
        },

        async onBackendChanged() {
            const backend = this.newProject.backend;
            if (!backend) {
                this.backendSettings = null;
                this.newProject.domain = '';
                return;
            }

            // Auto-fill domain from backend info
            const backendInfo = this.backends.find(b => b.name === backend);
            if (backendInfo) {
                this.newProject.domain = backendInfo.domain;
            }

            // Load settings for this backend
            this.settingsLoading = true;
            this.backendSettings = null;
            this.newProject.settings = {};

            try {
                const response = await fetch(`/api/backends/${backend}/settings`);
                if (!response.ok) throw new Error('Failed to load settings');
                const data = await response.json();
                this.backendSettings = data;
                console.log('Loaded settings:', data);

                // Initialize settings with defaults
                const allSettings = [
                    ...(data.base_settings || []),
                    ...(data.plugin_settings || [])
                ];
                allSettings.forEach(s => {
                    if (s.for_frontend && s.default !== null) {
                        this.newProject.settings[s.name] = s.default;
                    }
                });
            } catch (error) {
                console.error('Error loading settings:', error);
            } finally {
                this.settingsLoading = false;
            }
        },

        getFrontendSettings(group) {
            if (!this.backendSettings) return [];
            const settings = group === 'plugin'
                ? this.backendSettings.plugin_settings
                : this.backendSettings.base_settings;
            return (settings || []).filter(s => s.for_frontend);
        },

        getAdvancedSettings(group) {
            if (!this.backendSettings) return [];
            const settings = group === 'plugin'
                ? this.backendSettings.plugin_settings
                : this.backendSettings.base_settings;
            return (settings || []).filter(s => !s.for_frontend);
        },

        openCreateForm() {
            this.showCreateForm = true;
            this.editingProjectId = null;
            this.newProject = {
                name: '',
                description: '',
                backend: '',
                domain: '',
                ifc_path: '',
                settings: {}
            };
            this.backendSettings = null;
        },

        async openEditForm(project) {
            this.showCreateForm = true;
            this.editingProjectId = project.id;
            this.newProject = {
                name: project.name || '',
                description: project.description || '',
                backend: project.backend || '',
                domain: project.domain || '',
                ifc_path: project.ifc_path || '',
                settings: { ...(project.settings || {}) }
            };
            this.backendSettings = null;
            // Load settings for existing backend
            if (project.backend) {
                await this.onBackendChanged();
                // Re-apply existing settings over defaults
                this.newProject.settings = { ...(project.settings || {}) };
            }
        },

        cancelCreate() {
            this.showCreateForm = false;
            this.editingProjectId = null;
            this.backendSettings = null;
            this.error = null;
        },

        async createProject() {
            this.error = null;
            if (!this.newProject.name || !this.newProject.backend ||
                !this.newProject.ifc_path) {
                this.error = 'Name, Backend and IFC Path are required.';
                return;
            }

            try {
                const payload = {
                    name: this.newProject.name,
                    description: this.newProject.description,
                    backend: this.newProject.backend,
                    domain: this.newProject.domain,
                    ifc_path: this.newProject.ifc_path,
                    settings: { ...this.newProject.settings }
                };

                let response;
                if (this.editingProjectId) {
                    // Update existing project
                    response = await fetch(`/api/projects/${this.editingProjectId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                } else {
                    // Create new project
                    response = await fetch('/api/projects', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                }

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Failed to save project');
                }

                this.showCreateForm = false;
                this.editingProjectId = null;
                await this.loadProjects();

            } catch (error) {
                console.error('Error saving project:', error);
                this.error = error.message;
            }
        },

        selectProject(project) {
            this.selectedProject = project;
            Alpine.store('blender').selectedProject = {
                id: project.id, name: project.name, ifc_path: project.ifc_path
            };
            this.expandedRunId = null;
            this.expandedRunDetail = null;
            this.loadRuns(project.id);
        },

        async loadRuns(projectId) {
            this.loadingRuns = true;
            try {
                const response = await fetch(`/api/projects/${projectId}/runs`);
                if (!response.ok) throw new Error('Failed to load run history');
                const data = await response.json();
                this.projectRuns = data.runs || [];
            } catch (error) {
                console.error('Error loading run history:', error);
                this.projectRuns = [];
            } finally {
                this.loadingRuns = false;
            }
        },

        async copyRunPath(detail) {
            if (!detail || !detail.project_path) return;
            const ok = await copyTextToClipboard(detail.project_path);
            if (ok) {
                this.copiedPathRunId = detail.run_id;
                setTimeout(() => {
                    if (this.copiedPathRunId === detail.run_id) {
                        this.copiedPathRunId = null;
                    }
                }, 2000);
            }
        },

        async openRunFolder(detail) {
            if (!detail) return;
            try {
                const response = await fetch(
                    `/api/projects/${detail.project_id}/runs/${detail.run_id}/open-folder`,
                    { method: 'POST' }
                );
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Could not open folder');
                }
            } catch (error) {
                console.error('Error opening run folder:', error);
                this.error = error.message;
            }
        },

        async copyRunLog(detail) {
            if (!detail) return;
            const header = [
                `Project: ${detail.project_id}`,
                `Run: ${detail.run_id}`,
                `Status: ${detail.status}`,
                `Started: ${detail.started_at || '-'}`,
                `Finished: ${detail.finished_at || '-'}`,
                detail.project_path ? `Folder: ${detail.project_path}` : null,
                detail.error ? `Error: ${detail.error}` : null,
                '',
                'Settings:',
                JSON.stringify(detail.settings_snapshot, null, 2),
                '',
                `Log (${(detail.logs || []).length} entries):`,
            ].filter(line => line !== null).join('\n');

            const ok = await copyTextToClipboard(
                header + '\n' + formatLogsAsText(detail.logs));
            if (ok) {
                this.copiedRunId = detail.run_id;
                setTimeout(() => {
                    if (this.copiedRunId === detail.run_id) {
                        this.copiedRunId = null;
                    }
                }, 2000);
            }
        },

        async toggleRunDetail(run) {
            // Collapse if already expanded
            if (this.expandedRunId === run.run_id) {
                this.expandedRunId = null;
                this.expandedRunDetail = null;
                return;
            }

            this.expandedRunId = run.run_id;
            this.expandedRunDetail = null;
            this.loadingRunDetail = true;

            try {
                const response = await fetch(
                    `/api/projects/${run.project_id}/runs/${run.run_id}`
                );
                if (!response.ok) throw new Error('Failed to load run details');
                this.expandedRunDetail = await response.json();
            } catch (error) {
                console.error('Error loading run details:', error);
            } finally {
                this.loadingRunDetail = false;
            }
        },

        getRunDuration(run) {
            if (!run.started_at || !run.finished_at) return null;
            const ms = new Date(run.finished_at) - new Date(run.started_at);
            if (ms < 0) return null;
            const seconds = Math.round(ms / 1000);
            if (seconds < 60) return `${seconds}s`;
            return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
        },

        formatRunTime(isoString) {
            if (!isoString) return '-';
            const d = new Date(isoString);
            return d.toLocaleString();
        },

        async executeProject(projectId) {
            try {
                const response = await fetch(`/api/projects/${projectId}/execute`, {
                    method: 'POST'
                });
                if (!response.ok) throw new Error('Failed to execute project');
                const data = await response.json();
                console.log('Project execution started:', data);
                this.updateProjectStatus(projectId, 'running');
            } catch (error) {
                console.error('Error executing project:', error);
                this.error = error.message;
            }
        },

        async stopProject(projectId) {
            if (!confirm('Stop this project? All progress will be lost.')) return;
            try {
                const response = await fetch(`/api/projects/${projectId}/stop`, {
                    method: 'POST'
                });
                if (!response.ok) throw new Error('Failed to stop project');
                this.updateProjectStatus(projectId, 'idle');
            } catch (error) {
                console.error('Error stopping project:', error);
                this.error = error.message;
            }
        },

        async deleteProject(projectId) {
            if (!confirm('Delete this project permanently?')) return;
            try {
                const response = await fetch(`/api/projects/${projectId}`, {
                    method: 'DELETE'
                });
                if (!response.ok) throw new Error('Failed to delete project');
                this.selectedProject = null;
                Alpine.store('blender').selectedProject = null;
                await this.loadProjects();
            } catch (error) {
                console.error('Error deleting project:', error);
                this.error = error.message;
            }
        },

        updateProjectStatus(projectId, status) {
            const project = this.projects.find(p => p.id === projectId);
            if (project) project.status = status;
        },

        getStatusColor(status) {
            return { 'idle': 'gray', 'running': 'blue', 'completed': 'green', 'error': 'red' }[status] || 'gray';
        },

        getStatusText(status) {
            return status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown';
        }
    }));

    // Decision Manager Component
    Alpine.data('decisionManager', () => ({
        decisions: [],
        answers: {},
        pending: false,
        loading: false,
        error: null,
        blenderConnected: false,  // Track Blender status locally
        highlightSettings: {
            zoom: true,
            hideOthers: false,
            showContext: false,
            contextDepth: 1
        },

        async init() {
            // Load highlight settings from localStorage
            const saved = localStorage.getItem('highlightSettings');
            if (saved) {
                this.highlightSettings = JSON.parse(saved);
            }

            await this.loadDecisions();

            // Poll for decisions every 3 seconds
            setInterval(() => this.loadDecisions(), 3000);

            // Poll for Blender status every 3 seconds
            setInterval(() => this.checkBlenderStatus(), 3000);
            this.checkBlenderStatus(); // Initial check

            // React immediately when new decisions arrive from backend
            window.addEventListener('decisions-available', () => {
                console.log('Immediate decision reload triggered');
                this.loadDecisions();
            });

            // Clear decisions when project finishes or errors out
            window.addEventListener('project-status-changed', (event) => {
                const status = event.detail.status;
                if (status === 'completed' || status === 'error' || status === 'idle') {
                    console.log('Project finished, clearing decisions');
                    this.decisions = [];
                    this.answers = {};
                    this.pending = false;
                    this.error = null;
                }
            });
        },

        async checkBlenderStatus() {
            try {
                const response = await fetch('/api/status');
                if (response.ok) {
                    const data = await response.json();
                    this.blenderConnected = data.blender_connected || false;
                }
            } catch (error) {
                console.error('Failed to check Blender status:', error);
                this.blenderConnected = false;
            }
        },

        async loadDecisions() {
            try {
                const response = await fetch('/api/decisions');
                if (!response.ok) {
                    let errorMsg = `Failed to load decisions (HTTP ${response.status})`;
                    try {
                        const errorData = await response.json();
                        if (errorData.error) errorMsg += `: ${errorData.error}`;
                        if (errorData.traceback) console.error('Server traceback:', errorData.traceback);
                    } catch (e) { /* response wasn't JSON */ }
                    throw new Error(errorMsg);
                }

                const data = await response.json();
                this.pending = data.pending || false;

                // Only update if decisions actually changed
                const newDecisions = data.decisions || [];
                if (JSON.stringify(newDecisions) !== JSON.stringify(this.decisions)) {
                    this.decisions = newDecisions;

                    // DEBUG: Log decision structure
                    console.log('=== DECISION STRUCTURE DEBUG ===');
                    if (this.decisions.length > 0) {
                        console.log('First decision:', this.decisions[0]);
                        console.log('Type:', this.decisions[0].type);
                        console.log('Options:', this.decisions[0].options);
                        console.log('Body:', this.decisions[0].body);
                        console.log('Related:', this.decisions[0].related);
                    }
                    console.log('================================');

                    // FIX: Parse options from body if needed
                    this.decisions.forEach(decision => {
                        // If options is ["cancel", "skip"] and body is an array, extract real options
                        if (Array.isArray(decision.options) &&
                            decision.options.length === 2 &&
                            decision.options[0] === "cancel" &&
                            Array.isArray(decision.body)) {

                            // Body contains arrays like [index, "name", {...}]
                            decision.options = decision.body.map((item, idx) => {
                                if (Array.isArray(item) && item.length >= 2) {
                                    // Format: "0,GENERAL-Material"
                                    return `${item[0]},${item[1]}`;
                                }
                                return item;
                            });

                            console.log('Parsed options from body:', decision.options.length, 'options');
                            console.log('First 3 options:', decision.options.slice(0, 3));

                            // Clear body to avoid displaying it
                            decision.body = null;
                        }
                    });

                    // Initialize answers with defaults
                    this.decisions.forEach(decision => {
                        if (!(decision.id in this.answers)) {
                            // Set default value or appropriate empty value
                            if (decision.default !== null && decision.default !== undefined) {
                                this.answers[decision.id] = decision.default;
                            } else if (decision.type === 'DecisionBool' || decision.type === 'BoolDecision') {
                                this.answers[decision.id] = false;
                            } else if (decision.type === 'DecisionList' || decision.type === 'ListDecision') {
                                this.answers[decision.id] = '';
                            } else {
                                this.answers[decision.id] = '';
                            }
                        }
                    });

                    console.log('Decisions loaded:', newDecisions.length);
                }

            } catch (error) {
                console.error('Error loading decisions:', error);
                this.error = error.message;
            }
        },

        isAnswered(decision) {
            const answer = this.answers[decision.id];
            // null means explicitly skipped
            if (answer === null) return true;
            // Empty string means not answered
            if (answer === '' || answer === undefined) return false;
            return true;
        },

        getUnansweredRequired() {
            // Decisions that have no answer and cannot be skipped
            return this.decisions.filter(d =>
                !this.isAnswered(d) && !d.allow_skip
            );
        },

        getUnansweredSkippable() {
            // Decisions that have no answer but can be skipped
            return this.decisions.filter(d =>
                !this.isAnswered(d) && d.allow_skip
            );
        },

        async submitAnswers() {
            this.loading = true;
            this.error = null;

            try {
                // Auto-skip unanswered decisions that allow skipping
                this.decisions.forEach(decision => {
                    if (!this.isAnswered(decision) && decision.allow_skip) {
                        console.log(`Auto-skipping decision: ${decision.id}`);
                        this.answers[decision.id] = null;
                    }
                });

                // Final check: no unanswered required decisions
                const unanswered = this.getUnansweredRequired();
                if (unanswered.length > 0) {
                    throw new Error(
                        `${unanswered.length} required decision(s) still need an answer.`
                    );
                }

                console.log('Submitting answers:', this.answers);

                const response = await fetch('/api/decisions/answer', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        answers: this.answers
                    })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Failed to submit answers');
                }

                const data = await response.json();
                console.log('Answers submitted successfully:', data);

                // Clear decisions and answers
                this.decisions = [];
                this.answers = {};
                this.pending = false;

                // Reload to check for next bunch
                setTimeout(() => this.loadDecisions(), 1000);

            } catch (error) {
                console.error('Error submitting answers:', error);
                this.error = error.message;
            } finally {
                this.loading = false;
            }
        },

        async skipDecision(decisionId) {
            if (!confirm('Skip this decision? It will be answered with the default/None value.')) {
                return;
            }

            try {
                console.log('Skipping decision:', decisionId);

                // Mark this decision as skipped by setting answer to null
                this.answers[decisionId] = null;

                console.log('Decision marked as skipped (null). Submit all answers to continue.');

                // Show info to user
                alert('Decision marked as skipped. Click "Submit All Answers" to continue.');

            } catch (error) {
                console.error('Error skipping decision:', error);
                alert('Failed to skip decision: ' + error.message);
            }
        },

        async highlightElement(guid) {
            try {
                console.log('Highlighting element:', guid);

                const response = await fetch('/api/blender/highlight', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        guid: guid,
                        zoom: this.highlightSettings.zoom,
                        hide_others: this.highlightSettings.hideOthers,
                        show_context: this.highlightSettings.showContext,
                        context_depth: this.highlightSettings.contextDepth
                    })
                });

                if (!response.ok) throw new Error('Failed to highlight element');

                console.log('Element highlighted successfully');

            } catch (error) {
                console.error('Error highlighting element:', error);
                alert('Failed to highlight element: ' + error.message);
            }
        },

        saveHighlightSettings() {
            localStorage.setItem('highlightSettings', JSON.stringify(this.highlightSettings));
            console.log('Highlight settings saved:', this.highlightSettings);
        },

        hasGUID(decision) {
            // Check if decision has a GUID available for highlighting

            console.log('Checking GUID for decision:', decision.id);

            // Check in 'related' - can be string or array
            if (decision.related) {
                if (typeof decision.related === 'string' && decision.related.length > 0) {
                    console.log('Found GUID in related (string):', decision.related);
                    return true;
                }
                if (Array.isArray(decision.related) && decision.related.length > 0) {
                    console.log('Found GUID in related (array):', decision.related);
                    return true;
                }
            }

            // Check in 'context' object
            if (decision.context && typeof decision.context === 'object') {
                if (decision.context.guid || decision.context.GUID) {
                    console.log('Found GUID in context:', decision.context.guid || decision.context.GUID);
                    return true;
                }

                // Check for element property with guid
                if (decision.context.element && typeof decision.context.element === 'object') {
                    if (decision.context.element.guid || decision.context.element.GUID) {
                        console.log('Found GUID in context.element:', decision.context.element.guid || decision.context.element.GUID);
                        return true;
                    }
                }
            }

            console.log('No GUID found for decision:', decision.id);
            return false;
        },

        getGUID(decision) {
            // Extract GUID from decision for highlighting

            // Try 'related' - can be string or array
            if (decision.related) {
                if (typeof decision.related === 'string' && decision.related.length > 0) {
                    console.log('Using GUID from related (string):', decision.related);
                    return decision.related;
                }
                if (Array.isArray(decision.related) && decision.related.length > 0) {
                    console.log('Using GUID from related (array):', decision.related[0]);
                    return decision.related[0];
                }
            }

            // Try 'context' object
            if (decision.context && typeof decision.context === 'object') {
                if (decision.context.guid) {
                    console.log('Using GUID from context.guid:', decision.context.guid);
                    return decision.context.guid;
                }
                if (decision.context.GUID) {
                    console.log('Using GUID from context.GUID:', decision.context.GUID);
                    return decision.context.GUID;
                }

                // Try context.element
                if (decision.context.element && typeof decision.context.element === 'object') {
                    if (decision.context.element.guid) {
                        console.log('Using GUID from context.element.guid:', decision.context.element.guid);
                        return decision.context.element.guid;
                    }
                    if (decision.context.element.GUID) {
                        console.log('Using GUID from context.element.GUID:', decision.context.element.GUID);
                        return decision.context.element.GUID;
                    }
                }
            }

            console.warn('No GUID found for decision:', decision.id);
            return null;
        }
    }));
    // Log Viewer Component
    Alpine.data('logViewer', () => ({
        logs: [],
        loading: false,
        autoRefresh: true,
        filter: '',
        refreshInterval: null,
        logLevel: 'all',  // all | info | warning | error
        showNoise: false,  // hide polling/connection-wait spam by default
        copied: false,

        async init() {
            await this.loadLogs();
            this.refreshInterval = setInterval(() => {
                if (this.autoRefresh) this.loadLogs();
            }, 2000);
        },

        destroy() {
            if (this.refreshInterval) clearInterval(this.refreshInterval);
        },

        async loadLogs() {
            this.loading = true;
            try {
                const params = new URLSearchParams({
                    show_noise: this.showNoise ? 'true' : 'false'
                });
                const response = await fetch(`/api/logs?${params}`);
                if (!response.ok) throw new Error('Failed to load logs');
                const data = await response.json();
                this.logs = data.logs || [];
                if (this.autoRefresh) this.$nextTick(() => this.scrollToBottom());
            } catch (error) {
                console.error('Error loading logs:', error);
            } finally {
                this.loading = false;
            }
        },

        get filteredLogs() {
            return this.logs.filter(log => {
                const matchesFilter = !this.filter ||
                    log.message.toLowerCase().includes(this.filter.toLowerCase());
                const matchesLevel = this.logLevel === 'all' ||
                    log.level.toLowerCase() === this.logLevel;
                return matchesFilter && matchesLevel;
            });
        },

        getLevelClass(level) {
            return {
                'ERROR': 'log-error',
                'WARNING': 'log-warning',
                'INFO': 'log-info',
                'DEBUG': 'log-debug'
            }[level] || 'log-info';
        },

        scrollToBottom() {
            const el = this.$refs.logContainer;
            if (el) el.scrollTop = el.scrollHeight;
        },

        async copyLogs() {
            // Copies what is currently shown, i.e. respecting the filters
            const ok = await copyTextToClipboard(
                formatLogsAsText(this.filteredLogs));
            if (ok) {
                this.copied = true;
                setTimeout(() => { this.copied = false; }, 2000);
            }
        },

        clearFilter() {
            this.filter = '';
        }
    }));

    // Global Settings Component: machine-specific values (install paths
    // etc.) applied to every project as a fallback.
    Alpine.data('globalSettings', () => ({
        known: [],          // suggested entries from the backend
        values: {},         // name -> value for the suggested entries
        custom: [],         // [{key, value}] for everything else
        pathChecks: {},     // name -> true/false (path exists)
        loading: false,
        saving: false,
        saved: false,
        error: null,

        async init() {
            await this.load();
        },

        async load() {
            this.loading = true;
            this.error = null;
            try {
                const response = await fetch('/api/global-settings');
                if (!response.ok) throw new Error('Failed to load global settings');
                this.applyResponse(await response.json());
            } catch (error) {
                console.error('Error loading global settings:', error);
                this.error = error.message;
            } finally {
                this.loading = false;
            }
        },

        // Split the stored map into suggested entries and custom rows
        applyResponse(data) {
            this.known = data.known || [];
            this.pathChecks = data.path_checks || {};

            const stored = data.settings || {};
            const knownNames = this.known.map(k => k.name);

            const values = {};
            this.known.forEach(k => { values[k.name] = stored[k.name] || ''; });
            this.values = values;

            this.custom = Object.entries(stored)
                .filter(([name]) => !knownNames.includes(name))
                .map(([key, value]) => ({ key, value: String(value) }));
        },

        addCustom() {
            this.custom.push({ key: '', value: '' });
        },

        removeCustom(index) {
            this.custom.splice(index, 1);
        },

        async save() {
            this.saving = true;
            this.saved = false;
            this.error = null;

            // Rebuild the flat name -> value map; empty entries are dropped
            const settings = {};
            this.known.forEach(k => {
                const v = (this.values[k.name] || '').trim();
                if (v) settings[k.name] = v;
            });
            this.custom.forEach(row => {
                const key = (row.key || '').trim();
                const value = (row.value || '').trim();
                if (key && value) settings[key] = value;
            });

            try {
                const response = await fetch('/api/global-settings', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ settings })
                });
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Failed to save global settings');
                }
                this.applyResponse(await response.json());
                this.saved = true;
                setTimeout(() => { this.saved = false; }, 3000);
            } catch (error) {
                console.error('Error saving global settings:', error);
                this.error = error.message;
            } finally {
                this.saving = false;
            }
        }
    }));
});

// Log when Alpine is ready
document.addEventListener('alpine:initialized', () => {
    console.log('Alpine.js initialized');
});