import { Router } from 'express';
import { findUserById, createUser } from '../models/user';
import { ApiResponse, User } from '../types';
const router = Router();
router.get('/:id', async (req, res) => {
  const user = await findUserById(req.params.id);
  const response: ApiResponse<User | null> = { data: user };
  res.json(response);
});
router.post('/', async (req, res) => {
  const user = await createUser(req.body.email, req.body.name);
  const response: ApiResponse<User> = { data: user };
  res.status(201).json(response);
});
export default router;
