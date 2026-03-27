import { Document } from '../types/index.js';

export async function findById(id: string): Promise<Document | null> {
  // placeholder implementation
  return null;
}

export async function findAll(): Promise<Document[]> {
  return [];
}

export async function create(
  doc: Omit<Document, 'id' | 'created_at' | 'updated_at'>
): Promise<Document> {
  return {
    ...doc,
    id: 'new-id',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}
