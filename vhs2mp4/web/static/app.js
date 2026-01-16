(() => {
  const exactSection = document.querySelector('#date-exact');
  const rangeSection = document.querySelector('#date-range');
  const dateTypeInputs = document.querySelectorAll('input[name="date_type"]');
  const lockSection = document.querySelector('#date-lock');
  const lockCheckbox = lockSection?.querySelector('input[name="date_locked"]') ?? null;
  const lockText = document.querySelector('#date-lock-text');

  if (!exactSection || !rangeSection || dateTypeInputs.length === 0) {
    return;
  }

  const updateVisibility = () => {
    const selected = document.querySelector('input[name="date_type"]:checked');
    const value = selected ? selected.value : 'unknown';

    exactSection.style.display = value === 'exact' ? 'block' : 'none';
    rangeSection.style.display = value === 'range' ? 'block' : 'none';
    if (lockSection) {
      const isUnknown = value === 'unknown';
      lockSection.style.display = isUnknown ? 'none' : 'block';
      if (lockCheckbox) {
        lockCheckbox.disabled = isUnknown;
        if (isUnknown) {
          lockCheckbox.checked = false;
        }
      }
      if (lockText) {
        lockText.textContent =
          value === 'range'
            ? 'Lock Date (AI will not change the range you entered)'
            : 'Lock Date (AI will not change the date you entered)';
      }
    }
  };

  dateTypeInputs.forEach((input) => {
    input.addEventListener('change', updateVisibility);
  });

  updateVisibility();
})();

(() => {
  const labelInput = document.querySelector('#tape-label-text');
  const titleInput = document.querySelector('#tape-title');

  if (!labelInput || !titleInput) {
    return;
  }

  let titleAutofilled = false;

  const syncTitleFromLabel = () => {
    const labelValue = labelInput.value.trim();
    titleInput.value = labelValue;
    titleAutofilled = Boolean(labelValue);
  };

  const shouldAutofill = () => titleInput.value.trim() === '' || titleAutofilled;

  labelInput.addEventListener('input', () => {
    if (shouldAutofill()) {
      syncTitleFromLabel();
    }
  });

  titleInput.addEventListener('input', () => {
    titleAutofilled = false;
  });

  if (titleInput.value.trim() === '' && labelInput.value.trim() !== '') {
    syncTitleFromLabel();
  }
})();

(() => {
  const tagInput = document.querySelector('#tag-entry');
  const tagChips = document.querySelector('#tag-chips');
  const tagHidden = document.querySelector('#tags-json');
  const suggestionButtons = document.querySelectorAll('.tag-suggestion');

  if (!tagInput || !tagChips || !tagHidden) {
    return;
  }

  const tags = [];
  const tagSet = new Set();

  const syncHiddenInput = () => {
    tagHidden.value = JSON.stringify(tags);
  };

  const renderTags = () => {
    tagChips.innerHTML = '';
    tags.forEach((tag) => {
      const chip = document.createElement('span');
      chip.className = 'tag-chip';
      chip.textContent = tag;

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'tag-remove';
      remove.textContent = 'x';
      remove.setAttribute('aria-label', `Remove tag ${tag}`);
      remove.addEventListener('click', () => {
        const index = tags.indexOf(tag);
        if (index >= 0) {
          tags.splice(index, 1);
          tagSet.delete(tag.toLowerCase());
          renderTags();
          syncHiddenInput();
        }
      });

      chip.appendChild(remove);
      tagChips.appendChild(chip);
    });
  };

  const addTag = (rawTag) => {
    const cleaned = rawTag.trim();
    if (!cleaned) {
      return;
    }
    const key = cleaned.toLowerCase();
    if (tagSet.has(key)) {
      return;
    }
    tagSet.add(key);
    tags.push(cleaned);
    renderTags();
    syncHiddenInput();
  };

  const hydrateTags = () => {
    try {
      const initial = JSON.parse(tagHidden.value || '[]');
      if (Array.isArray(initial)) {
        initial.forEach((tag) => {
          if (typeof tag === 'string') {
            addTag(tag);
          }
        });
      }
    } catch (error) {
      // Leave tags empty if parsing fails.
    }
  };

  tagInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addTag(tagInput.value);
      tagInput.value = '';
    }
  });

  suggestionButtons.forEach((button) => {
    button.addEventListener('click', () => {
      addTag(button.dataset.tag || button.textContent || '');
    });
  });

  hydrateTags();
  syncHiddenInput();
})();

(() => {
  const jobCard = document.querySelector('[data-job-id]');
  if (!jobCard) {
    return;
  }

  const jobId = jobCard.dataset.jobId;
  const backUrl = jobCard.dataset.backUrl || '/';
  const statusEl = document.querySelector('#job-status');
  const progressEl = document.querySelector('#job-progress');
  const percentEl = document.querySelector('#job-percent');
  const stepEl = document.querySelector('#job-step');
  const detailEl = document.querySelector('#job-detail');
  const errorEl = document.querySelector('#job-error');
  const errorTextEl = document.querySelector('#job-error-text');
  const cancelButton = document.querySelector('#job-cancel-button');
  const backLink = document.querySelector('#job-back-link');

  if (backLink) {
    backLink.href = backUrl;
  }

  const updateDisplay = (data) => {
    if (statusEl) {
      statusEl.textContent = data.status;
    }
    if (progressEl) {
      progressEl.value = data.percent ?? 0;
    }
    if (percentEl) {
      percentEl.textContent = `${data.percent ?? 0}%`;
    }
    if (stepEl) {
      stepEl.textContent = data.current_step || 'Queued';
    }
    if (detailEl) {
      detailEl.textContent = data.detail || '';
    }
  };

  const showError = (message) => {
    if (errorTextEl) {
      errorTextEl.textContent = message || 'Unknown error.';
    }
    if (errorEl) {
      errorEl.hidden = false;
    }
  };

  const handleTerminalState = (data) => {
    if (cancelButton) {
      cancelButton.disabled = true;
    }
    if (data.status === 'success') {
      const redirectUrl = data.result?.redirect_url || '/';
      window.location.assign(redirectUrl);
      return true;
    }
    if (['failed', 'stale', 'canceled'].includes(data.status)) {
      const message =
        data.error_text ||
        (data.status === 'canceled'
          ? 'Job canceled.'
          : 'Job failed. See details below.');
      showError(message);
      return true;
    }
    return false;
  };

  const pollStatus = async () => {
    try {
      const response = await fetch(`/jobs/${jobId}/status`, { cache: 'no-store' });
      if (!response.ok) {
        throw new Error('Unable to fetch job status.');
      }
      const data = await response.json();
      updateDisplay(data);
      if (handleTerminalState(data)) {
        clearInterval(timer);
      }
    } catch (error) {
      if (statusEl) {
        statusEl.textContent = 'connection error';
      }
      showError('Unable to reach the server. Please try again.');
      if (cancelButton) {
        cancelButton.disabled = true;
      }
      clearInterval(timer);
    }
  };

  const timer = setInterval(pollStatus, 750);
  pollStatus();
})();
