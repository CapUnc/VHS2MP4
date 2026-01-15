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
