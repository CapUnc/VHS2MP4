(() => {
  const exactSection = document.querySelector('#date-exact');
  const rangeSection = document.querySelector('#date-range');
  const dateTypeInputs = document.querySelectorAll('input[name="date_type"]');

  if (!exactSection || !rangeSection || dateTypeInputs.length === 0) {
    return;
  }

  const updateVisibility = () => {
    const selected = document.querySelector('input[name="date_type"]:checked');
    const value = selected ? selected.value : 'unknown';

    exactSection.style.display = value === 'exact' ? 'block' : 'none';
    rangeSection.style.display = value === 'range' ? 'block' : 'none';
  };

  dateTypeInputs.forEach((input) => {
    input.addEventListener('change', updateVisibility);
  });

  updateVisibility();
})();
