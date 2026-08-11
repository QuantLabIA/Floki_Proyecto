const openModal = (id) => {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  setTimeout(() => modal.querySelector('input, select, textarea')?.focus(), 50);
};

const closeModal = (modal) => {
  if (!modal) return;
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
};

document.querySelectorAll('[data-modal-open]').forEach((button) => {
  button.addEventListener('click', () => openModal(button.dataset.modalOpen));
});
document.querySelectorAll('[data-modal-close]').forEach((button) => {
  button.addEventListener('click', () => closeModal(button.closest('.modal')));
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeModal(document.querySelector('.modal.open'));
});

document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

const categorySelect = document.querySelector('[data-category-select]');
const priceInput = document.querySelector('[data-price-input]');
const promoterField = document.querySelector('[data-promoter-field]');
const entryCategories = new Set(['general', 'free']);

const updateSaleFields = () => {
  if (!categorySelect || !priceInput) return;
  const selected = categorySelect.options[categorySelect.selectedIndex];
  const presetPrice = selected?.dataset.price;
  if (categorySelect.value === 'free') {
    priceInput.value = '0';
    priceInput.setAttribute('readonly', 'readonly');
  } else {
    priceInput.removeAttribute('readonly');
    if (presetPrice !== undefined) priceInput.value = presetPrice;
  }
  if (promoterField) promoterField.hidden = !entryCategories.has(categorySelect.value);
};

categorySelect?.addEventListener('change', updateSaleFields);
document.querySelectorAll('[data-quick-category]').forEach((button) => {
  button.addEventListener('click', () => {
    if (!categorySelect || !priceInput) return;
    categorySelect.value = button.dataset.quickCategory;
    priceInput.value = button.dataset.quickPrice || '0';
    updateSaleFields();
  });
});
updateSaleFields();

setTimeout(() => document.querySelectorAll('.flash').forEach((element) => element.remove()), 4500);
// v2.8.5: modo estable online. Voucher RRPP fijo en $0 y una sola consumición.
// Desregistramos cualquier Service Worker anterior y limpiamos sólo cachés de Floki.
// NO borramos IndexedDB para no perder posibles operaciones pendientes de pruebas anteriores.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.map((registration) => registration.unregister()));
      if ('caches' in window) {
        const keys = await caches.keys();
        await Promise.all(keys.filter((key) => key.startsWith('floki-manager-')).map((key) => caches.delete(key)));
      }
    } catch (_) { /* Floki funciona 100% online sin Service Worker. */ }
  }, { once: true });
}

// Floki Manager v1.2: sincroniza los controles globales con todos los botones rápidos.
const globalPayment = document.querySelector('[data-global-payment]');
const globalQuantity = document.querySelector('[data-global-quantity]');
const globalPromoter = document.querySelector('[data-global-promoter]');

const syncQuickForms = () => {
  document.querySelectorAll('[data-quick-payment]').forEach((input) => { input.value = globalPayment?.value || 'cash'; });
  document.querySelectorAll('[data-quick-quantity]').forEach((input) => { input.value = globalQuantity?.value || '1'; });
  document.querySelectorAll('[data-quick-promoter]').forEach((input) => { input.value = globalPromoter?.value || ''; });
};

globalPayment?.addEventListener('change', syncQuickForms);
globalQuantity?.addEventListener('change', syncQuickForms);
globalPromoter?.addEventListener('change', syncQuickForms);
syncQuickForms();

document.querySelectorAll('[data-quick-form]').forEach((form) => {
  form.addEventListener('submit', () => {
    syncQuickForms();
    const button = form.querySelector('button[type="submit"]');
    if (button) {
      button.disabled = true;
      button.dataset.originalText = button.innerHTML;
      button.innerHTML = '<span>Registrando…</span>';
    }
  });
});

// Floki Manager v1.3: compartir el enlace del QR desde el celular.
document.querySelectorAll('[data-share-qr]').forEach((button) => {
  button.addEventListener('click', async () => {
    const url = button.dataset.shareUrl;
    const name = button.dataset.shareName || 'Promotor Floki';
    try {
      if (navigator.share) {
        await navigator.share({ title: `QR de ${name}`, text: `Código de lista de ${name}`, url });
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(url);
        button.textContent = 'Enlace copiado';
        setTimeout(() => { button.textContent = 'Compartir enlace'; }, 1800);
      } else {
        window.prompt('Copiá este enlace:', url);
      }
    } catch (error) {
      if (error?.name !== 'AbortError') window.prompt('Copiá este enlace:', url);
    }
  });
});

// Floki Manager v1.4: sectores de usuario.
const userRoleSelect = document.querySelector('[data-user-role]');
const userSectorSelect = document.querySelector('[data-user-sector]');
const syncUserSector = () => {
  if (!userRoleSelect || !userSectorSelect) return;
  const isAdmin = userRoleSelect.value === 'admin';
  userSectorSelect.disabled = isAdmin;
  if (isAdmin) userSectorSelect.value = 'ticketing';
};
userRoleSelect?.addEventListener('change', syncUserSector);
syncUserSector();

const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

// Bloc de notas persistente + conversión previa.
const workspace = document.querySelector('[data-list-workspace]');
const workspaceStatus = document.querySelector('[data-workspace-status]');
const workspacePreview = document.querySelector('[data-list-preview]');
let workspaceTimer;
let workspaceRequest = 0;

const renderWorkspacePreview = (payload) => {
  if (!workspacePreview) return;
  const metadata = payload?.metadata || {};
  const groups = payload?.groups || [];
  if (!groups.length) {
    workspacePreview.innerHTML = '<p class="muted">Todavía no se detectaron listas. Pegá el mensaje completo y respetá los promotores en MAYÚSCULAS.</p>';
    return;
  }
  workspacePreview.innerHTML = `
    <div class="preview-summary"><strong>${metadata.guest_count || 0} nombres detectados</strong><span>${metadata.promoter_count || 0} promotores · ${metadata.promo_count || 0} en PROMOS · ${metadata.common_count || 0} en Lista común</span></div>
    <div class="preview-groups">${groups.map((group) => `
      <article><strong>${escapeHtml(group.promoter_name)}</strong><small>${group.guest_count} nombres</small><p>${group.guests.map(escapeHtml).join(', ')}</p></article>
    `).join('')}</div>`;
};

const updateWorkspace = async () => {
  if (!workspace) return;
  const requestId = ++workspaceRequest;
  const sourceText = workspace.value;
  if (workspaceStatus) workspaceStatus.textContent = 'Guardando…';
  try {
    const [saveResponse, previewResponse] = await Promise.all([
      fetch(workspace.dataset.autosaveUrl, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': workspace.dataset.csrf },
        body: JSON.stringify({ source_text: sourceText }),
      }),
      fetch(workspace.dataset.previewUrl, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': workspace.dataset.csrf },
        body: JSON.stringify({ source_text: sourceText }),
      }),
    ]);
    if (requestId !== workspaceRequest) return;
    if (!saveResponse.ok || !previewResponse.ok) throw new Error('No se pudo actualizar');
    const preview = await previewResponse.json();
    renderWorkspacePreview(preview);
    if (workspaceStatus) workspaceStatus.textContent = 'Guardado';
  } catch (error) {
    if (workspaceStatus) workspaceStatus.textContent = 'Sin guardar';
  }
};
workspace?.addEventListener('input', () => {
  clearTimeout(workspaceTimer);
  if (workspaceStatus) workspaceStatus.textContent = 'Editando…';
  workspaceTimer = setTimeout(updateWorkspace, 650);
});

// Búsqueda predictiva de personas y listas.
const predictiveInput = document.querySelector('[data-guest-predict]');
const predictiveResults = document.querySelector('[data-guest-suggestions]');
const predictiveRoot = predictiveInput?.closest('[data-checkin-template]');
let predictiveTimer;
let predictiveController;

const renderSuggestions = (suggestions) => {
  if (!predictiveResults || !predictiveRoot) return;
  if (!suggestions.length) {
    predictiveResults.innerHTML = '<p class="muted">No se encontraron nombres parecidos.</p>';
    return;
  }
  const template = predictiveRoot.dataset.checkinTemplate;
  const csrf = predictiveRoot.dataset.csrf;
  predictiveResults.innerHTML = suggestions.map((item) => {
    const lists = item.lists.map((list) => {
      const action = template.replace('/0/', `/${list.guest_id}/`);
      const unavailable = list.free_available === false;
      const disabled = item.checked_in || unavailable;
      const detail = unavailable ? (list.unavailable_reason || 'FREE no disponible') : (list.is_common ? 'Lista común · hasta las 03:30' : (list.is_promo ? 'PROMOS · hasta las 03:30' : 'Lista de promotor · hasta las 03:30'));
      return `<form action="${escapeHtml(action)}" method="post" class="suggestion-list-form ${unavailable ? 'unavailable' : ''}" data-offline-operation="guest_checkin" data-guest-id="${list.guest_id}" data-confirm="¿Confirmar el ingreso de ${escapeHtml(item.name)} para ${escapeHtml(list.promoter_name)}?">
        <input type="hidden" name="csrf_token" value="${escapeHtml(csrf)}">
        <button type="submit" ${disabled ? 'disabled' : ''}><span>${escapeHtml(list.promoter_name)}</span><small>${escapeHtml(detail)}</small></button>
      </form>`;
    }).join('');
    const status = item.checked_in
      ? `<div class="suggestion-checked">✓ Ya ingresó · ${escapeHtml(item.credited_promoter_name || '')}</div>`
      : '<div class="suggestion-pending">Elegí la lista correcta para confirmar</div>';
    return `<article class="predictive-item ${item.checked_in ? 'checked-in' : ''}"><div class="predictive-person"><strong>${escapeHtml(item.name)}</strong>${status}</div><div class="suggestion-lists">${lists}</div></article>`;
  }).join('');
  predictiveResults.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => { if (!window.confirm(form.dataset.confirm)) event.preventDefault(); });
  });
};

const searchGuests = async () => {
  const query = predictiveInput?.value.trim() || '';
  if (!predictiveResults || !predictiveInput) return;
  if (!query) {
    predictiveResults.innerHTML = '<p class="muted">Escribí al menos una letra para buscar.</p>';
    return;
  }
  predictiveController?.abort();
  predictiveController = new AbortController();
  predictiveResults.innerHTML = '<p class="muted">Buscando…</p>';
  try {
    const response = await fetch(`${predictiveInput.dataset.suggestionsUrl}?q=${encodeURIComponent(query)}`, { signal: predictiveController.signal });
    if (!response.ok) throw new Error('Error de búsqueda');
    const payload = await response.json();
    renderSuggestions(payload.suggestions || []);
  } catch (error) {
    if (error.name !== 'AbortError') predictiveResults.innerHTML = '<p class="muted">No se pudo completar la búsqueda.</p>';
  }
};
predictiveInput?.addEventListener('input', () => { clearTimeout(predictiveTimer); predictiveTimer = setTimeout(searchGuests, 180); });
if (predictiveInput?.value.trim()) searchGuests();

// Floki Manager v1.8: controles visuales Minimal Luxe.
document.querySelectorAll('[data-password-toggle]').forEach((button) => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.passwordToggle);
    if (!input) return;
    const showing = input.type === 'text';
    input.type = showing ? 'password' : 'text';
    button.textContent = showing ? '◉' : '◎';
    button.setAttribute('aria-label', showing ? 'Mostrar contraseña' : 'Ocultar contraseña');
  });
});

document.querySelectorAll('.quick-sale-button, .action-card, .primary-button').forEach((element) => {
  element.addEventListener('pointerdown', () => element.classList.add('is-pressed'));
  ['pointerup', 'pointercancel', 'pointerleave'].forEach((eventName) => {
    element.addEventListener(eventName, () => element.classList.remove('is-pressed'));
  });
});

// Floki Manager v1.9: constructor guiado de variantes de bebidas.
const beverageBuilder = document.querySelector('[data-beverage-builder]');
if (beverageBuilder) {
  const typeSelect = beverageBuilder.querySelector('[data-beverage-type]');
  const brandSelect = beverageBuilder.querySelector('[data-beverage-brand]');
  const presentationSelect = beverageBuilder.querySelector('[data-beverage-presentation]');
  const customBrandField = beverageBuilder.querySelector('[data-custom-brand-field]');
  const customBrandInput = beverageBuilder.querySelector('[data-custom-brand]');
  const preview = beverageBuilder.querySelector('[data-beverage-preview]');

  const refreshBeveragePreview = () => {
    const useCustomBrand = brandSelect?.value === '__custom__';
    if (customBrandField) customBrandField.hidden = !useCustomBrand;
    if (customBrandInput) customBrandInput.required = useCustomBrand;
    const type = typeSelect?.value || 'Bebida';
    const selectedBrand = useCustomBrand ? customBrandInput?.value.trim() : brandSelect?.value;
    const brand = selectedBrand && selectedBrand !== 'Sin marca' ? ` ${selectedBrand}` : '';
    const presentation = presentationSelect?.selectedOptions?.[0]?.textContent || 'Unidad';
    if (preview) preview.textContent = `${type}${brand} · ${presentation}`;
  };

  [typeSelect, brandSelect, presentationSelect, customBrandInput].forEach((field) => {
    field?.addEventListener('input', refreshBeveragePreview);
    field?.addEventListener('change', refreshBeveragePreview);
  });
  refreshBeveragePreview();
}

// Floki Manager v2.5: instalación PWA y estado de conexión.
let deferredInstallPrompt = null;
const installButton = document.querySelector('[data-install-app]');
const networkStatus = document.querySelector('[data-network-status]');
const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
const isIOS = /iphone|ipad|ipod/i.test(window.navigator.userAgent);

const updateNetworkStatus = () => {
  if (!networkStatus) return;
  const online = navigator.onLine;
  networkStatus.classList.toggle('online', online);
  networkStatus.classList.toggle('offline', !online);
  const label = networkStatus.querySelector('span');
  if (label) label.textContent = online ? 'En línea' : 'Sin conexión';
};
window.addEventListener('online', updateNetworkStatus);
window.addEventListener('offline', updateNetworkStatus);
updateNetworkStatus();

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  if (installButton && !isStandalone) installButton.hidden = false;
});

if (installButton && isIOS && !isStandalone) installButton.hidden = false;
installButton?.addEventListener('click', async () => {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    installButton.hidden = true;
    return;
  }
  if (isIOS) {
    window.alert('En iPhone: tocá Compartir y después “Agregar a pantalla de inicio”.');
  } else {
    window.alert('Abrí el menú del navegador y elegí “Instalar aplicación” o “Agregar a pantalla de inicio”.');
  }
});

window.addEventListener('appinstalled', () => {
  if (installButton) installButton.hidden = true;
});

// Floki Manager v2.5.1: vista previa del banner dinámico del evento.
const eventCreateForm = document.querySelector('[data-event-create-form]');
if (eventCreateForm) {
  const imageInput = eventCreateForm.querySelector('[data-event-image-input]');
  const nameInput = eventCreateForm.querySelector('[data-event-name-input]');
  const dateInput = eventCreateForm.querySelector('[data-event-date-input]');
  const preview = eventCreateForm.querySelector('[data-event-banner-preview]');
  const namePreview = eventCreateForm.querySelector('[data-event-name-preview]');
  const datePreview = eventCreateForm.querySelector('[data-event-date-preview]');
  let previewUrl = null;

  const refreshEventCopy = () => {
    if (namePreview) namePreview.textContent = nameInput?.value.trim() || 'Noche Floki';
    if (datePreview && dateInput?.value) {
      const [year, month, day] = dateInput.value.split('-');
      datePreview.textContent = `${day}/${month}/${year}`;
    }
  };

  imageInput?.addEventListener('change', () => {
    const file = imageInput.files?.[0];
    if (!file || !preview) return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);
    preview.style.backgroundImage = `url("${previewUrl}")`;
  });
  nameInput?.addEventListener('input', refreshEventCopy);
  dateInput?.addEventListener('change', refreshEventCopy);
  refreshEventCopy();
}

// v2.8.6: Caja de Bebidas puede revisar sus movimientos recientes sin totales acumulados.


// v2.8.8 · Guardado de precios/configuración sin recargar la página.
const ajaxPriceSettingsForm = document.querySelector('[data-ajax-price-settings]');
if (ajaxPriceSettingsForm) {
  const saveStatus = ajaxPriceSettingsForm.querySelector('[data-price-save-status]');
  const saveButton = ajaxPriceSettingsForm.querySelector('[data-save-price-settings]');
  let dirty = false;

  const markDirty = () => {
    dirty = true;
    if (saveStatus) saveStatus.textContent = 'Cambios sin guardar';
  };

  ajaxPriceSettingsForm.querySelectorAll('select, input').forEach((field) => {
    if (field.name !== 'csrf_token' && field.name !== 'return_section') {
      field.addEventListener('change', markDirty);
      field.addEventListener('input', markDirty);
    }
  });

  ajaxPriceSettingsForm.addEventListener('submit', async (event) => {
    // Los botones Eliminar usan formaction propio y deben seguir funcionando normal.
    if (event.submitter && event.submitter.matches('.tiny-danger')) return;
    event.preventDefault();
    if (!saveButton) return;

    const originalText = saveButton.textContent;
    saveButton.disabled = true;
    saveButton.textContent = 'Guardando…';
    if (saveStatus) saveStatus.textContent = 'Guardando cambios…';

    try {
      const response = await fetch(ajaxPriceSettingsForm.action, {
        method: 'POST',
        body: new FormData(ajaxPriceSettingsForm),
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
        },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.message || 'No se pudieron guardar los cambios');
      dirty = false;
      if (saveStatus) saveStatus.textContent = '✓ Cambios guardados sin recargar la página';
      saveButton.textContent = 'Guardado ✓';
      setTimeout(() => {
        saveButton.textContent = originalText;
        if (saveStatus && !dirty) saveStatus.textContent = 'Podés seguir modificando y guardar todo junto.';
      }, 1800);
    } catch (error) {
      if (saveStatus) saveStatus.textContent = error.message || 'Error al guardar';
      saveButton.textContent = 'Reintentar guardado';
    } finally {
      saveButton.disabled = false;
    }
  });
}

// Floki Manager v2.9.4 · Casilleros para importar stock/gastos del evento anterior.
const previousEventImport = document.querySelector('[data-previous-event-import]');
if (previousEventImport) {
  previousEventImport.querySelectorAll('[data-import-master]').forEach((master) => {
    const groupName = master.dataset.importMaster;
    const items = previousEventImport.querySelector(`[data-import-items="${groupName}"]`);
    const children = items ? Array.from(items.querySelectorAll('input[type="checkbox"]')) : [];

    const refreshImportGroup = () => {
      children.forEach((child) => {
        child.disabled = !master.checked;
      });
    };

    master.addEventListener('change', refreshImportGroup);
    refreshImportGroup();
  });
}
