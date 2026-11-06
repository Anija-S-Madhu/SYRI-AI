/**
 * SYRI AI - Client-side Application Scripts
 * Handles modal dialogs, AJAX transaction edits, deletions, and category management.
 */

document.addEventListener('DOMContentLoaded', () => {
    initTransactionManagement();
    initCategoryManagement();
    initBudgetManagement();
});

// Helper: Escape HTML strings to prevent XSS
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Modal Helpers
function openModal(modal) {
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modal) {
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

function showModalAlert(alertId, message) {
    const alertBox = document.getElementById(alertId);
    if (alertBox) {
        alertBox.textContent = message;
        alertBox.style.display = 'block';
    }
}

function hideModalAlert(alertId) {
    const alertBox = document.getElementById(alertId);
    if (alertBox) {
        alertBox.textContent = '';
        alertBox.style.display = 'none';
    }
}

function showBannerAlert(alertElementId, message, category = 'success') {
    const banner = document.getElementById(alertElementId);
    if (!banner) return;
    banner.className = `alert ${category}`;
    banner.textContent = message;
    banner.style.display = 'block';
    banner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    setTimeout(() => {
        if (banner.textContent === message) {
            banner.style.display = 'none';
        }
    }, 4000);
}

// ========================================================
// 1. TRANSACTION MANAGEMENT
// ========================================================
function initTransactionManagement() {
    const transactionsTable = document.getElementById('transactions-table');
    const editModal = document.getElementById('edit-modal');
    const deleteModal = document.getElementById('delete-modal');

    if (!transactionsTable && !editModal && !deleteModal) {
        return;
    }

    let pendingDeleteId = null;

    // ---- Category filtering for Add Transaction form ----
    const addTypeSelect = document.getElementById('add-tx-type');
    const addCategorySelect = document.getElementById('add-tx-category');

    if (addTypeSelect && addCategorySelect) {
        function filterAddCategories() {
            const selectedType = addTypeSelect.value;
            const options = addCategorySelect.querySelectorAll('option[data-type]');

            // Reset category selection when type changes
            addCategorySelect.value = '';

            options.forEach(opt => {
                if (!selectedType || opt.getAttribute('data-type') === selectedType) {
                    opt.style.display = '';
                    opt.disabled = false;
                } else {
                    opt.style.display = 'none';
                    opt.disabled = true;
                }
            });
        }

        addTypeSelect.addEventListener('change', filterAddCategories);
        filterAddCategories(); // Apply filter on page load
    }

    // Helper: Format YYYY-MM-DD into "DD Mon YYYY" (e.g., 04 Nov 2026)
    function formatDisplayDate(isoDateStr) {
        if (!isoDateStr) return '';
        const parts = String(isoDateStr).split('-');
        if (parts.length !== 3) return isoDateStr;
        const day = parts[2].padStart(2, '0');
        const monthIndex = parseInt(parts[1], 10) - 1;
        const year = parts[0];
        const monthNames = [
            'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
        ];
        const month = monthNames[monthIndex] || parts[1];
        return `${day} ${month} ${year}`;
    }

    // Helper: Format amount with INR symbol, sign, and theme color
    function formatCurrencyHtml(amount, type) {
        const num = parseFloat(amount);
        const formatted = isNaN(num) ? '0.00' : num.toFixed(2);
        if (type === 'income') {
            return `<span style="color:#658C78; font-weight: 600;">+ &#8377;${formatted}</span>`;
        }
        return `<span style="color:#C76F86; font-weight: 600;">- &#8377;${formatted}</span>`;
    }

    function checkEmptyState() {
        const tbody = document.getElementById('transactions-tbody');
        const tableWrapper = document.getElementById('transactions-table-wrapper');
        const emptyState = document.getElementById('empty-state-container');

        if (tbody && tbody.children.length === 0) {
            if (tableWrapper) tableWrapper.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
        }
    }

    function filterEditCategories(targetType, selectedCatId = '') {
        const editCatSelect = document.getElementById('edit-tx-category');
        if (!editCatSelect) return;
        const options = editCatSelect.querySelectorAll('option[data-type]');
        options.forEach(opt => {
            if (!targetType || opt.getAttribute('data-type') === targetType) {
                opt.style.display = '';
                opt.disabled = false;
            } else {
                opt.style.display = 'none';
                opt.disabled = true;
            }
        });
        editCatSelect.value = selectedCatId;
    }

    const editTypeSelectElem = document.getElementById('edit-tx-type');
    if (editTypeSelectElem) {
        editTypeSelectElem.addEventListener('change', () => {
            filterEditCategories(editTypeSelectElem.value, '');
        });
    }

    function populateAndOpenEditModal(btn) {
        const id = btn.getAttribute('data-id');
        const type = btn.getAttribute('data-type') || 'expense';
        const categoryId = btn.getAttribute('data-category-id') || '';
        const amount = btn.getAttribute('data-amount') || '';
        const description = btn.getAttribute('data-description') || '';
        const dateVal = btn.getAttribute('data-date') || '';

        const idInput = document.getElementById('edit-tx-id');
        const typeSelect = document.getElementById('edit-tx-type');
        const catSelect = document.getElementById('edit-tx-category');
        const amountInput = document.getElementById('edit-tx-amount');
        const descInput = document.getElementById('edit-tx-description');
        const dateInput = document.getElementById('edit-tx-date');

        if (idInput) idInput.value = id;
        if (typeSelect) typeSelect.value = type;
        if (amountInput) amountInput.value = amount;
        if (descInput) descInput.value = description;
        if (dateInput) dateInput.value = dateVal;

        filterEditCategories(type, categoryId);

        hideModalAlert('edit-modal-alert');
        openModal(editModal);
    }

    const editForm = document.getElementById('edit-transaction-form');
    if (editForm) {
        editForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const id = document.getElementById('edit-tx-id').value;
            const type = document.getElementById('edit-tx-type').value;
            const catSelect = document.getElementById('edit-tx-category');
            const categoryId = catSelect ? catSelect.value : '';
            const amount = document.getElementById('edit-tx-amount').value.trim();
            const description = document.getElementById('edit-tx-description').value.trim();
            const dateVal = document.getElementById('edit-tx-date').value;

            if (!type || !amount || !dateVal) {
                showModalAlert('edit-modal-alert', 'Please fill in all required fields.');
                return;
            }

            const numAmount = parseFloat(amount);
            if (isNaN(numAmount) || numAmount <= 0) {
                showModalAlert('edit-modal-alert', 'Please enter a valid positive amount.');
                return;
            }

            const saveBtn = document.getElementById('save-edit-btn');
            const originalText = saveBtn.textContent;
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';
            hideModalAlert('edit-modal-alert');

            try {
                const response = await fetch(`/api/transactions/${id}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        type: type,
                        category_id: categoryId ? parseInt(categoryId, 10) : null,
                        amount: amount,
                        description: description,
                        date: dateVal
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    showModalAlert('edit-modal-alert', result.error || 'Failed to update transaction.');
                    saveBtn.disabled = false;
                    saveBtn.textContent = originalText;
                    return;
                }

                const txData = result.transaction || {
                    id: id,
                    type: type,
                    category_id: categoryId,
                    category_name: 'Uncategorized',
                    amount: amount,
                    description: description,
                    date: dateVal
                };

                const row = document.getElementById(`tx-row-${id}`);
                if (row) {
                    const descCell = row.querySelector('.tx-cell-desc');
                    const catCell = row.querySelector('.tx-cell-category');
                    const typeCell = row.querySelector('.tx-cell-type');
                    const dateCell = row.querySelector('.tx-cell-date');
                    const amountCell = row.querySelector('.tx-cell-amount');

                    if (descCell) {
                        descCell.innerHTML = `<span class="tx-desc-text">${escapeHtml(txData.description || 'Untitled')}</span>`;
                    }
                    if (catCell) {
                        catCell.innerHTML = `<span class="muted-tag">${escapeHtml(txData.category_name || 'Uncategorized')}</span>`;
                    }
                    if (typeCell) {
                        const capitalized = txData.type.charAt(0).toUpperCase() + txData.type.slice(1);
                        typeCell.innerHTML = `<span class="type-pill ${txData.type}">${capitalized}</span>`;
                    }
                    if (dateCell) {
                        dateCell.setAttribute('data-iso', txData.date);
                        dateCell.textContent = formatDisplayDate(txData.date);
                    }
                    if (amountCell) {
                        const formattedAmt = parseFloat(txData.amount).toFixed(2);
                        amountCell.setAttribute('data-raw', formattedAmt);
                        amountCell.innerHTML = formatCurrencyHtml(txData.amount, txData.type);
                    }

                    const editBtn = row.querySelector('.edit-transaction');
                    if (editBtn) {
                        editBtn.setAttribute('data-type', txData.type);
                        editBtn.setAttribute('data-category-id', txData.category_id || '');
                        editBtn.setAttribute('data-amount', parseFloat(txData.amount).toFixed(2));
                        editBtn.setAttribute('data-description', txData.description || '');
                        editBtn.setAttribute('data-date', txData.date);
                    }

                    const delBtn = row.querySelector('.delete-transaction');
                    if (delBtn) {
                        delBtn.setAttribute('data-description', txData.description || 'Untitled');
                    }

                    row.classList.remove('row-updated');
                    void row.offsetWidth;
                    row.classList.add('row-updated');
                }

                closeModal(editModal);
                showBannerAlert('dynamic-alert', result.message || 'Transaction updated successfully.', 'success');

            } catch (err) {
                showModalAlert('edit-modal-alert', 'Network error. Please try again.');
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = originalText;
            }
        });
    }

    function openDeleteConfirmation(btn) {
        pendingDeleteId = btn.getAttribute('data-id');
        const desc = btn.getAttribute('data-description') || 'Untitled';

        const previewElem = document.getElementById('delete-tx-desc-preview');
        if (previewElem) {
            previewElem.textContent = `"${desc}"`;
        }

        hideModalAlert('delete-modal-alert');
        openModal(deleteModal);
    }

    const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', async () => {
            if (!pendingDeleteId) return;

            const originalText = confirmDeleteBtn.textContent;
            confirmDeleteBtn.disabled = true;
            confirmDeleteBtn.textContent = 'Deleting...';
            hideModalAlert('delete-modal-alert');

            try {
                const response = await fetch(`/api/transactions/${pendingDeleteId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                });

                const result = await response.json();

                if (!response.ok) {
                    showModalAlert('delete-modal-alert', result.error || 'Failed to delete transaction.');
                    confirmDeleteBtn.disabled = false;
                    confirmDeleteBtn.textContent = originalText;
                    return;
                }

                const row = document.getElementById(`tx-row-${pendingDeleteId}`);
                if (row) {
                    row.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
                    row.style.opacity = '0';
                    row.style.transform = 'translateX(12px)';
                    setTimeout(() => {
                        row.remove();
                        checkEmptyState();
                    }, 250);
                }

                closeModal(deleteModal);
                showBannerAlert('dynamic-alert', result.message || 'Transaction deleted successfully.', 'success');

            } catch (err) {
                showModalAlert('delete-modal-alert', 'Network error. Please try again.');
            } finally {
                confirmDeleteBtn.disabled = false;
                confirmDeleteBtn.textContent = originalText;
                pendingDeleteId = null;
            }
        });
    }

    document.addEventListener('click', (e) => {
        const editBtn = e.target.closest('.edit-transaction');
        if (editBtn) {
            populateAndOpenEditModal(editBtn);
            return;
        }

        const deleteBtn = e.target.closest('.delete-transaction');
        if (deleteBtn) {
            openDeleteConfirmation(deleteBtn);
            return;
        }

        if (e.target.matches('#close-edit-modal, #cancel-edit-btn')) {
            closeModal(editModal);
            return;
        }

        if (e.target.matches('#close-delete-modal, #cancel-delete-btn')) {
            closeModal(deleteModal);
            pendingDeleteId = null;
            return;
        }

        if (e.target === editModal) {
            closeModal(editModal);
            return;
        }
        if (e.target === deleteModal) {
            closeModal(deleteModal);
            pendingDeleteId = null;
            return;
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (editModal && editModal.classList.contains('active')) {
                closeModal(editModal);
            }
            if (deleteModal && deleteModal.classList.contains('active')) {
                closeModal(deleteModal);
                pendingDeleteId = null;
            }
        }
    });
}

// ========================================================
// 2. CATEGORY MANAGEMENT
// ========================================================
function initCategoryManagement() {
    const editCatModal = document.getElementById('edit-category-modal');
    const deleteCatModal = document.getElementById('delete-category-modal');

    if (!editCatModal && !deleteCatModal) {
        return;
    }

    let pendingDeleteCatId = null;

    function openEditCategoryModal(btn) {
        const id = btn.getAttribute('data-id');
        const name = btn.getAttribute('data-name') || '';
        const type = btn.getAttribute('data-type') || 'expense';
        const txCount = parseInt(btn.getAttribute('data-tx-count') || '0', 10);

        const idInput = document.getElementById('edit-cat-id');
        const nameInput = document.getElementById('edit-cat-name');
        const typeSelect = document.getElementById('edit-cat-type');
        const typeNote = document.getElementById('edit-cat-type-note');
        const editForm = document.getElementById('edit-category-form');

        if (idInput) idInput.value = id;
        if (nameInput) nameInput.value = name;
        if (typeSelect) {
            typeSelect.value = type;
            if (txCount > 0) {
                typeSelect.disabled = true;
                if (typeNote) typeNote.style.display = 'block';
            } else {
                typeSelect.disabled = false;
                if (typeNote) typeNote.style.display = 'none';
            }
        }
        if (editForm) {
            editForm.action = `/categories/${id}/edit`;
        }

        hideModalAlert('edit-category-modal-alert');
        openModal(editCatModal);
    }

    const editCategoryForm = document.getElementById('edit-category-form');
    if (editCategoryForm) {
        editCategoryForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const id = document.getElementById('edit-cat-id').value;
            const name = document.getElementById('edit-cat-name').value.trim();
            const typeSelect = document.getElementById('edit-cat-type');
            const type = typeSelect ? typeSelect.value : 'expense';

            if (!name) {
                showModalAlert('edit-category-modal-alert', 'Category name is required.');
                return;
            }

            const saveBtn = document.getElementById('save-edit-category-btn');
            const originalText = saveBtn.textContent;
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';
            hideModalAlert('edit-category-modal-alert');

            try {
                const response = await fetch(`/api/categories/${id}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        name: name,
                        type: type
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    showModalAlert('edit-category-modal-alert', result.error || 'Failed to update category.');
                    saveBtn.disabled = false;
                    saveBtn.textContent = originalText;
                    return;
                }

                // Update table row in DOM
                const row = document.getElementById(`cat-row-${id}`);
                if (row) {
                    const nameCell = row.querySelector('.cat-cell-name');
                    if (nameCell) {
                        nameCell.innerHTML = `<strong>${escapeHtml(result.category.name)}</strong>`;
                    }
                    const editBtn = row.querySelector('.edit-category');
                    if (editBtn) {
                        editBtn.setAttribute('data-name', result.category.name);
                        editBtn.setAttribute('data-type', result.category.type);
                    }
                    const delBtn = row.querySelector('.delete-category');
                    if (delBtn) {
                        delBtn.setAttribute('data-name', result.category.name);
                        delBtn.setAttribute('data-type', result.category.type);
                    }
                    row.classList.remove('row-updated');
                    void row.offsetWidth;
                    row.classList.add('row-updated');
                }

                closeModal(editCatModal);
                showBannerAlert('dynamic-category-alert', result.message || 'Category updated successfully.', 'success');

            } catch (err) {
                showModalAlert('edit-category-modal-alert', 'Network error. Please try again.');
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = originalText;
            }
        });
    }

    function openDeleteCategoryConfirmation(btn) {
        pendingDeleteCatId = btn.getAttribute('data-id');
        const name = btn.getAttribute('data-name') || 'this category';
        const txCount = parseInt(btn.getAttribute('data-tx-count') || '0', 10);

        const previewElem = document.getElementById('delete-cat-name-preview');
        if (previewElem) {
            previewElem.textContent = `"${name}"`;
        }

        const warningElem = document.getElementById('delete-category-warning');
        const confirmBtn = document.getElementById('confirm-delete-category-btn');
        const promptElem = document.getElementById('delete-category-prompt');
        const deleteForm = document.getElementById('delete-category-form');

        if (deleteForm) {
            deleteForm.action = `/categories/${pendingDeleteCatId}/delete`;
        }

        hideModalAlert('delete-category-modal-alert');

        if (txCount > 0) {
            if (warningElem) {
                warningElem.textContent = `Cannot delete: this category is currently assigned to ${txCount} transaction(s). Reassign or delete those transactions first.`;
                warningElem.style.display = 'block';
            }
            if (confirmBtn) {
                confirmBtn.disabled = true;
            }
            if (promptElem) {
                promptElem.style.display = 'none';
            }
        } else {
            if (warningElem) {
                warningElem.textContent = '';
                warningElem.style.display = 'none';
            }
            if (confirmBtn) {
                confirmBtn.disabled = false;
            }
            if (promptElem) {
                promptElem.style.display = 'block';
            }
        }

        openModal(deleteCatModal);
    }

    const confirmDeleteCatBtn = document.getElementById('confirm-delete-category-btn');
    if (confirmDeleteCatBtn) {
        confirmDeleteCatBtn.addEventListener('click', async () => {
            if (!pendingDeleteCatId) return;

            const originalText = confirmDeleteCatBtn.textContent;
            confirmDeleteCatBtn.disabled = true;
            confirmDeleteCatBtn.textContent = 'Deleting...';
            hideModalAlert('delete-category-modal-alert');

            try {
                const response = await fetch(`/api/categories/${pendingDeleteCatId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                });

                const result = await response.json();

                if (!response.ok) {
                    showModalAlert('delete-category-modal-alert', result.error || 'Failed to delete category.');
                    confirmDeleteCatBtn.disabled = false;
                    confirmDeleteCatBtn.textContent = originalText;
                    return;
                }

                const row = document.getElementById(`cat-row-${pendingDeleteCatId}`);
                if (row) {
                    const parentTbody = row.closest('tbody');
                    row.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
                    row.style.opacity = '0';
                    row.style.transform = 'translateX(12px)';
                    setTimeout(() => {
                        row.remove();
                        // Update badge count
                        if (parentTbody) {
                            const column = parentTbody.closest('.category-column');
                            if (column) {
                                const badge = column.querySelector('.category-count-badge');
                                if (badge) {
                                    badge.textContent = parentTbody.children.length;
                                }
                                if (parentTbody.children.length === 0) {
                                    const tableWrapper = column.querySelector('.category-table-wrapper');
                                    const emptyState = column.querySelector('.empty-state');
                                    if (tableWrapper) tableWrapper.style.display = 'none';
                                    if (emptyState) emptyState.style.display = 'block';
                                }
                            }
                        }
                    }, 250);
                }

                closeModal(deleteCatModal);
                showBannerAlert('dynamic-category-alert', result.message || 'Category deleted successfully.', 'success');

            } catch (err) {
                showModalAlert('delete-category-modal-alert', 'Network error. Please try again.');
            } finally {
                confirmDeleteCatBtn.disabled = false;
                confirmDeleteCatBtn.textContent = originalText;
                pendingDeleteCatId = null;
            }
        });
    }

    document.addEventListener('click', (e) => {
        const editBtn = e.target.closest('.edit-category');
        if (editBtn) {
            openEditCategoryModal(editBtn);
            return;
        }

        const deleteBtn = e.target.closest('.delete-category');
        if (deleteBtn) {
            openDeleteCategoryConfirmation(deleteBtn);
            return;
        }

        if (e.target.matches('#close-edit-category-modal, #cancel-edit-category-btn')) {
            closeModal(editCatModal);
            return;
        }

        if (e.target.matches('#close-delete-category-modal, #cancel-delete-category-btn')) {
            closeModal(deleteCatModal);
            pendingDeleteCatId = null;
            return;
        }

        if (e.target === editCatModal) {
            closeModal(editCatModal);
            return;
        }
        if (e.target === deleteCatModal) {
            closeModal(deleteCatModal);
            pendingDeleteCatId = null;
            return;
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (editCatModal && editCatModal.classList.contains('active')) {
                closeModal(editCatModal);
            }
            if (deleteCatModal && deleteCatModal.classList.contains('active')) {
                closeModal(deleteCatModal);
                pendingDeleteCatId = null;
            }
        }
    });
}

// ========================================================
// 3. BUDGET MANAGEMENT
// ========================================================
function initBudgetManagement() {
    const editBudgetModal = document.getElementById('edit-budget-modal');
    const deleteBudgetModal = document.getElementById('delete-budget-modal');

    if (!editBudgetModal && !deleteBudgetModal) {
        return;
    }

    let pendingDeleteBudgetId = null;

    const monthNames = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ];

    function openEditBudgetModal(btn) {
        const id = btn.getAttribute('data-id');
        const categoryId = btn.getAttribute('data-category-id') || '';
        const amount = btn.getAttribute('data-amount') || '';
        const month = btn.getAttribute('data-month') || '';
        const year = btn.getAttribute('data-year') || '';

        const idInput = document.getElementById('edit-budget-id');
        const catSelect = document.getElementById('edit-budget-category');
        const amountInput = document.getElementById('edit-budget-amount');
        const monthSelect = document.getElementById('edit-budget-month');
        const yearInput = document.getElementById('edit-budget-year');
        const editForm = document.getElementById('edit-budget-form');

        if (idInput) idInput.value = id;
        if (catSelect) catSelect.value = categoryId;
        if (amountInput) amountInput.value = amount;
        if (monthSelect) monthSelect.value = month;
        if (yearInput) yearInput.value = year;

        if (editForm) {
            editForm.action = `/budgets/${id}/edit`;
        }

        hideModalAlert('edit-budget-modal-alert');
        openModal(editBudgetModal);
    }

    const editBudgetForm = document.getElementById('edit-budget-form');
    if (editBudgetForm) {
        editBudgetForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const id = document.getElementById('edit-budget-id').value;
            const categoryId = document.getElementById('edit-budget-category').value;
            const amount = document.getElementById('edit-budget-amount').value.trim();
            const month = document.getElementById('edit-budget-month').value;
            const year = document.getElementById('edit-budget-year').value.trim();

            if (!categoryId || !amount || !month || !year) {
                showModalAlert('edit-budget-modal-alert', 'Please fill in all fields.');
                return;
            }

            const numAmount = parseFloat(amount);
            if (isNaN(numAmount) || numAmount <= 0) {
                showModalAlert('edit-budget-modal-alert', 'Budget amount must be a positive number.');
                return;
            }

            const saveBtn = document.getElementById('save-edit-budget-btn');
            const originalText = saveBtn.textContent;
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';
            hideModalAlert('edit-budget-modal-alert');

            try {
                const response = await fetch(`/api/budgets/${id}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        category_id: parseInt(categoryId, 10),
                        amount: amount,
                        month: parseInt(month, 10),
                        year: parseInt(year, 10)
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    showModalAlert('edit-budget-modal-alert', result.error || 'Failed to update budget.');
                    saveBtn.disabled = false;
                    saveBtn.textContent = originalText;
                    return;
                }

                const bData = result.budget;
                const card = document.getElementById(`budget-card-${id}`);

                if (card) {
                    // Update title & period
                    const titleElem = card.querySelector('.budget-card-title');
                    const periodElem = card.querySelector('.budget-period-tag');
                    if (titleElem) titleElem.textContent = bData.category_name;
                    if (periodElem) {
                        const mName = monthNames[bData.month] || bData.month;
                        periodElem.textContent = `${mName} ${bData.year}`;
                    }

                    // Update amounts
                    const limitVal = card.querySelector('.amount-val.limit');
                    const remainingVal = card.querySelector('.amount-val.remaining');
                    if (limitVal) limitVal.textContent = `₹${parseFloat(bData.amount).toFixed(2)}`;

                    const remNum = parseFloat(bData.remaining);
                    if (remainingVal) {
                        if (remNum < 0) {
                            remainingVal.className = 'amount-val remaining negative';
                            remainingVal.textContent = `-₹${Math.abs(remNum).toFixed(2)}`;
                        } else {
                            remainingVal.className = 'amount-val remaining positive';
                            remainingVal.textContent = `₹${remNum.toFixed(2)}`;
                        }
                    }

                    // Update badge & card status
                    card.className = `budget-card status-${bData.status}`;
                    const badge = card.querySelector('.budget-badge');
                    if (badge) {
                        badge.className = `budget-badge status-${bData.status}`;
                        if (bData.status === 'overspent') {
                            badge.textContent = `🚨 Over Budget (${bData.percent}%)`;
                        } else if (bData.status === 'warning') {
                            badge.textContent = `⚠️ Caution (${bData.percent}%)`;
                        } else {
                            badge.textContent = `✦ On Track (${bData.percent}%)`;
                        }
                    }

                    // Update progress bar
                    const progressBar = card.querySelector('.budget-progress-bar');
                    if (progressBar) {
                        progressBar.className = `budget-progress-bar status-${bData.status}`;
                        progressBar.style.width = `${Math.min(bData.percent, 100)}%`;
                    }

                    // Update alert slot banner
                    const alertSlot = card.querySelector('.budget-alert-slot');
                    if (alertSlot) {
                        if (bData.status === 'overspent') {
                            alertSlot.innerHTML = `<div class="budget-alert-banner alert error">🚨 <strong>Over Budget!</strong> Exceeded by ₹${Math.abs(remNum).toFixed(2)} (${bData.percent}% spent).</div>`;
                        } else if (bData.status === 'warning') {
                            alertSlot.innerHTML = `<div class="budget-alert-banner alert-warning-box">⚠️ <strong>Warning:</strong> ${bData.percent}% of this budget has been used (₹${remNum.toFixed(2)} remaining).</div>`;
                        } else {
                            alertSlot.innerHTML = '';
                        }
                    }

                    // Update edit button data attributes
                    const editBtn = card.querySelector('.edit-budget');
                    if (editBtn) {
                        editBtn.setAttribute('data-category-id', bData.category_id);
                        editBtn.setAttribute('data-category-name', bData.category_name);
                        editBtn.setAttribute('data-amount', parseFloat(bData.amount).toFixed(2));
                        editBtn.setAttribute('data-month', bData.month);
                        editBtn.setAttribute('data-year', bData.year);
                    }

                    const delBtn = card.querySelector('.delete-budget');
                    if (delBtn) {
                        const mName = monthNames[bData.month] || bData.month;
                        delBtn.setAttribute('data-category-name', bData.category_name);
                        delBtn.setAttribute('data-period', `${mName} ${bData.year}`);
                    }

                    // Flash row
                    card.classList.remove('row-updated');
                    void card.offsetWidth;
                    card.classList.add('row-updated');
                }

                closeModal(editBudgetModal);
                showBannerAlert('dynamic-budget-alert', result.message || 'Budget updated successfully.', 'success');

            } catch (err) {
                showModalAlert('edit-budget-modal-alert', 'Network error. Please try again.');
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = originalText;
            }
        });
    }

    function openDeleteBudgetConfirmation(btn) {
        pendingDeleteBudgetId = btn.getAttribute('data-id');
        const catName = btn.getAttribute('data-category-name') || 'this budget';
        const period = btn.getAttribute('data-period') || '';

        const previewElem = document.getElementById('delete-budget-name-preview');
        if (previewElem) {
            previewElem.textContent = `${catName} (${period})`;
        }

        const deleteForm = document.getElementById('delete-budget-form');
        if (deleteForm) {
            deleteForm.action = `/budgets/${pendingDeleteBudgetId}/delete`;
        }

        hideModalAlert('delete-budget-modal-alert');
        openModal(deleteBudgetModal);
    }

    const confirmDeleteBudgetBtn = document.getElementById('confirm-delete-budget-btn');
    if (confirmDeleteBudgetBtn) {
        confirmDeleteBudgetBtn.addEventListener('click', async () => {
            if (!pendingDeleteBudgetId) return;

            const originalText = confirmDeleteBudgetBtn.textContent;
            confirmDeleteBudgetBtn.disabled = true;
            confirmDeleteBudgetBtn.textContent = 'Deleting...';
            hideModalAlert('delete-budget-modal-alert');

            try {
                const response = await fetch(`/api/budgets/${pendingDeleteBudgetId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                });

                const result = await response.json();

                if (!response.ok) {
                    showModalAlert('delete-budget-modal-alert', result.error || 'Failed to delete budget.');
                    confirmDeleteBudgetBtn.disabled = false;
                    confirmDeleteBudgetBtn.textContent = originalText;
                    return;
                }

                const card = document.getElementById(`budget-card-${pendingDeleteBudgetId}`);
                if (card) {
                    card.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
                    card.style.opacity = '0';
                    card.style.transform = 'scale(0.92)';
                    setTimeout(() => {
                        card.remove();
                        const container = document.getElementById('budgets-container');
                        const emptyState = document.getElementById('empty-budgets-container');
                        if (container && container.children.length === 0) {
                            container.style.display = 'none';
                            if (emptyState) emptyState.style.display = 'block';
                        }
                    }, 250);
                }

                closeModal(deleteBudgetModal);
                showBannerAlert('dynamic-budget-alert', result.message || 'Budget deleted successfully.', 'success');

            } catch (err) {
                showModalAlert('delete-budget-modal-alert', 'Network error. Please try again.');
            } finally {
                confirmDeleteBudgetBtn.disabled = false;
                confirmDeleteBudgetBtn.textContent = originalText;
                pendingDeleteBudgetId = null;
            }
        });
    }

    document.addEventListener('click', (e) => {
        const editBtn = e.target.closest('.edit-budget');
        if (editBtn) {
            openEditBudgetModal(editBtn);
            return;
        }

        const deleteBtn = e.target.closest('.delete-budget');
        if (deleteBtn) {
            openDeleteBudgetConfirmation(deleteBtn);
            return;
        }

        if (e.target.matches('#close-edit-budget-modal, #cancel-edit-budget-btn')) {
            closeModal(editBudgetModal);
            return;
        }

        if (e.target.matches('#close-delete-budget-modal, #cancel-delete-budget-btn')) {
            closeModal(deleteBudgetModal);
            pendingDeleteBudgetId = null;
            return;
        }

        if (e.target === editBudgetModal) {
            closeModal(editBudgetModal);
            return;
        }
        if (e.target === deleteBudgetModal) {
            closeModal(deleteBudgetModal);
            pendingDeleteBudgetId = null;
            return;
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (editBudgetModal && editBudgetModal.classList.contains('active')) {
                closeModal(editBudgetModal);
            }
            if (deleteBudgetModal && deleteBudgetModal.classList.contains('active')) {
                closeModal(deleteBudgetModal);
                pendingDeleteBudgetId = null;
            }
        }
    });
}
