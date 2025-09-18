/**
 * Recovery Visualizer JavaScript
 * Interactive table functionality for CivitAI Model Recovery Results
 */

class RecoveryVisualizer {
    constructor() {
        this.data = [];
        this.filteredData = [];
        this.currentSort = { column: null, direction: 'asc' };
        this.filters = {
            search: '',
            status: 'all',
            size: 'all'
        };
        this.isCompactView = false;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadData();
        this.updateTimestamp();
    }
    
    bindEvents() {
        // Search functionality
        const searchInput = document.getElementById('search-input');
        const clearSearch = document.getElementById('clear-search');
        
        searchInput.addEventListener('input', this.debounce((e) => {
            this.filters.search = e.target.value.toLowerCase();
            this.applyFilters();
        }, 300));
        
        clearSearch.addEventListener('click', () => {
            searchInput.value = '';
            this.filters.search = '';
            this.applyFilters();
        });
        
        // Filter controls
        document.getElementById('status-filter').addEventListener('change', (e) => {
            this.filters.status = e.target.value;
            this.applyFilters();
        });
        
        document.getElementById('size-filter').addEventListener('change', (e) => {
            this.filters.size = e.target.value;
            this.applyFilters();
        });
        
        // View toggles
        document.getElementById('toggle-details').addEventListener('click', () => {
            this.setView(false);
        });
        
        document.getElementById('toggle-compact').addEventListener('click', () => {
            this.setView(true);
        });
        
        // Export functionality
        document.getElementById('export-csv').addEventListener('click', () => {
            this.exportData('csv');
        });
        
        document.getElementById('export-json').addEventListener('click', () => {
            this.exportData('json');
        });
        
        // Modal controls
        document.getElementById('modal-close').addEventListener('click', () => {
            this.closeModal();
        });
        
        // Close modal on outside click
        document.getElementById('file-details-modal').addEventListener('click', (e) => {
            if (e.target.id === 'file-details-modal') {
                this.closeModal();
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
            if (e.ctrlKey && e.key === 'f') {
                e.preventDefault();
                document.getElementById('search-input').focus();
            }
        });
        
        // Table sorting
        document.querySelectorAll('.sortable').forEach(header => {
            header.addEventListener('click', () => {
                const column = header.dataset.sort;
                this.sortTable(column);
            });
        });
    }
    
    loadData() {
        // Check if data is embedded in the page
        if (window.recoveryData) {
            this.data = window.recoveryData.results || [];
            this.updateStatistics(window.recoveryData.statistics || {});
            this.applyFilters();
            this.hideLoading();
        } else {
            // Try to load from localStorage or show empty state
            this.showEmptyState();
        }
    }
    
    updateStatistics(stats) {
        document.getElementById('successful-count').textContent = stats.successful || 0;
        document.getElementById('failed-count').textContent = stats.failed || 0;
        document.getElementById('skipped-count').textContent = stats.skipped || 0;
        document.getElementById('duplicates-count').textContent = stats.duplicates || 0;
        document.getElementById('total-files').textContent = stats.total || 0;
        document.getElementById('total-size').textContent = this.formatFileSize(stats.totalSize || 0);
        
        // Update timestamp if available
        if (stats.timestamp) {
            document.getElementById('recovery-timestamp').textContent = 
                `Recovery completed at: ${new Date(stats.timestamp).toLocaleString()}`;
        }
    }
    
    updateTimestamp() {
        document.getElementById('generation-date').textContent = new Date().toLocaleString();
    }
    
    applyFilters() {
        this.filteredData = this.data.filter(item => {
            // Search filter
            if (this.filters.search) {
                const searchableText = [
                    item.filename,
                    item.filepath,
                    item.details,
                    item.status
                ].join(' ').toLowerCase();
                
                if (!searchableText.includes(this.filters.search)) {
                    return false;
                }
            }
            
            // Status filter
            if (this.filters.status !== 'all') {
                const statusMap = {
                    'success': ['success', 'successfully recovered', 'completed'],
                    'failed': ['failed', 'error', 'fail'],
                    'skipped': ['skipped', 'already registered', 'exists'],
                    'duplicate': ['duplicate', 'duplicated']
                };
                
                const statusTerms = statusMap[this.filters.status] || [];
                const itemStatus = item.status.toLowerCase();
                
                if (!statusTerms.some(term => itemStatus.includes(term))) {
                    return false;
                }
            }
            
            // Size filter
            if (this.filters.size !== 'all') {
                const sizeBytes = this.parseFileSize(item.size);
                const sizeMB = sizeBytes / (1024 * 1024);
                const sizeGB = sizeMB / 1024;
                
                switch (this.filters.size) {
                    case 'small':
                        if (sizeMB >= 100) return false;
                        break;
                    case 'medium':
                        if (sizeMB < 100 || sizeGB >= 1) return false;
                        break;
                    case 'large':
                        if (sizeGB < 1 || sizeGB >= 5) return false;
                        break;
                    case 'xlarge':
                        if (sizeGB < 5) return false;
                        break;
                }
            }
            
            return true;
        });
        
        this.updateResultsCount();
        this.renderTable();
    }
    
    sortTable(column) {
        if (this.currentSort.column === column) {
            this.currentSort.direction = this.currentSort.direction === 'asc' ? 'desc' : 'asc';
        } else {
            this.currentSort.column = column;
            this.currentSort.direction = 'asc';
        }
        
        // Update sort indicators
        document.querySelectorAll('.sortable').forEach(header => {
            header.classList.remove('sorted-asc', 'sorted-desc');
        });
        
        const currentHeader = document.querySelector(`[data-sort="${column}"]`);
        currentHeader.classList.add(`sorted-${this.currentSort.direction}`);
        
        // Sort the data
        this.filteredData.sort((a, b) => {
            let aVal = a[column];
            let bVal = b[column];
            
            // Special handling for size sorting
            if (column === 'size') {
                aVal = this.parseFileSize(aVal);
                bVal = this.parseFileSize(bVal);
            }
            
            // Convert to string for consistent comparison
            aVal = String(aVal).toLowerCase();
            bVal = String(bVal).toLowerCase();
            
            if (this.currentSort.direction === 'asc') {
                return aVal.localeCompare(bVal, undefined, { numeric: true });
            } else {
                return bVal.localeCompare(aVal, undefined, { numeric: true });
            }
        });
        
        this.renderTable();
    }
    
    renderTable() {
        const tbody = document.getElementById('table-body');
        tbody.innerHTML = '';
        
        if (this.filteredData.length === 0) {
            this.showEmptyState();
            return;
        }
        
        this.hideEmptyState();
        
        this.filteredData.forEach((item, index) => {
            const row = this.createTableRow(item, index);
            tbody.appendChild(row);
        });
    }
    
    createTableRow(item, index) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="filename-cell">
                <i class="fas fa-file"></i>
                ${this.escapeHtml(item.filename)}
            </td>
            <td class="filepath-cell" title="${this.escapeHtml(item.filepath)}">
                ${this.escapeHtml(this.truncatePath(item.filepath))}
            </td>
            <td class="status-cell">
                ${this.createStatusBadge(item.status)}
            </td>
            <td class="size-cell">
                ${this.formatFileSize(this.parseFileSize(item.size))}
            </td>
            <td class="details-cell" title="${this.escapeHtml(item.details)}">
                ${this.escapeHtml(this.truncateText(item.details, 50))}
            </td>
            <td class="actions-cell">
                <button class="action-btn" onclick="visualizer.showFileDetails(${index})" title="View Details">
                    <i class="fas fa-info-circle"></i>
                </button>
                <button class="action-btn" onclick="visualizer.openFileLocation('${this.escapeHtml(item.filepath)}')" title="Open Location">
                    <i class="fas fa-folder-open"></i>
                </button>
            </td>
        `;
        
        return row;
    }
    
    createStatusBadge(status) {
        const statusLower = status.toLowerCase();
        let badgeClass = 'status-badge';
        let icon = 'fas fa-question-circle';
        
        if (statusLower.includes('success') || statusLower.includes('completed')) {
            badgeClass += ' success';
            icon = 'fas fa-check-circle';
        } else if (statusLower.includes('failed') || statusLower.includes('error')) {
            badgeClass += ' failed';
            icon = 'fas fa-times-circle';
        } else if (statusLower.includes('skipped') || statusLower.includes('exists')) {
            badgeClass += ' skipped';
            icon = 'fas fa-minus-circle';
        } else if (statusLower.includes('duplicate')) {
            badgeClass += ' duplicate';
            icon = 'fas fa-copy';
        }
        
        return `<span class="${badgeClass}"><i class="${icon}"></i>${this.escapeHtml(status)}</span>`;
    }
    
    showFileDetails(index) {
        const item = this.filteredData[index];
        const modal = document.getElementById('file-details-modal');
        const detailsContainer = document.getElementById('modal-file-details');
        
        detailsContainer.innerHTML = `
            <div class="detail-section">
                <h4><i class="fas fa-file"></i> File Information</h4>
                <div class="detail-grid">
                    <div class="detail-item">
                        <strong>Filename:</strong>
                        <span>${this.escapeHtml(item.filename)}</span>
                    </div>
                    <div class="detail-item">
                        <strong>File Path:</strong>
                        <span class="filepath-text">${this.escapeHtml(item.filepath)}</span>
                    </div>
                    <div class="detail-item">
                        <strong>File Size:</strong>
                        <span>${this.formatFileSize(this.parseFileSize(item.size))}</span>
                    </div>
                    <div class="detail-item">
                        <strong>Status:</strong>
                        <span>${this.createStatusBadge(item.status)}</span>
                    </div>
                </div>
            </div>
            <div class="detail-section">
                <h4><i class="fas fa-list-ul"></i> Recovery Details</h4>
                <div class="detail-content">
                    ${this.escapeHtml(item.details)}
                </div>
            </div>
            ${item.duplicate_files && item.duplicate_files.length > 0 ? `
                <div class="detail-section">
                    <h4><i class="fas fa-copy"></i> Duplicate Files Detected</h4>
                    <div class="detail-content">
                        <p class="duplicate-info">This file shares the same hash (identical content) with the following files:</p>
                        <div class="duplicate-files-list">
                            ${item.duplicate_files.map(duplicateFile => `
                                <div class="duplicate-file-item">
                                    <i class="fas fa-file"></i>
                                    <div class="duplicate-file-info">
                                        <div class="duplicate-filename">${this.escapeHtml(this.getFilenameFromPath(duplicateFile))}</div>
                                        <div class="duplicate-filepath">${this.escapeHtml(duplicateFile)}</div>
                                    </div>
                                    <button class="duplicate-action-btn" onclick="visualizer.openFileLocation('${this.escapeHtml(duplicateFile)}')" title="Open Location">
                                        <i class="fas fa-folder-open"></i>
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                        <div class="duplicate-note">
                            <i class="fas fa-info-circle"></i>
                            <span>These files have identical content but may have different names or locations.</span>
                        </div>
                    </div>
                </div>
            ` : ''}
            ${item.modelId ? `
                <div class="detail-section">
                    <h4><i class="fas fa-cube"></i> Model Information</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <strong>Model ID:</strong>
                            <span>${this.escapeHtml(item.modelId)}</span>
                        </div>
                        <div class="detail-item">
                            <strong>Version ID:</strong>
                            <span>${this.escapeHtml(item.versionId || 'N/A')}</span>
                        </div>
                        <div class="detail-item">
                            <strong>Model Name:</strong>
                            <span>${this.escapeHtml(item.modelName || 'N/A')}</span>
                        </div>
                    </div>
                </div>
            ` : ''}
        `;
        
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
    
    closeModal() {
        const modal = document.getElementById('file-details-modal');
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
    
    openFileLocation(filepath) {
        // This would typically be handled by the Python application
        // For now, just copy the path to clipboard
        navigator.clipboard.writeText(filepath).then(() => {
            this.showNotification('File path copied to clipboard', 'info');
        }).catch(() => {
            this.showNotification('Could not copy file path', 'error');
        });
    }
    
    setView(compact) {
        this.isCompactView = compact;
        const container = document.querySelector('.container');
        
        if (compact) {
            container.classList.add('compact-view');
            document.getElementById('toggle-compact').classList.add('active');
            document.getElementById('toggle-details').classList.remove('active');
        } else {
            container.classList.remove('compact-view');
            document.getElementById('toggle-details').classList.add('active');
            document.getElementById('toggle-compact').classList.remove('active');
        }
    }
    
    exportData(format) {
        const exportData = this.filteredData.map(item => ({
            filename: item.filename,
            filepath: item.filepath,
            status: item.status,
            size: item.size,
            details: item.details,
            ...(item.modelId && { modelId: item.modelId }),
            ...(item.versionId && { versionId: item.versionId }),
            ...(item.modelName && { modelName: item.modelName })
        }));
        
        if (format === 'csv') {
            this.exportCSV(exportData);
        } else if (format === 'json') {
            this.exportJSON(exportData);
        }
    }
    
    exportCSV(data) {
        if (data.length === 0) {
            this.showNotification('No data to export', 'warning');
            return;
        }
        
        const headers = Object.keys(data[0]);
        const csvContent = [
            headers.join(','),
            ...data.map(row => 
                headers.map(header => 
                    `"${String(row[header] || '').replace(/"/g, '""')}"`
                ).join(',')
            )
        ].join('\n');
        
        this.downloadFile(csvContent, 'recovery-results.csv', 'text/csv');
    }
    
    exportJSON(data) {
        const jsonContent = JSON.stringify({
            exported: new Date().toISOString(),
            total: data.length,
            results: data
        }, null, 2);
        
        this.downloadFile(jsonContent, 'recovery-results.json', 'application/json');
    }
    
    downloadFile(content, filename, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        this.showNotification(`Exported ${filename}`, 'success');
    }
    
    updateResultsCount() {
        document.getElementById('filtered-count').textContent = this.filteredData.length;
        document.getElementById('total-count').textContent = this.data.length;
    }
    
    hideLoading() {
        document.getElementById('loading-state').style.display = 'none';
    }
    
    showEmptyState() {
        document.getElementById('loading-state').style.display = 'none';
        document.getElementById('empty-state').style.display = 'flex';
    }
    
    hideEmptyState() {
        document.getElementById('empty-state').style.display = 'none';
    }
    
    showNotification(message, type = 'info') {
        // Create a simple notification system
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'times' : 'info'}"></i>
            ${message}
        `;
        
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--secondary-bg);
            color: var(--text-primary);
            padding: 12px 16px;
            border-radius: var(--radius-md);
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-lg);
            z-index: 2000;
            display: flex;
            align-items: center;
            gap: 8px;
            max-width: 300px;
            transition: var(--transition-normal);
        `;
        
        if (type === 'success') {
            notification.style.borderColor = 'var(--success-color)';
        } else if (type === 'error') {
            notification.style.borderColor = 'var(--error-color)';
        } else if (type === 'warning') {
            notification.style.borderColor = 'var(--warning-color)';
        }
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }
    
    // Utility functions
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
    
    truncatePath(path, maxLength = 50) {
        if (path.length <= maxLength) return path;
        const parts = path.split(/[\/\\]/);
        if (parts.length <= 2) return path;
        
        const filename = parts[parts.length - 1];
        const start = parts[0];
        return `${start}/.../${filename}`;
    }
    
    getFilenameFromPath(filepath) {
        return filepath.split(/[\/\\]/).pop() || filepath;
    }
    
    parseFileSize(sizeStr) {
        if (typeof sizeStr === 'number') return sizeStr;
        
        const match = String(sizeStr).match(/^([\d.]+)\s*([KMGT]?B)?$/i);
        if (!match) return 0;
        
        const value = parseFloat(match[1]);
        const unit = (match[2] || 'B').toUpperCase();
        
        const multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 * 1024,
            'GB': 1024 * 1024 * 1024,
            'TB': 1024 * 1024 * 1024 * 1024
        };
        
        return Math.round(value * (multipliers[unit] || 1));
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
    }
}

// Initialize the visualizer when the page loads
let visualizer;
document.addEventListener('DOMContentLoaded', () => {
    visualizer = new RecoveryVisualizer();
});

// Global function for external data injection
window.setRecoveryData = function(data) {
    window.recoveryData = data;
    if (visualizer) {
        visualizer.data = data.results || [];
        visualizer.updateStatistics(data.statistics || {});
        visualizer.applyFilters();
        visualizer.hideLoading();
    }
};