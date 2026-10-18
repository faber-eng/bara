import type { EvidenceKind, GeoPoint } from "../contracts";
import type { IssuedTicket } from "./upload";

const DATABASE = "bara-outbox";
const STORE = "items";
const VERSION = 1;

export type OutboxItem = {
  id: string;
  volunteerId: string;
  taskId: string;
  kind: EvidenceKind;
  contentType: string;
  blob: Blob;
  sample: boolean;
  point: GeoPoint | null;
  capturedAt: string;
  ticket: IssuedTicket | null;
  queuedAt: number;
};

type StoredItem = Omit<OutboxItem, "blob"> & { bytes: ArrayBuffer; blobType: string };

export type NewOutboxItem = Omit<OutboxItem, "id" | "queuedAt">;

function settle<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("IndexedDB request failed"));
  });
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, VERSION);
    request.onupgradeneeded = () => {
      const store = request.result.createObjectStore(STORE, { keyPath: "id" });
      store.createIndex("volunteerId", "volunteerId");
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("IndexedDB could not open"));
    request.onblocked = () => reject(new Error("IndexedDB is blocked"));
  });
}

function toItem(record: StoredItem): OutboxItem {
  const { bytes, blobType, ...rest } = record;
  return { ...rest, blob: new Blob([bytes], { type: blobType }) };
}

async function withStore<T>(
  mode: IDBTransactionMode,
  action: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const database = await openDatabase();
  try {
    return await settle(action(database.transaction(STORE, mode).objectStore(STORE)));
  } finally {
    database.close();
  }
}

let lastQueuedAt = 0;

function nextQueuedAt(): number {
  lastQueuedAt = Math.max(Date.now(), lastQueuedAt + 1);
  return lastQueuedAt;
}

export async function addOutboxItem(item: NewOutboxItem): Promise<string> {
  const id = crypto.randomUUID();
  const { blob, ...rest } = item;
  const stored: StoredItem = {
    ...rest,
    id,
    queuedAt: nextQueuedAt(),
    bytes: await blob.arrayBuffer(),
    blobType: blob.type,
  };
  await withStore("readwrite", (store) => store.add(stored));
  return id;
}

export async function listOutboxItems(volunteerId: string): Promise<OutboxItem[]> {
  const found = await withStore<StoredItem[]>("readonly", (store) =>
    store.index("volunteerId").getAll(volunteerId),
  );
  return found.sort((first, second) => first.queuedAt - second.queuedAt).map(toItem);
}

export async function countOutboxItems(volunteerId: string): Promise<number> {
  return withStore("readonly", (store) => store.index("volunteerId").count(volunteerId));
}

export async function removeOutboxItem(id: string): Promise<void> {
  await withStore("readwrite", (store) => store.delete(id));
}

export async function saveOutboxTicket(id: string, ticket: IssuedTicket): Promise<void> {
  const database = await openDatabase();
  try {
    const store = database.transaction(STORE, "readwrite").objectStore(STORE);
    const record: StoredItem | undefined = await settle(store.get(id));
    if (record === undefined) return;
    await settle(store.put({ ...record, ticket }));
  } finally {
    database.close();
  }
}
