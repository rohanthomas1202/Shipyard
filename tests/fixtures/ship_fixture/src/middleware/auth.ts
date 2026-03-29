import { Request, Response, NextFunction } from 'express';
import { findUserById } from '../models/user';
export async function authMiddleware(req: Request, res: Response, next: NextFunction) {
  const userId = req.headers['x-user-id'] as string;
  if (!userId) { return res.status(401).json({ error: 'Missing user ID' }); }
  const user = await findUserById(userId);
  if (!user) { return res.status(401).json({ error: 'Invalid user' }); }
  (req as any).user = user;
  next();
}
