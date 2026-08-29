// Frame-Distill Dashboard Interactions

let currentFilter = 'ALL';
let sortDirection = {
    time: 'asc',
    score: 'desc'
};

document.addEventListener('DOMContentLoaded', () => {
    // Search input listener in top nav / table
    const searchInput = document.getElementById('tableSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', applyFiltersAndSearch);
    }
});

// ==========================================
// 1. Sidebar Collapsible Toggle
// ==========================================
function toggleSidebar() {
    const sidebar = document.getElementById('appSidebar');
    if (sidebar) {
        sidebar.classList.toggle('collapsed');
    }
}

// ==========================================
// 2. Tab Navigation Switcher
// ==========================================
function switchTab(tabId, tabElement) {
    // 1. Update active states on top nav tabs
    const allTabs = document.querySelectorAll('.nav-tab');
    allTabs.forEach(tab => {
        tab.classList.remove('active', 'text-primary', 'border-b-2', 'border-primary', 'bg-surface-container');
        tab.classList.add('text-on-surface-variant');
    });

    if (tabElement) {
        tabElement.classList.remove('text-on-surface-variant');
        tabElement.classList.add('active', 'text-primary', 'border-b-2', 'border-primary', 'bg-surface-container');
    }

    // 2. Hide all tab content panes
    const tabPanes = document.querySelectorAll('.tab-pane');
    tabPanes.forEach(pane => {
        pane.classList.add('hidden');
    });

    // 3. Show target tab pane
    const targetPane = document.getElementById(`tab-content-${tabId}`);
    if (targetPane) {
        targetPane.classList.remove('hidden');
    }
}

// ==========================================
// 3. Filtering & Search Logic (Metrics Tab)
// ==========================================
function setFilter(filterType, btnElement) {
    currentFilter = filterType;
    
    // Switch to metrics tab if we are in another tab
    const metricsTabNav = document.getElementById('navTabMetrics');
    switchTab('metrics', metricsTabNav);

    // Update active filter button states
    const filterButtons = document.querySelectorAll('.filter-btn');
    filterButtons.forEach(btn => {
        btn.classList.remove('bg-primary', 'text-on-primary');
        btn.classList.add('text-on-surface-variant');
    });
    
    if (btnElement) {
        btnElement.classList.remove('text-on-surface-variant');
        btnElement.classList.add('bg-primary', 'text-on-primary');
    }
    
    applyFiltersAndSearch();
}

function applyFiltersAndSearch() {
    const searchInput = document.getElementById('tableSearchInput');
    const query = (searchInput?.value || '').toLowerCase().trim();
    const rows = document.querySelectorAll('#frameTableBody tr');

    rows.forEach(row => {
        const status = row.getAttribute('data-status');
        const filename = (row.getAttribute('data-filename') || '').toLowerCase();
        const timestamp = (row.getAttribute('data-timestamp') || '').toLowerCase();
        const laplacian = (row.getAttribute('data-laplacian') || '').toLowerCase();

        const matchesFilter = (currentFilter === 'ALL') || 
                              (currentFilter === 'KEPT' && status === 'KEPT') || 
                              (currentFilter === 'DISCARDED' && status === 'DISCARDED');

        const matchesSearch = !query || 
                              filename.includes(query) || 
                              timestamp.includes(query) || 
                              laplacian.includes(query);

        if (matchesFilter && matchesSearch) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// ==========================================
// 4. Sorting Logic (Metrics Tab)
// ==========================================
function sortBy(column) {
    const tbody = document.getElementById('frameTableBody');
    if (!tbody) return;
    
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // Toggle sort direction
    sortDirection[column] = sortDirection[column] === 'asc' ? 'desc' : 'asc';
    const isAsc = sortDirection[column] === 'asc';

    // Update sort button icon/indicator
    const icon = document.getElementById(`sortIcon-${column}`);
    if (icon) {
        icon.textContent = isAsc ? 'arrow_upward' : 'arrow_downward';
    }

    rows.sort((a, b) => {
        let valA, valB;
        if (column === 'time') {
            valA = parseFloat(a.getAttribute('data-timestamp-sec')) || 0;
            valB = parseFloat(b.getAttribute('data-timestamp-sec')) || 0;
        } else if (column === 'score') {
            valA = parseFloat(a.getAttribute('data-laplacian')) || 0;
            valB = parseFloat(b.getAttribute('data-laplacian')) || 0;
        }

        return isAsc ? valA - valB : valB - valA;
    });

    rows.forEach(row => tbody.appendChild(row));
}

// ==========================================
// 5. Modal Inspection Logic
// ==========================================
function openModal(filename, timestamp, laplacian, ssim, isKept) {
    const modal = document.getElementById('modalOverlay');
    if (!modal) return;

    document.getElementById('modalTitle').textContent = `INSPECTION :: ${filename}`;
    
    // Load local sample image or fallback
    const modalImg = document.getElementById('modalImg');
    if (modalImg) {
        modalImg.src = `../dev_mock/sample_frames/${filename}`;
        modalImg.onerror = function() {
            this.onerror = null;
            this.src = `https://placehold.co/600x400/131315/4edea3?text=${encodeURIComponent(filename)}`;
        };
    }

    document.getElementById('modalTime').textContent = `${parseFloat(timestamp).toFixed(2)}s`;
    document.getElementById('modalLaplacian').textContent = parseFloat(laplacian).toFixed(1);
    document.getElementById('modalSSIM').textContent = parseFloat(ssim).toFixed(2);

    const statusEl = document.getElementById('modalStatus');
    if (statusEl) {
        statusEl.textContent = isKept ? 'KEPT' : 'DISCARDED';
        statusEl.className = isKept 
            ? 'font-data-md text-secondary border border-secondary px-2 py-0.5 bg-secondary/10' 
            : 'font-data-md text-error border border-error px-2 py-0.5 bg-error/10';
    }

    modal.classList.add('open');
}

function closeModal(event = null, force = false) {
    const modal = document.getElementById('modalOverlay');
    if (modal && (force || (event && event.target === modal))) {
        modal.classList.remove('open');
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal(null, true);
});
