(() => {
  'use strict';
  if (!document.body.matches('[data-offline-operations-page]')) return;

  const money = (value) => new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(Number(value || 0));
  const normalize = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
  const eventPanel = document.querySelector('[data-offline-event]');
  const operationArea = document.querySelector('[data-offline-operation-area]');
  const conflictPanel = document.querySelector('[data-offline-conflict-panel]');
  const conflictList = document.querySelector('[data-offline-conflict-list]');
  let adminMode = 'ticketing';

  const currentEntryPrice = (entry) => {
    const [hour, minute] = String(entry.cutoff_time || '03:30').split(':').map(Number);
    const now = new Date();
    const current = now.getHours() * 60 + now.getMinutes();
    const cutoff = hour * 60 + minute;
    const after = current >= cutoff && current < 12 * 60;
    return { price: after ? entry.after_price : entry.before_price, phase: after ? `Después de ${entry.cutoff_time}` : `Antes de ${entry.cutoff_time}` };
  };

  const getQueuedGuestKeys = async () => {
    const operations = await window.FlokiOffline.getOperations();
    return new Set(operations
      .filter((item) => ['pending', 'retry'].includes(item.status) && item.operation_type === 'guest_checkin')
      .map((item) => item.payload?.normalized_name || `guest:${item.payload?.guest_id}`));
  };

  const renderHeader = (bootstrap) => {
    if (!bootstrap?.cash_session) {
      eventPanel.innerHTML = '<p class="eyebrow">SIN EVENTO LOCAL</p><h2>No hay una jornada descargada</h2><p class="muted">Conectate, iniciá sesión y abrí el evento al menos una vez para habilitar el modo offline.</p>';
      return;
    }
    const saved = bootstrap.saved_at ? new Date(bootstrap.saved_at).toLocaleString('es-AR') : '—';
    eventPanel.innerHTML = `<div><p class="eyebrow">EVENTO GUARDADO</p><h2>${window.FlokiOffline.escapeHtml(bootstrap.cash_session.event_name)}</h2><p class="muted">${window.FlokiOffline.escapeHtml(bootstrap.user.name)} · ${window.FlokiOffline.escapeHtml(bootstrap.user.sector)}</p></div><div class="offline-event-meta"><strong>${window.FlokiOffline.escapeHtml(bootstrap.cash_session.event_date || '')}</strong><small>Actualizado ${window.FlokiOffline.escapeHtml(saved)}</small></div>`;
  };

  const queueQuickSale = async (payload) => {
    try {
      const operation = await window.FlokiOffline.queueOperation('quick_sale', payload);
      if (navigator.onLine) {
        await window.FlokiOffline.syncPending({ silent: true, refresh: true });
        const remaining = await window.FlokiOffline.getOperations();
        const current = remaining.find((item) => item.operation_id === operation.operation_id);
        if (current?.status === 'conflict') window.FlokiOffline.toast(current.error || 'La operación quedó en conflicto.', 'warning');
        else if (current) window.FlokiOffline.toast('La operación quedó pendiente y se volverá a intentar.', 'warning');
        else window.FlokiOffline.toast('Operación sincronizada.');
      } else {
        window.FlokiOffline.toast('Operación guardada en este dispositivo.');
      }
    } catch (error) {
      window.FlokiOffline.toast(error.message || 'No se pudo guardar', 'error');
    }
  };

  const renderTicketing = async (bootstrap) => {
    const queuedGuests = await getQueuedGuestKeys();
    const entry = bootstrap.entry_prices?.[0];
    const entryData = entry ? currentEntryPrice(entry) : null;
    operationArea.innerHTML = `
      <section class="card offline-controls-card">
        <div class="section-heading compact"><div><p class="eyebrow">BOLETERÍA OFFLINE</p><h2>Operaciones rápidas</h2></div></div>
        <div class="quick-controls two-controls"><label>Medio de pago<select data-offline-payment><option value="cash">Efectivo</option><option value="mercadopago">Mercado Pago</option><option value="transfer">Transferencia</option><option value="debit">Débito</option><option value="credit">Crédito</option><option value="other">Otro</option></select></label><label>Cantidad<select data-offline-quantity>${Array.from({ length: 10 }, (_, index) => `<option value="${index + 1}">${index + 1}</option>`).join('')}</select></label></div>
        <div class="quick-button-grid" data-offline-ticket-buttons></div>
      </section>
      <section class="card offline-guest-card">
        <div class="section-heading compact"><div><p class="eyebrow">LISTAS DESCARGADAS</p><h2>Buscar persona</h2><p class="muted">La confirmación quedará pendiente hasta sincronizar.</p></div></div>
        <label class="offline-search-label">Nombre<input data-offline-guest-search placeholder="Empezá a escribir…" autocomplete="off"></label>
        <div class="predictive-results" data-offline-guest-results><p class="muted">Escribí al menos una letra.</p></div>
      </section>`;

    const buttonArea = operationArea.querySelector('[data-offline-ticket-buttons]');
    if (entryData) {
      buttonArea.insertAdjacentHTML('beforeend', `<button type="button" class="quick-sale-button entry-button" data-offline-entry><span>${window.FlokiOffline.escapeHtml(entry.label)}</span><strong>${money(entryData.price)}</strong><small>${window.FlokiOffline.escapeHtml(entryData.phase)}</small></button>`);
    }
    for (const product of bootstrap.ticketing_products || []) {
      buttonArea.insertAdjacentHTML('beforeend', `<button type="button" class="quick-sale-button cloakroom-button" data-offline-ticket-product="${product.id}"><span>${window.FlokiOffline.escapeHtml(product.name)}</span><strong>${money(product.price)}</strong><small>Guardarropa</small></button>`);
    }

    const payment = operationArea.querySelector('[data-offline-payment]');
    const quantity = operationArea.querySelector('[data-offline-quantity]');
    operationArea.querySelector('[data-offline-entry]')?.addEventListener('click', () => queueQuickSale({ sale_kind: 'entry', category: 'general', payment_method: payment.value, quantity: quantity.value, promoter_id: '' }));
    operationArea.querySelectorAll('[data-offline-ticket-product]').forEach((button) => button.addEventListener('click', () => queueQuickSale({ sale_kind: 'ticketing_product', ticketing_product_id: button.dataset.offlineTicketProduct, payment_method: payment.value, quantity: quantity.value })));

    const input = operationArea.querySelector('[data-offline-guest-search]');
    const results = operationArea.querySelector('[data-offline-guest-results]');
    const renderGuests = () => {
      const query = normalize(input.value);
      if (!query) { results.innerHTML = '<p class="muted">Escribí al menos una letra.</p>'; return; }
      const rows = (bootstrap.guests || []).filter((guest) => normalize(guest.guest_name).includes(query)).slice(0, 30);
      if (!rows.length) { results.innerHTML = '<p class="muted">No se encontraron nombres.</p>'; return; }
      results.innerHTML = rows.map((guest) => {
        const guestKey = guest.normalized_name || `guest:${guest.guest_id}`;
        const queued = queuedGuests.has(guestKey);
        const disabled = guest.checked_in || queued;
        const status = guest.checked_in ? 'Ya ingresó' : (queued ? 'Pendiente de sincronizar' : guest.promoter_name);
        return `<article class="offline-guest-result ${disabled ? 'checked-in' : ''}"><div><strong>${window.FlokiOffline.escapeHtml(guest.guest_name)}</strong><small>${window.FlokiOffline.escapeHtml(status)}</small></div><button type="button" class="secondary-button" data-offline-guest-id="${guest.guest_id}" ${disabled ? 'disabled' : ''}>Confirmar FREE</button></article>`;
      }).join('');
      results.querySelectorAll('[data-offline-guest-id]').forEach((button) => button.addEventListener('click', async () => {
        const guest = rows.find((row) => Number(row.guest_id) === Number(button.dataset.offlineGuestId));
        if (!guest || !window.confirm(`¿Confirmar el ingreso de ${guest.guest_name} para ${guest.promoter_name}?`)) return;
        try {
          await window.FlokiOffline.queueOperation('guest_checkin', { guest_id: guest.guest_id, normalized_name: guest.normalized_name, guest_name: guest.guest_name, promoter_name: guest.promoter_name });
          queuedGuests.add(guest.normalized_name || `guest:${guest.guest_id}`);
          renderGuests();
          window.FlokiOffline.toast('Ingreso guardado en este dispositivo.');
        } catch (error) { window.FlokiOffline.toast(error.message || 'No se pudo guardar', 'error'); }
      }));
    };
    input.addEventListener('input', renderGuests);
  };

  const renderBeverages = (bootstrap) => {
    const products = bootstrap.beverages || [];
    const productOptions = products.map((item) => `<option value="${item.id}">${window.FlokiOffline.escapeHtml(item.name)} · ${window.FlokiOffline.escapeHtml(item.sale_unit)}</option>`).join('');
    const birthdayOptions = (bootstrap.birthdays || []).filter((item) => item.birthday_checked_in).map((item) => `<option value="${item.promoter_id}">${window.FlokiOffline.escapeHtml(item.birthday_person_name)} · ${item.checked_count} ingresaron</option>`).join('');
    operationArea.innerHTML = `
      <section class="card offline-controls-card">
        <div class="section-heading compact"><div><p class="eyebrow">BEBIDAS OFFLINE</p><h2>Venta rápida</h2></div></div>
        <div class="quick-controls two-controls"><label>Medio de pago<select data-offline-payment><option value="cash">Efectivo</option><option value="mercadopago">Mercado Pago</option><option value="transfer">Transferencia</option><option value="debit">Débito</option><option value="credit">Crédito</option><option value="other">Otro</option></select></label><label>Cantidad<select data-offline-quantity>${Array.from({ length: 20 }, (_, index) => `<option value="${index + 1}">${index + 1}</option>`).join('')}</select></label></div>
        <div class="quick-button-grid beverage-grid" data-offline-beverage-buttons></div>
      </section>
      <section class="card offline-benefit-forms">
        <details><summary><strong>BENEFICIO RRPP</strong><small>Sin cobro · descuenta stock</small></summary><div class="details-content stack-form"><label>Bebida<select data-benefit-beverage>${productOptions}</select></label><label>Beneficiario / comentario <small>(opcional)</small><input data-benefit-comment maxlength="120" placeholder="Ej.: Martina Gómez"></label><button type="button" class="primary-button full" data-offline-benefit>Guardar beneficio</button></div></details>
        <details><summary><strong>Bebida especial</strong><small>Precio variable y comentario</small></summary><div class="details-content stack-form"><label>Bebida<select data-special-beverage>${productOptions}</select></label><div class="form-grid-2"><label>Cantidad<select data-special-quantity>${Array.from({ length: 20 }, (_, index) => `<option value="${index + 1}">${index + 1}</option>`).join('')}</select></label><label>Precio unitario<input data-special-price type="number" min="500" max="300000" step="500" value="5000"></label></div><label>Comentario<input data-special-comment maxlength="160" placeholder="Ej.: promoción 2x1" required></label><label>Medio de pago<select data-special-payment><option value="cash">Efectivo</option><option value="mercadopago">Mercado Pago</option><option value="transfer">Transferencia</option><option value="debit">Débito</option><option value="credit">Crédito</option><option value="other">Otro</option></select></label><button type="button" class="primary-button full" data-offline-special>Guardar bebida especial</button></div></details>
        ${birthdayOptions ? `<details><summary><strong>50% OFF cumpleaños</strong><small>Se valida al sincronizar</small></summary><div class="details-content stack-form"><label>Cumpleaños<select data-birthday-promoter>${birthdayOptions}</select></label><label>Bebida<select data-birthday-beverage>${productOptions}</select></label><div class="form-grid-2"><label>Cantidad<select data-birthday-quantity>${Array.from({ length: 20 }, (_, index) => `<option value="${index + 1}">${index + 1}</option>`).join('')}</select></label><label>Medio de pago<select data-birthday-payment><option value="cash">Efectivo</option><option value="mercadopago">Mercado Pago</option><option value="transfer">Transferencia</option><option value="debit">Débito</option><option value="credit">Crédito</option><option value="other">Otro</option></select></label></div><button type="button" class="primary-button full" data-offline-birthday>Guardar 50% OFF</button></div></details>` : ''}
      </section>`;
    const payment = operationArea.querySelector('[data-offline-payment]');
    const quantity = operationArea.querySelector('[data-offline-quantity]');
    const buttons = operationArea.querySelector('[data-offline-beverage-buttons]');
    buttons.innerHTML = products.map((product) => {
      const paid = `<button type="button" class="quick-sale-button beverage-button" data-offline-beverage-id="${product.id}"><span>${window.FlokiOffline.escapeHtml(product.name)}</span><strong>${money(product.price)}</strong><small>${window.FlokiOffline.escapeHtml(product.sale_unit)}</small></button>`;
      const zero = product.is_speed ? `<button type="button" class="quick-sale-button beverage-button benefit-action" data-offline-speed-zero="${product.id}"><span>${window.FlokiOffline.escapeHtml(product.name)} · CHAMPAGNE</span><strong>$0</strong><small>Incluido · descuenta stock</small></button>` : '';
      return paid + zero;
    }).join('');
    buttons.querySelectorAll('[data-offline-beverage-id]').forEach((button) => button.addEventListener('click', () => queueQuickSale({ sale_kind: 'beverage', beverage_id: button.dataset.offlineBeverageId, payment_method: payment.value, quantity: quantity.value })));
    buttons.querySelectorAll('[data-offline-speed-zero]').forEach((button) => button.addEventListener('click', () => queueQuickSale({ sale_kind: 'beverage_zero', beverage_id: button.dataset.offlineSpeedZero, payment_method: 'other', quantity: quantity.value })));
    operationArea.querySelector('[data-offline-benefit]')?.addEventListener('click', () => queueQuickSale({ sale_kind: 'rrpp_benefit', beverage_id: operationArea.querySelector('[data-benefit-beverage]').value, beneficiary_comment: operationArea.querySelector('[data-benefit-comment]').value.trim(), quantity: 1, payment_method: 'other' }));
    operationArea.querySelector('[data-offline-special]')?.addEventListener('click', () => {
      const comment = operationArea.querySelector('[data-special-comment]').value.trim();
      if (comment.length < 2) { window.FlokiOffline.toast('Escribí un comentario para la bebida especial.', 'error'); return; }
      queueQuickSale({ sale_kind: 'special_beverage', beverage_id: operationArea.querySelector('[data-special-beverage]').value, special_price: operationArea.querySelector('[data-special-price]').value, comment, quantity: operationArea.querySelector('[data-special-quantity]').value, payment_method: operationArea.querySelector('[data-special-payment]').value });
    });
    operationArea.querySelector('[data-offline-birthday]')?.addEventListener('click', () => queueQuickSale({ sale_kind: 'birthday_discount', birthday_promoter_id: operationArea.querySelector('[data-birthday-promoter]').value, beverage_id: operationArea.querySelector('[data-birthday-beverage]').value, quantity: operationArea.querySelector('[data-birthday-quantity]').value, payment_method: operationArea.querySelector('[data-birthday-payment]').value }));
  };

  const appendAdminExpense = () => {
    operationArea.insertAdjacentHTML('beforeend', `
      <section class="card offline-controls-card">
        <div class="section-heading compact"><div><p class="eyebrow">GASTOS OFFLINE</p><h2>Agregar gasto</h2><p class="muted">Se guarda en este dispositivo y se suma al cierre cuando sincronice.</p></div></div>
        <div class="stack-form">
          <label>Descripción<input data-offline-expense-description maxlength="180" placeholder="Ej.: hielo, seguridad, proveedor..."></label>
          <label>Monto<input data-offline-expense-amount inputmode="decimal" placeholder="0"></label>
          <label>Medio de pago<select data-offline-expense-payment><option value="cash">Efectivo</option><option value="mercadopago">Mercado Pago</option><option value="transfer">Transferencia</option><option value="debit">Débito</option><option value="credit">Crédito</option><option value="other">Otro</option></select></label>
          <button type="button" class="primary-button full" data-offline-expense>Guardar gasto</button>
        </div>
      </section>`);
    operationArea.querySelector('[data-offline-expense]')?.addEventListener('click', async () => {
      const description = operationArea.querySelector('[data-offline-expense-description]')?.value.trim() || '';
      const amount = operationArea.querySelector('[data-offline-expense-amount]')?.value.trim() || '';
      const payment_method = operationArea.querySelector('[data-offline-expense-payment]')?.value || 'cash';
      if (description.length < 2 || !amount) {
        window.FlokiOffline.toast('Completá descripción y monto del gasto.', 'error');
        return;
      }
      try {
        await window.FlokiOffline.queueOperation('expense', { description, amount, payment_method });
        operationArea.querySelector('[data-offline-expense-description]').value = '';
        operationArea.querySelector('[data-offline-expense-amount]').value = '';
        window.FlokiOffline.toast(navigator.onLine ? 'Gasto guardado. Sincronizando…' : 'Gasto guardado en este dispositivo.');
        if (navigator.onLine) await window.FlokiOffline.syncPending({ silent: false, refresh: true });
      } catch (error) {
        window.FlokiOffline.toast(error.message || 'No se pudo guardar el gasto', 'error');
      }
    });
  };

  const renderAdminMode = async (bootstrap) => {
    if (adminMode === 'beverages') renderBeverages(bootstrap);
    else if (adminMode === 'expenses') { operationArea.innerHTML = ''; appendAdminExpense(); }
    else await renderTicketing(bootstrap);

    operationArea.insertAdjacentHTML('afterbegin', `
      <section class="card offline-admin-switcher">
        <div class="section-heading compact"><div><p class="eyebrow">ADMINISTRACIÓN OFFLINE</p><h2>Elegí el panel</h2></div></div>
        <div class="button-row">
          <button type="button" class="${adminMode === 'ticketing' ? 'primary-button' : 'secondary-button'}" data-admin-offline-mode="ticketing">Boletería</button>
          <button type="button" class="${adminMode === 'beverages' ? 'primary-button' : 'secondary-button'}" data-admin-offline-mode="beverages">Bebidas</button>
          <button type="button" class="${adminMode === 'expenses' ? 'primary-button' : 'secondary-button'}" data-admin-offline-mode="expenses">Gastos</button>
        </div>
        <p class="muted compact-copy">Configuración, importaciones, stock final y cierre de caja requieren conexión. Primero sincronizá todos los pendientes.</p>
      </section>`);
    operationArea.querySelectorAll('[data-admin-offline-mode]').forEach((button) => button.addEventListener('click', async () => {
      adminMode = button.dataset.adminOfflineMode || 'ticketing';
      await renderAdminMode(bootstrap);
    }));
  };

  const renderOperations = async (bootstrap) => {
    renderHeader(bootstrap);
    if (!bootstrap?.cash_session) { operationArea.innerHTML = ''; return; }
    const sector = bootstrap.user?.sector;
    if (bootstrap.user?.role === 'admin') {
      await renderAdminMode(bootstrap);
      return;
    }
    if (sector === 'ticketing') await renderTicketing(bootstrap);
    if (sector === 'beverages') renderBeverages(bootstrap);
  };

  const renderConflicts = async () => {
    const operations = await window.FlokiOffline.getOperations();
    const conflicts = operations.filter((item) => item.status === 'conflict');
    conflictPanel.hidden = conflicts.length === 0;
    conflictList.innerHTML = conflicts.map((item) => `<article class="offline-conflict-item"><div><strong>${window.FlokiOffline.escapeHtml(item.operation_type)}</strong><small>${window.FlokiOffline.escapeHtml(item.user_name || '')} · ${window.FlokiOffline.escapeHtml(item.error || 'Conflicto pendiente')}</small></div><button type="button" class="tiny-danger" data-delete-conflict="${item.operation_id}">Descartar</button></article>`).join('');
    conflictList.querySelectorAll('[data-delete-conflict]').forEach((button) => button.addEventListener('click', async () => {
      if (!window.confirm('¿Descartar esta operación local? No se registrará en la caja.')) return;
      await window.FlokiOffline.deleteOperation(button.dataset.deleteConflict);
      await window.FlokiOffline.updateIndicators();
      renderConflicts();
    }));
  };

  const boot = async () => {
    const bootstrap = await window.FlokiOffline.getBootstrap();
    await renderOperations(bootstrap);
    await renderConflicts();
  };


  document.querySelector('[data-clear-offline]')?.addEventListener('click', async () => {
    const operations = await window.FlokiOffline.getOperations();
    const pending = operations.filter((item) => item.status === 'pending' || item.status === 'retry').length;
    const warning = pending ? `Hay ${pending} operaciones pendientes que se perderán. ` : '';
    if (!window.confirm(`${warning}¿Borrar todos los datos offline de este dispositivo?`)) return;
    await window.FlokiOffline.clearOfflineData();
    eventPanel.innerHTML = '<p class="eyebrow">DATOS LOCALES BORRADOS</p><h2>Volvé a conectarte para preparar el modo offline</h2>';
    operationArea.innerHTML = '';
    await renderConflicts();
  });

  document.addEventListener('floki:offline-unavailable', () => {
    eventPanel.innerHTML = '<p class="eyebrow">MODO OFFLINE NO DISPONIBLE</p><h2>Este navegador no permite almacenamiento local</h2><p class="muted">Usá Chrome, Edge o Safari actualizado.</p>';
    operationArea.innerHTML = '';
  }, { once: true });
  document.addEventListener('floki:offline-ready', boot, { once: true });
  document.addEventListener('floki:bootstrap-updated', (event) => renderOperations(event.detail));
  document.addEventListener('floki:queue-updated', renderConflicts);
  document.addEventListener('floki:operation-queued', async () => {
    const bootstrap = await window.FlokiOffline.getBootstrap();
    await renderOperations(bootstrap);
  });
  document.addEventListener('floki:sync-complete', async () => {
    const bootstrap = await window.FlokiOffline.getBootstrap();
    await renderOperations(bootstrap);
    await renderConflicts();
  });
})();
