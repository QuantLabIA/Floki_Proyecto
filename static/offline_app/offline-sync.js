(() => {
  'use strict';

  const OFFLINE_STORAGE_AVAILABLE = 'indexedDB' in window;
  const DB_NAME = 'floki-manager-offline';
  const DB_VERSION = 1;
  const META_STORE = 'meta';
  const OPERATIONS_STORE = 'operations';
  const BOOTSTRAP_KEY = 'bootstrap';
  const DEVICE_KEY = 'floki-device-id';
  const SUPPORTED_QUICK_KINDS = new Set([
    'entry', 'ticketing_product', 'beverage', 'special_beverage',
    'rrpp_benefit', 'birthday_discount',
  ]);

  let databasePromise = null;
  let syncInProgress = false;
  let knownPendingCount = 0;

  const escapeHtml = (value) => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

  const openDatabase = () => {
    if (databasePromise) return databasePromise;
    databasePromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(META_STORE)) db.createObjectStore(META_STORE, { keyPath: 'key' });
        if (!db.objectStoreNames.contains(OPERATIONS_STORE)) {
          const store = db.createObjectStore(OPERATIONS_STORE, { keyPath: 'operation_id' });
          store.createIndex('status', 'status', { unique: false });
          store.createIndex('created_at', 'created_at', { unique: false });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    return databasePromise;
  };

  const transactionRequest = async (storeName, mode, callback) => {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(storeName, mode);
      const store = tx.objectStore(storeName);
      let result;
      try { result = callback(store); } catch (error) { reject(error); return; }
      tx.oncomplete = () => resolve(result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error || new Error('Operación local cancelada'));
    });
  };

  const requestResult = (request) => new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  const getMeta = async (key) => {
    const db = await openDatabase();
    const tx = db.transaction(META_STORE, 'readonly');
    return requestResult(tx.objectStore(META_STORE).get(key));
  };

  const setMeta = (key, value) => transactionRequest(META_STORE, 'readwrite', (store) => store.put({ key, value }));
  const putOperation = (operation) => transactionRequest(OPERATIONS_STORE, 'readwrite', (store) => store.put(operation));
  const deleteOperation = (operationId) => transactionRequest(OPERATIONS_STORE, 'readwrite', (store) => store.delete(operationId));
  const clearOfflineData = async () => {
    const db = await openDatabase();
    await Promise.all([
      new Promise((resolve, reject) => {
        const tx = db.transaction(META_STORE, 'readwrite');
        tx.objectStore(META_STORE).clear();
        tx.oncomplete = resolve; tx.onerror = () => reject(tx.error);
      }),
      new Promise((resolve, reject) => {
        const tx = db.transaction(OPERATIONS_STORE, 'readwrite');
        tx.objectStore(OPERATIONS_STORE).clear();
        tx.oncomplete = resolve; tx.onerror = () => reject(tx.error);
      }),
    ]);
    await updateIndicators();
  };

  const getOperations = async () => {
    const db = await openDatabase();
    const tx = db.transaction(OPERATIONS_STORE, 'readonly');
    const rows = await requestResult(tx.objectStore(OPERATIONS_STORE).getAll());
    return (rows || []).sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
  };

  const getBootstrap = async () => (await getMeta(BOOTSTRAP_KEY))?.value || null;

  const setBootstrap = async (payload) => {
    if (!payload || typeof payload !== 'object') return;
    payload.saved_at = new Date().toISOString();
    payload.client_received_epoch_ms = Date.now();
    await setMeta(BOOTSTRAP_KEY, payload);
    document.dispatchEvent(new CustomEvent('floki:bootstrap-updated', { detail: payload }));
  };

  const getDeviceId = () => {
    let deviceId = localStorage.getItem(DEVICE_KEY);
    if (!deviceId) {
      const random = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      deviceId = `floki-${random}`;
      localStorage.setItem(DEVICE_KEY, deviceId);
    }
    return deviceId;
  };

  const localTimestamp = () => {
    const now = new Date();
    const pad = (value) => String(value).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  };

  const operationId = () => {
    const random = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    return `op-${random}`;
  };

  const toast = (message, type = 'success') => {
    let stack = document.querySelector('.offline-toast-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.className = 'offline-toast-stack';
      document.body.appendChild(stack);
    }
    const item = document.createElement('div');
    item.className = `offline-toast ${type}`;
    item.textContent = message;
    stack.appendChild(item);
    setTimeout(() => item.remove(), 5000);
  };

  const updateIndicators = async () => {
    const operations = await getOperations();
    const pending = operations.filter((item) => item.status === 'pending' || item.status === 'retry').length;
    const conflicts = operations.filter((item) => item.status === 'conflict').length;
    knownPendingCount = pending;
    document.querySelectorAll('[data-offline-pending]').forEach((element) => { element.textContent = String(pending); });
    document.querySelectorAll('[data-offline-conflicts]').forEach((element) => { element.textContent = String(conflicts); });
    document.querySelectorAll('[data-offline-queue-link]').forEach((element) => {
      element.hidden = pending === 0 && conflicts === 0;
      element.classList.toggle('has-conflicts', conflicts > 0);
    });
    document.querySelectorAll('[data-offline-sync-control]').forEach((element) => {
      element.hidden = pending === 0 && conflicts === 0;
      element.classList.toggle('has-conflicts', conflicts > 0);
      element.title = conflicts > 0 ? `${conflicts} conflicto(s) pendientes de revisión` : `${pending} operación(es) pendientes`;
    });
    document.documentElement.dataset.offlinePending = String(pending);
    document.documentElement.dataset.offlineConflicts = String(conflicts);
    document.dispatchEvent(new CustomEvent('floki:queue-updated', { detail: { pending, conflicts, operations } }));
    return { pending, conflicts, operations };
  };

  const currentCsrf = async () => {
    const pageToken = document.documentElement.dataset.flokiCsrf || document.querySelector('input[name="csrf_token"]')?.value;
    if (pageToken) return pageToken;
    return (await getBootstrap())?.csrf_token || '';
  };

  const refreshBootstrap = async () => {
    if (!navigator.onLine) return getBootstrap();
    const response = await fetch('/api/offline/bootstrap', { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
    const contentType = response.headers.get('content-type') || '';
    if (!response.ok || !contentType.includes('application/json')) throw new Error('Iniciá sesión para actualizar los datos offline');
    const payload = await response.json();
    await setBootstrap(payload);
    return payload;
  };

  const queueOperation = async (operationType, payload, options = {}) => {
    let bootstrap = options.bootstrap || await getBootstrap();
    const pageUserId = Number(document.documentElement.dataset.flokiUserId || 0);
    const wrongUser = pageUserId && Number(bootstrap?.user?.id || 0) !== pageUserId;
    if ((!bootstrap?.cash_session?.id || !bootstrap?.user?.id || wrongUser) && navigator.onLine) {
      bootstrap = await refreshBootstrap();
    }
    if (!bootstrap?.cash_session?.id || !bootstrap?.user?.id) throw new Error('Abrí el evento con internet al menos una vez antes de usar el modo offline');
    const elapsed = Math.max(0, Date.now() - Number(bootstrap.client_received_epoch_ms || Date.now()));
    const trustedEpoch = Number(bootstrap.server_epoch_ms || Date.now()) + elapsed;
    const finalPayload = { ...payload };
    if (operationType === 'guest_checkin' && !finalPayload.normalized_name) {
      const guest = (bootstrap.guests || []).find((item) => Number(item.guest_id) === Number(finalPayload.guest_id));
      if (guest) {
        finalPayload.normalized_name = guest.normalized_name;
        finalPayload.guest_name = guest.guest_name;
        finalPayload.promoter_name = guest.promoter_name;
      }
    }
    const operation = {
      operation_id: operationId(),
      operation_type: operationType,
      cash_session_id: bootstrap.cash_session.id,
      user_id: bootstrap.user.id,
      user_name: bootstrap.user.name,
      device_id: getDeviceId(),
      created_at: localTimestamp(),
      created_at_epoch_ms: trustedEpoch,
      status: 'pending',
      payload: finalPayload,
    };
    await putOperation(operation);
    await updateIndicators();
    document.dispatchEvent(new CustomEvent('floki:operation-queued', { detail: operation }));
    return operation;
  };

  const syncPending = async ({ silent = false, refresh = true } = {}) => {
    if (syncInProgress || !navigator.onLine) return null;
    syncInProgress = true;
    document.documentElement.classList.add('offline-syncing');
    try {
      if (refresh) {
        try { await refreshBootstrap(); } catch (error) { /* La cola puede conservarse hasta el próximo inicio de sesión. */ }
      }
      const all = await getOperations();
      const bootstrap = await getBootstrap();
      const activeUserId = Number(bootstrap?.user?.id || document.documentElement.dataset.flokiUserId || 0);
      const pending = all.filter((item) => (item.status === 'pending' || item.status === 'retry') && Number(item.user_id) === activeUserId).slice(0, 100);
      if (!activeUserId && all.some((item) => item.status === 'pending' || item.status === 'retry')) {
        throw new Error('Iniciá sesión con el usuario que creó las operaciones para sincronizarlas');
      }
      if (!pending.length) {
        await updateIndicators();
        return { applied: 0, conflicts: 0, retry: 0 };
      }
      const csrf = await currentCsrf();
      if (!csrf) throw new Error('Iniciá sesión para sincronizar las operaciones pendientes');
      const response = await fetch('/api/offline/sync', {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, Accept: 'application/json' },
        body: JSON.stringify({ device_id: getDeviceId(), operations: pending }),
      });
      const contentType = response.headers.get('content-type') || '';
      if (!response.ok || !contentType.includes('application/json')) throw new Error('No se pudo sincronizar. Revisá la sesión e intentá nuevamente');
      const payload = await response.json();
      for (const result of payload.results || []) {
        const local = pending.find((item) => item.operation_id === result.operation_id);
        if (!local) continue;
        if (result.status === 'applied') {
          await deleteOperation(local.operation_id);
        } else if (result.status === 'conflict') {
          local.status = 'conflict';
          local.error = result.result?.message || 'Conflicto pendiente de revisión';
          await putOperation(local);
        } else {
          local.status = 'retry';
          local.error = result.result?.message || 'Se volverá a intentar';
          await putOperation(local);
        }
      }
      if (payload.bootstrap) await setBootstrap(payload.bootstrap);
      await updateIndicators();
      const summary = payload.summary || {};
      if (!silent) {
        if (summary.conflicts) toast(`${summary.applied || 0} operaciones sincronizadas y ${summary.conflicts} con conflicto.`, 'warning');
        else if (summary.applied) toast(`${summary.applied} operaciones sincronizadas correctamente.`);
      }
      document.dispatchEvent(new CustomEvent('floki:sync-complete', { detail: payload }));
      return summary;
    } finally {
      syncInProgress = false;
      document.documentElement.classList.remove('offline-syncing');
    }
  };

  const formPayload = (form) => {
    const data = {};
    new FormData(form).forEach((value, key) => {
      if (key !== 'csrf_token' && typeof value === 'string') data[key] = value;
    });
    return data;
  };

  const supportedForm = (form) => {
    const explicit = form.dataset.offlineOperation;
    if (explicit === 'quick_sale') return { type: 'quick_sale', payload: formPayload(form) };
    if (explicit === 'guest_checkin') return { type: 'guest_checkin', payload: { guest_id: form.dataset.guestId } };
    if (explicit === 'expense') return { type: 'expense', payload: formPayload(form) };
    const action = new URL(form.action, window.location.href).pathname;
    if (action === '/movements/quick-sale') return { type: 'quick_sale', payload: formPayload(form) };
    if (action === '/movements/expense') return { type: 'expense', payload: formPayload(form) };
    const match = action.match(/^\/promoter-lists\/(\d+)\/check-in$/);
    if (match) return { type: 'guest_checkin', payload: { guest_id: match[1] } };
    return null;
  };

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    const supported = supportedForm(form);
    if (!supported) return;
    // Etapa 1 segura: con internet NO interceptamos nada; Flask maneja el formulario como siempre.
    if (navigator.onLine) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) return;
    const buttons = [...form.querySelectorAll('button[type="submit"]')];
    buttons.forEach((button) => { button.disabled = true; });
    try {
      if (!OFFLINE_STORAGE_AVAILABLE) throw new Error('Este navegador no permite guardar operaciones sin conexión');
      if (supported.type === 'quick_sale' && !SUPPORTED_QUICK_KINDS.has(supported.payload.sale_kind)) {
        throw new Error('Esta operación requiere conexión a internet');
      }
      const operation = await queueOperation(supported.type, supported.payload);
      buttons.forEach((button) => {
        button.classList.add('queued-pulse');
        setTimeout(() => button.classList.remove('queued-pulse'), 900);
      });
      if (!navigator.onLine) {
        const offlineMessage = supported.type === 'guest_checkin'
          ? 'Ingreso guardado en este dispositivo. Se sincronizará al volver internet.'
          : (supported.type === 'expense'
            ? 'Gasto guardado en este dispositivo. Se sincronizará al volver internet.'
            : 'Venta guardada sin conexión. Se sincronizará automáticamente.');
        toast(offlineMessage);
        return;
      }
      await syncPending({ silent: true, refresh: false });
      const remaining = await getOperations();
      const current = remaining.find((item) => item.operation_id === operation.operation_id);
      if (!current) {
        sessionStorage.setItem('floki-sync-message', supported.type === 'guest_checkin' ? 'Ingreso confirmado y sincronizado.' : 'Venta registrada y sincronizada.');
        window.location.reload();
      } else if (current.status === 'conflict') {
        toast(current.error || 'La operación quedó en conflicto', 'warning');
      } else {
        toast('La operación quedó pendiente y se volverá a intentar.', 'warning');
      }
    } catch (error) {
      toast(error.message || 'No se pudo guardar la operación offline', 'error');
    } finally {
      buttons.forEach((button) => { button.disabled = false; });
    }
  }, true);

  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.matches('form[action$="/cash/close"]')) return;
    if (knownPendingCount > 0) {
      event.preventDefault();
      event.stopImmediatePropagation();
      window.alert(`Hay ${knownPendingCount} operaciones pendientes en este dispositivo. Conectalo y sincronizá antes de cerrar la caja.`);
    }
  }, true);

  document.querySelectorAll('[data-sync-now]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      const original = button.textContent;
      button.textContent = 'Sincronizando…';
      try { await syncPending(); } catch (error) { toast(error.message || 'No se pudo sincronizar', 'error'); }
      button.textContent = original;
      button.disabled = false;
    });
  });

  const reloadAfterApplied = (summary) => {
    if (!summary?.applied || document.body.matches('[data-offline-operations-page]')) return false;
    sessionStorage.setItem('floki-sync-message', `${summary.applied} operaciones pendientes fueron sincronizadas.`);
    window.location.reload();
    return true;
  };

  window.addEventListener('online', async () => {
    try {
      const summary = await syncPending({ silent: false, refresh: true });
      reloadAfterApplied(summary);
    } catch (error) { /* Indicador principal ya muestra conexión. */ }
  });

  const syncWhenActive = async () => {
    if (!navigator.onLine || document.visibilityState === 'hidden') return;
    try {
      const summary = await syncPending({ silent: true, refresh: true });
      reloadAfterApplied(summary);
    } catch (_) {
      // La cola permanece local hasta que haya conexión y sesión válidas.
    }
  };
  window.addEventListener('focus', syncWhenActive);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') syncWhenActive();
  });

  window.FlokiOffline = {
    getBootstrap,
    refreshBootstrap,
    queueOperation,
    getOperations,
    putOperation,
    deleteOperation,
    clearOfflineData,
    syncPending,
    updateIndicators,
    toast,
    escapeHtml,
  };

  const initialize = async () => {
    if (!OFFLINE_STORAGE_AVAILABLE) {
      document.dispatchEvent(new CustomEvent('floki:offline-unavailable'));
      return;
    }
    const restoredMessage = sessionStorage.getItem('floki-sync-message');
    if (restoredMessage) {
      sessionStorage.removeItem('floki-sync-message');
      setTimeout(() => toast(restoredMessage), 80);
    }
    await updateIndicators();
    if (navigator.onLine) {
      try {
        const summary = await syncPending({ silent: true, refresh: true });
        if (reloadAfterApplied(summary)) return;
      } catch (error) {
        // La app normal sigue funcionando; la cola se conserva.
      }
    }
    document.dispatchEvent(new CustomEvent('floki:offline-ready'));
  };

  initialize().catch(() => {});
})();
