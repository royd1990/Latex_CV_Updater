/**
 * TUI JS — dynamic row management, present-marker, compile polling
 */

// ── EntryManager ──────────────────────────────────────────────────────────

class EntryManager {
  /**
   * @param {string} listId    id of the container div holding entry rows
   * @param {string} templateId  id of the hidden template row
   * @param {string} prefix    form field prefix (e.g. "employment")
   */
  constructor(listId, templateId, prefix) {
    this.list = document.getElementById(listId);
    this.template = document.getElementById(templateId);
    this.prefix = prefix;

    if (!this.list || !this.template) return;

    // Attach remove handlers to any pre-rendered rows
    this.list.querySelectorAll('.entry-row:not(.template)').forEach(row => {
      this._attachRemove(row);
    });
  }

  /** Add a new empty (or pre-filled) row. */
  addRow(data = {}) {
    if (!this.list || !this.template) return;
    const idx = this.list.querySelectorAll('.entry-row:not(.template)').length;
    const clone = this.template.cloneNode(true);
    clone.classList.remove('template');
    clone.removeAttribute('id');
    clone.style.display = '';

    // Replace __IDX__ in all name / id / for attributes
    clone.querySelectorAll('[name]').forEach(el => {
      el.name = el.name.replace(/__IDX__/g, String(idx));
    });
    clone.querySelectorAll('[id]').forEach(el => {
      el.id = el.id.replace(/__IDX__/g, String(idx));
    });
    clone.querySelectorAll('[for]').forEach(el => {
      el.htmlFor = el.htmlFor.replace(/__IDX__/g, String(idx));
    });

    // Populate with data if provided
    Object.entries(data).forEach(([key, val]) => {
      const input = clone.querySelector(`[name="${this.prefix}[${idx}][${key}]"]`);
      if (input) input.value = val;
    });

    // Update row header index label
    const header = clone.querySelector('.entry-idx');
    if (header) header.textContent = `#${idx + 1}`;

    this._attachRemove(clone);
    this.list.appendChild(clone);
  }

  /** Re-index all rows after removal. */
  reIndex() {
    const rows = this.list.querySelectorAll('.entry-row:not(.template)');
    rows.forEach((row, i) => {
      row.querySelectorAll('[name]').forEach(el => {
        el.name = el.name.replace(/\[\d+\]/g, `[${i}]`);
      });
      const header = row.querySelector('.entry-idx');
      if (header) header.textContent = `#${i + 1}`;
    });
  }

  /** Attach remove button handler to a row. */
  _attachRemove(row) {
    const btn = row.querySelector('.remove-row-btn');
    if (btn) {
      btn.addEventListener('click', () => this.removeRow(row));
    }
  }

  /** Remove a row and re-index. */
  removeRow(row) {
    row.remove();
    this.reIndex();
  }
}

// ── Present marker ────────────────────────────────────────────────────────

/**
 * Sets the sibling input's value to the LaTeX present marker.
 * @param {HTMLButtonElement} btn
 */
function setPresent(btn) {
  const wrapper = btn.closest('.input-with-btn');
  if (!wrapper) return;
  const input = wrapper.querySelector('input');
  if (input) {
    input.value = '$\\cdots\\cdot$';
    input.focus();
  }
}

// ── Flash message auto-dismiss ────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Auto-close flashes after 5 seconds
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 5000);

    const closeBtn = el.querySelector('.flash-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => el.remove());
    }
  });

  // Referee mode toggle: show/hide full referee fields (handles short/full/skip)
  const radioFull  = document.getElementById('mode_full');
  const radioShort = document.getElementById('mode_short');
  const radioSkip  = document.getElementById('mode_skip');
  const refereeFields = document.getElementById('referee-fields');

  if (refereeFields) {
    const toggle = () => {
      refereeFields.style.display = (radioFull && radioFull.checked) ? 'block' : 'none';
    };
    toggle();
    [radioFull, radioShort, radioSkip].forEach(r => {
      if (r) r.addEventListener('change', toggle);
    });
  }
});

// ── Compile status polling (placeholder) ─────────────────────────────────

let _pollInterval = null;

function startCompilePolling(statusEl) {
  if (!statusEl) return;
  let dots = 0;
  _pollInterval = setInterval(() => {
    dots = (dots + 1) % 4;
    statusEl.textContent = 'Compiling' + '.'.repeat(dots);
  }, 500);
}

function stopCompilePolling(statusEl, message, success) {
  if (_pollInterval) {
    clearInterval(_pollInterval);
    _pollInterval = null;
  }
  if (statusEl) {
    statusEl.textContent = message;
    statusEl.style.color = success ? 'var(--green)' : 'var(--red)';
  }
}
