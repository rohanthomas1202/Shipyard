import React from 'react';
import { User } from '../types';
interface Props { user: User; }
export function UserProfile({ user }: Props) {
  return <div><h2>{user.name}</h2><p>{user.email}</p></div>;
}
