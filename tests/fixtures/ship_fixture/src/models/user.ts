import { PrismaClient } from '@prisma/client';
import { User } from '../types';
const prisma = new PrismaClient();
export async function findUserById(id: string): Promise<User | null> {
  return prisma.user.findUnique({ where: { id } });
}
export async function createUser(email: string, name: string): Promise<User> {
  return prisma.user.create({ data: { email, name } });
}
