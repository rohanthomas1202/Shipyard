import { PrismaClient } from '@prisma/client';
import { Document } from '../types';
const prisma = new PrismaClient();
export async function findDocumentsByAuthor(authorId: string): Promise<Document[]> {
  return prisma.document.findMany({ where: { authorId } });
}
export async function createDocument(title: string, content: string, authorId: string): Promise<Document> {
  return prisma.document.create({ data: { title, content, authorId } });
}
