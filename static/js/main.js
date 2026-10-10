/**
 * DocExtract AI - Client UI & GSAP Animation Engine
 */

document.addEventListener('DOMContentLoaded', () => {
  initPageAnimations();
  initLineItemsTable();
  initUploadDropzone();
  initModals();
  initAlertDismissal();
  initNumberCounters();
});

/**
 * GSAP Page & Element Entrance Animations
 */
function initPageAnimations() {
  if (!window.gsap) return;

  // Stagger Metric Cards
  const metricCards = document.querySelectorAll('.metric-card');
  if (metricCards.length > 0) {
    gsap.from(metricCards, {
      y: 18,
      opacity: 0,
      duration: 0.5,
      stagger: 0.08,
      ease: 'power2.out',
      clearProps: 'transform'
    });
  }

  // Cards Entrance
  const cards = document.querySelectorAll('.card');
  if (cards.length > 0) {
    gsap.from(cards, {
      y: 20,
      opacity: 0,
      duration: 0.6,
      stagger: 0.1,
      delay: 0.1,
      ease: 'power3.out',
      clearProps: 'transform'
    });
  }

  // Table Rows Micro Stagger
  const tableRows = document.querySelectorAll('.table tbody tr');
  if (tableRows.length > 0 && tableRows.length <= 15) {
    gsap.from(tableRows, {
      opacity: 0,
      y: 10,
      duration: 0.35,
      stagger: 0.04,
      delay: 0.2,
      ease: 'power2.out',
      clearProps: 'transform'
    });
  }

  // Animate Confidence Progress Bars
  document.querySelectorAll('.document-viewer, .editor-pane').forEach((el, idx) => {
    gsap.from(el, {
      opacity: 0,
      y: 15,
      duration: 0.5,
      delay: idx * 0.1,
      ease: 'power2.out'
    });
  });
}

/**
 * Animated Number Counters for KPIs
 */
function initNumberCounters() {
  if (!window.gsap) return;

  document.querySelectorAll('.metric-value').forEach(el => {
    const text = el.textContent.trim();
    if (text.startsWith('$')) {
      const targetVal = parseFloat(text.replace('$', '').replace(/,/g, ''));
      if (!isNaN(targetVal)) {
        const counterObj = { val: 0 };
        gsap.to(counterObj, {
          val: targetVal,
          duration: 1.2,
          ease: 'power2.out',
          onUpdate: () => {
            el.textContent = '$' + counterObj.val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          }
        });
      }
    } else if (text.endsWith('%')) {
      const targetVal = parseInt(text.replace('%', ''), 10);
      if (!isNaN(targetVal)) {
        const counterObj = { val: 0 };
        gsap.to(counterObj, {
          val: targetVal,
          duration: 1.0,
          ease: 'power2.out',
          onUpdate: () => {
            el.textContent = Math.round(counterObj.val) + '%';
          }
        });
      }
    }
  });
}

/**
 * Dynamic Line Items Table in Invoice Review UI with GSAP Row Animations
 */
function initLineItemsTable() {
  const lineTable = document.getElementById('line-items-tbody');
  const addLineBtn = document.getElementById('add-line-btn');
  const subtotalInput = document.getElementById('id_subtotal');
  const taxInput = document.getElementById('id_tax_amount');
  const totalInput = document.getElementById('id_total_amount');

  if (!lineTable) return;

  // Add new line item row with GSAP animation
  if (addLineBtn) {
    addLineBtn.addEventListener('click', () => {
      const rowCount = lineTable.querySelectorAll('tr.line-row').length + 1;
      const accountOptionsHtml = document.getElementById('account-options-template')?.innerHTML || '';

      const tr = document.createElement('tr');
      tr.className = 'line-row';
      tr.innerHTML = `
        <td style="text-align: center; font-weight: 600; color: var(--text-muted);">${rowCount}</td>
        <td>
          <input type="hidden" name="line_id[]" value="">
          <input type="text" name="line_description[]" class="form-control line-desc-input" placeholder="Line description..." required>
          <div class="suggestion-container"></div>
        </td>
        <td style="width: 90px;">
          <input type="number" name="line_quantity[]" class="form-control form-control-mono line-qty-input" value="1.00" step="0.01" min="0">
        </td>
        <td style="width: 120px;">
          <input type="number" name="line_unit_price[]" class="form-control form-control-mono line-price-input" value="0.00" step="0.01" min="0">
        </td>
        <td style="width: 130px;">
          <input type="number" name="line_total[]" class="form-control form-control-mono line-total-input" value="0.00" step="0.01" min="0">
        </td>
        <td style="width: 220px;">
          <select name="line_account_code[]" class="form-select line-account-select">
            ${accountOptionsHtml}
          </select>
        </td>
        <td style="text-align: center; width: 50px;">
          <button type="button" class="btn btn-secondary btn-sm remove-line-btn" title="Remove line" style="color: #ef4444; padding: 4px 8px;">✕</button>
        </td>
      `;

      lineTable.appendChild(tr);
      attachRowEvents(tr);
      recalculateTotals();

      if (window.gsap) {
        gsap.fromTo(tr, 
          { opacity: 0, y: -10, backgroundColor: '#ecfdf5' },
          { opacity: 1, y: 0, backgroundColor: '#ffffff', duration: 0.5, ease: 'power2.out', clearProps: 'backgroundColor,transform' }
        );
      }
    });
  }

  // Attach events to all existing rows
  lineTable.querySelectorAll('tr.line-row').forEach(row => {
    attachRowEvents(row);
  });

  if (subtotalInput) subtotalInput.addEventListener('input', updateGrandTotal);
  if (taxInput) taxInput.addEventListener('input', updateGrandTotal);

  function attachRowEvents(row) {
    const qtyInput = row.querySelector('.line-qty-input');
    const priceInput = row.querySelector('.line-price-input');
    const totalInput = row.querySelector('.line-total-input');
    const descInput = row.querySelector('.line-desc-input');
    const removeBtn = row.querySelector('.remove-line-btn');
    const accountSelect = row.querySelector('.line-account-select');
    const suggestionContainer = row.querySelector('.suggestion-container');

    const calcRowTotal = () => {
      const qty = parseFloat(qtyInput?.value || 0);
      const price = parseFloat(priceInput?.value || 0);
      if (totalInput) {
        totalInput.value = (qty * price).toFixed(2);
      }
      recalculateTotals();
    };

    if (qtyInput) qtyInput.addEventListener('input', calcRowTotal);
    if (priceInput) priceInput.addEventListener('input', calcRowTotal);
    if (totalInput) totalInput.addEventListener('input', recalculateTotals);

    // Dynamic Account Code Suggestion with debounce
    let debounceTimer;
    if (descInput) {
      descInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          fetchAccountSuggestion(descInput.value, accountSelect, suggestionContainer);
        }, 400);
      });
    }

    // Remove row with GSAP exit animation
    if (removeBtn) {
      removeBtn.addEventListener('click', () => {
        if (window.gsap) {
          gsap.to(row, {
            opacity: 0,
            x: -20,
            scale: 0.95,
            duration: 0.25,
            ease: 'power2.in',
            onComplete: () => {
              row.remove();
              recalculateTotals();
              renumberRows();
            }
          });
        } else {
          row.remove();
          recalculateTotals();
          renumberRows();
        }
      });
    }
  }

  function renumberRows() {
    lineTable.querySelectorAll('tr.line-row').forEach((row, idx) => {
      const firstCol = row.querySelector('td:first-child');
      if (firstCol) firstCol.textContent = idx + 1;
    });
  }

  function recalculateTotals() {
    let sum = 0;
    lineTable.querySelectorAll('.line-total-input').forEach(inp => {
      sum += parseFloat(inp.value || 0);
    });

    if (subtotalInput) {
      subtotalInput.value = sum.toFixed(2);
    }
    updateGrandTotal();
  }

  function updateGrandTotal() {
    const subtotal = parseFloat(subtotalInput?.value || 0);
    const tax = parseFloat(taxInput?.value || 0);
    if (totalInput) {
      totalInput.value = (subtotal + tax).toFixed(2);
    }
  }

  function fetchAccountSuggestion(description, selectEl, containerEl) {
    if (!description || description.trim().length < 3) return;

    const supplierSelect = document.getElementById('id_supplier_id');
    const supplierId = supplierSelect ? supplierSelect.value : '';
    const supplierName = document.getElementById('id_supplier_name_raw')?.value || '';

    fetch(`/api/suggest-account/?description=${encodeURIComponent(description)}&supplier_id=${encodeURIComponent(supplierId)}&supplier_name=${encodeURIComponent(supplierName)}`)
      .then(res => res.json())
      .then(data => {
        if (!containerEl) return;
        if (data.has_suggestion && data.account_id) {
          containerEl.innerHTML = `
            <div class="suggestion-chip" title="${data.reason}">
              <span>✨ AI Match: ${data.account_code} (${Math.round(data.confidence * 100)}%)</span>
            </div>
          `;
          if (selectEl && !selectEl.value) {
            selectEl.value = data.account_id;
          }
        } else {
          containerEl.innerHTML = `
            <div class="suggestion-chip none" title="${data.reason}">
              <span>No history match — manual code required</span>
            </div>
          `;
        }

        if (window.gsap) {
          gsap.from(containerEl.querySelector('.suggestion-chip'), {
            opacity: 0,
            scale: 0.9,
            duration: 0.3,
            ease: 'back.out(1.5)'
          });
        }
      })
      .catch(err => console.error('Suggestion fetch error:', err));
  }
}

/**
 * Initialize Drag and Drop Upload Interface
 */
function initUploadDropzone() {
  const dropzone = document.getElementById('upload-dropzone');
  const fileInput = document.getElementById('id_document_file');
  const fileInfo = document.getElementById('upload-file-info');
  const fileNameDisplay = document.getElementById('upload-file-name');
  const fileSizeDisplay = document.getElementById('upload-file-size');

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
      if (window.gsap) {
        gsap.to(dropzone, { scale: 1.015, duration: 0.2, ease: 'power1.out' });
      }
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
      if (window.gsap) {
        gsap.to(dropzone, { scale: 1, duration: 0.2, ease: 'power1.out' });
      }
    });
  });

  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      fileInput.files = e.dataTransfer.files;
      displaySelectedFile(fileInput.files[0]);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      displaySelectedFile(fileInput.files[0]);
    }
  });

  function displaySelectedFile(file) {
    if (!file) return;
    if (fileNameDisplay) fileNameDisplay.textContent = file.name;
    if (fileSizeDisplay) fileSizeDisplay.textContent = `(${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
    if (fileInfo) {
      fileInfo.style.display = 'inline-block';
      if (window.gsap) {
        gsap.fromTo(fileInfo, { opacity: 0, y: 8, scale: 0.95 }, { opacity: 1, y: 0, scale: 1, duration: 0.35, ease: 'back.out(1.5)' });
      }
    }
  }
}

/**
 * GSAP Animated Modals
 */
function initModals() {
  document.querySelectorAll('[data-modal-target]').forEach(trigger => {
    trigger.addEventListener('click', () => {
      const targetId = trigger.getAttribute('data-modal-target');
      const modal = document.getElementById(targetId);
      if (modal) {
        openModal(modal);
      }
    });
  });

  document.querySelectorAll('[data-modal-close]').forEach(closeBtn => {
    closeBtn.addEventListener('click', () => {
      const modal = closeBtn.closest('.modal-overlay');
      if (modal) closeModal(modal);
    });
  });

  document.querySelectorAll('.modal-overlay').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeModal(modal);
      }
    });
  });

  function openModal(modal) {
    modal.classList.add('active');
    const modalBox = modal.querySelector('.modal-box');
    if (window.gsap) {
      gsap.fromTo(modal, { opacity: 0 }, { opacity: 1, duration: 0.25 });
      if (modalBox) {
        gsap.fromTo(modalBox, 
          { opacity: 0, scale: 0.92, y: 15 },
          { opacity: 1, scale: 1, y: 0, duration: 0.35, ease: 'back.out(1.4)' }
        );
      }
    } else {
      modal.style.opacity = '1';
    }
  }

  function closeModal(modal) {
    const modalBox = modal.querySelector('.modal-box');
    if (window.gsap) {
      gsap.to(modalBox, { opacity: 0, scale: 0.94, y: 8, duration: 0.2, ease: 'power2.in' });
      gsap.to(modal, {
        opacity: 0,
        duration: 0.2,
        onComplete: () => {
          modal.classList.remove('active');
        }
      });
    } else {
      modal.classList.remove('active');
    }
  }
}

/**
 * Auto-dismiss Alert Messages with GSAP
 */
function initAlertDismissal() {
  document.querySelectorAll('.alert').forEach(alert => {
    if (window.gsap) {
      gsap.from(alert, {
        opacity: 0,
        y: -12,
        duration: 0.4,
        ease: 'power2.out'
      });
    }

    setTimeout(() => {
      if (window.gsap) {
        gsap.to(alert, {
          opacity: 0,
          y: -10,
          duration: 0.4,
          ease: 'power2.in',
          onComplete: () => alert.remove()
        });
      } else {
        alert.remove();
      }
    }, 6000);
  });
}
