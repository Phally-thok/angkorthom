// Main JavaScript for Angkor Thom Education Management System

document.addEventListener('DOMContentLoaded', () => {
    initSearchFilter();
    initModals();
});

// Generic Table Filter
function initSearchFilter() {
    const searchInput = document.getElementById('globalSearch');
    if (!searchInput) return;

    searchInput.addEventListener('keyup', (e) => {
        const query = e.target.value.toLowerCase();
        const rows = document.querySelectorAll('.custom-table tbody tr');

        rows.forEach(row => {
            const text = row.innerText.toLowerCase();
            if (text.includes(query)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
}

// Modal Toggle Functions
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

function initModals() {
    // Close modal when clicking backdrop
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) {
                backdrop.classList.remove('active');
            }
        });
    });
}

// Format Khmer Numbers
function toKhmerNum(num) {
    const khmerDigits = ['០', '១', '២', '៣', '៤', '៥', '៦', '៧', '៨', '៩'];
    return String(num).replace(/\d/g, digit => khmerDigits[digit]);
}
