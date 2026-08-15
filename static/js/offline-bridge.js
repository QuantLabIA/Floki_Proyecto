(() => {
  'use strict';
  if (!('indexedDB' in window)) return;
  const DB_NAME = 'floki-manager-offline';
  const DB_VERSION = 1;
  const META_STORE = 'meta';
  const OPERATIONS_STORE = 'operations';

  const openDatabase = () => new Promise((resolve, reject) => {
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

  const requestResult = (request) => new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  const saveBootstrap = async (payload) => {
    payload.saved_at = new Date().toISOString();
    payload.client_received_epoch_ms = Date.now();
    const db = await openDatabase();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(META_STORE, 'readwrite');
      tx.objectStore(META_STORE).put({ key: 'bootstrap', value: payload });
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  };

  const refreshBadge = async () => {
    const db = await openDatabase();
    const tx = db.transaction(OPERATIONS_STORE, 'readonly');
    const rows = await requestResult(tx.objectStore(OPERATIONS_STORE).getAll());
    const pending = (rows || []).filter((row) => row.status === 'pending' || row.status === 'retry').length;
    const conflicts = (rows || []).filter((row) => row.status === 'conflict').length;
    document.querySelectorAll('[data-offline-bridge-pending]').forEach((el) => { el.textContent = String(pending); });
    document.querySelectorAll('[data-offline-bridge-link]').forEach((el) => {
      el.classList.toggle('has-conflicts', conflicts > 0);
      el.title = conflicts ? `${conflicts} conflicto(s) offline` : `${pending} operación(es) offline pendientes`;
    });
  };

  const prepare = async () => {
    try {
      // v2.10.5: este puente solo prepara IndexedDB/bootstrap. Nunca registra Service Workers.
      if (navigator.onLine) {
        const response = await fetch('/api/offline/bootstrap', { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
        if (response.ok && (response.headers.get('content-type') || '').includes('application/json')) {
          await saveBootstrap(await response.json());
        }
      }
      await refreshBadge();
    } catch (_) {
      // Cualquier problema de preparación offline jamás bloquea la aplicación principal.
    }
  };

  window.addEventListener('load', prepare, { once: true });
  window.addEventListener('online', prepare);
  window.addEventListener('focus', refreshBadge);
})();
